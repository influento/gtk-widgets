"""Tests for the launcher's dmenu row options and launcher-clipboard's sorting
(src/gtk_widgets/widgets/launcher/options.py, clipboard.py). No GTK, no cliphist: entries
come from a fake listing, decode() from a dict, files from a temp dir.

  uv run pytest -c pytest.toml tests/launcher_clipboard_test.py
"""

from pathlib import Path
from typing import override

import pytest

from gtk_widgets.widgets.launcher import clipboard, options
from gtk_widgets.widgets.launcher.options import Options
from gtk_widgets.widgets.launcher.selection import Forms

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
WEBP = b"RIFF\x24\0\0\0WEBPVP8 " + b"\x9d" * 24
# 1x1 GIFs: header + colour table, then per frame a control extension and an image
_GIF_HEAD = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
_GIF_FRAME = b"!\xf9\x04\x00\x0a\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00"
GIF_STILL = _GIF_HEAD + _GIF_FRAME + b";"
GIF_ANIM = _GIF_HEAD + _GIF_FRAME + _GIF_FRAME + b";"
OWNER_ONLY_FILE, OWNER_ONLY_DIR = 0o600, 0o700
MODE_BITS = 0o777


# --- options ---


def test_plain_line_has_no_options() -> None:
    assert options.split("12\tswaymsg reload") == ("12\tswaymsg reload", {})


def test_pairs_after_nul_and_repeated_keys() -> None:
    text, opts = options.split(
        "3\tsheets\0kind\x1ffiles\x1fpreview\x1f/a.png\x1fpreview\x1f/b.png"
    )
    assert text == "3\tsheets"
    assert opts == {"kind": ["files"], "preview": ["/a.png", "/b.png"]}
    assert options.first(opts, "preview") == "/a.png"
    assert options.first(opts, "icon", "none") == "none"


def test_gif_frames(tmp_path: Path) -> None:
    still, anim, png = (tmp_path / n for n in ("s.gif", "a.gif", "p.gif"))
    for path, data in ((still, GIF_STILL), (anim, GIF_ANIM), (png, PNG)):
        _ = path.write_bytes(data)
    assert not options.gif_animated(str(still))
    assert options.gif_animated(str(anim))
    assert not options.gif_animated(str(png))  # not a GIF
    assert not options.gif_animated(str(tmp_path / "gone.gif"))


# --- launcher-clipboard's rows ---


class Board:
    """A cache dir under a temp dir, cliphist's bytes per id and the ids decoded."""

    def __init__(self, root: Path) -> None:
        self.dir = root
        self.cache = str(root / "cache")
        self.blobs: dict[str, bytes] = {}
        self.decoded: list[str] = []

    def file(self, name: str, data: bytes = b"x") -> str:
        path = self.dir / name
        path.parent.mkdir(exist_ok=True, parents=True)
        _ = path.write_bytes(data)
        return str(path)

    def decode(self, cid: str) -> bytes:
        self.decoded.append(cid)
        return self.blobs[cid]

    def rows(self, *entries: tuple[str, str]) -> dict[str, tuple[str, Options]]:
        """entries: (id, preview text); -> {id: (text, options)}"""
        listing = "\n".join(f"{cid}\t{text}" for cid, text in entries).encode()
        out = clipboard.run(listing, self.decode, root=self.cache)
        return {o.split("\t", 1)[0]: options.split(o.split("\t", 1)[1]) for o in out}


@pytest.fixture
def board(tmp_path: Path) -> Board:
    return Board(tmp_path)


def test_image_data_is_decoded_once_and_named(board: Board) -> None:
    board.blobs["7"] = PNG
    row = board.rows(("7", "[[ binary data 245 KiB png 1920x1080 ]]"))["7"]
    assert row[0] == "PNG image · 1920\N{MULTIPLICATION SIGN}1080"
    assert row[1]["kind"] == ["image"]
    assert row[1]["detail"] == ["245 KiB"]
    data = row[1]["preview"][0]
    assert Path(data).read_bytes() == PNG
    assert row[1]["icon"] == [data]
    _ = board.rows(("7", "[[ binary data 245 KiB png 1920x1080 ]]"))
    assert board.decoded == ["7"]  # the second run reads the cache


def test_gif_data(board: Board) -> None:
    board.blobs["8"] = GIF_ANIM
    row = board.rows(("8", "[[ binary data 1.2 MiB gif 480x270 ]]"))["8"]
    assert row[1]["kind"] == ["gif"]


def test_bytes_cliphist_cannot_name(board: Board) -> None:
    board.blobs["5"] = WEBP
    board.blobs["6"] = b"\x8f\x01junk\x00\xff" * 40
    rows = board.rows(("5", "RIFF�� WEBPVP8 �"), ("6", "��junk"))
    assert rows["5"][0] == "WEBP image"
    assert rows["5"][1]["kind"] == ["image"]
    assert rows["5"][1]["icon"][0].endswith("5.webp")
    assert rows["6"][0] == "Binary data · 320 B"
    assert rows["6"][1]["kind"] == ["binary"]
    assert "icon" not in rows["6"][1]


def test_file_links(board: Board) -> None:
    shot = board.file("shots/screenshot 1.png", PNG)
    rec = board.file("rec/recording.gif", GIF_ANIM)
    pdf = board.file("docs/report.pdf")
    uri = "file://" + shot.replace(" ", "%20")
    rows = board.rows(
        ("1", uri),
        ("2", "file://" + rec),
        ("3", "file://" + pdf),
        ("4", "file:///nowhere/gone.png"),
    )
    assert rows["1"][0] == "screenshot 1.png"
    assert rows["1"][1]["kind"] == ["image"]
    assert rows["1"][1]["icon"] == [shot]
    assert rows["2"][1]["kind"] == ["gif"]
    assert rows["3"][1]["kind"] == ["file"]
    assert "icon" not in rows["3"][1]
    assert rows["4"][1]["kind"] == ["missing"]
    assert rows["4"][1]["detail"][0].endswith("· missing")
    assert board.decoded == []  # whole previews need no decode


def test_several_links_cut_by_cliphist_are_decoded(board: Board) -> None:
    sheets = [board.file(f"rec/sheet-{i}.png", PNG) for i in (1, 2, 3)]
    board.blobs["9"] = "\r\n".join("file://" + s for s in sheets).encode()
    row = board.rows(("9", "file://" + sheets[0] + " file://" + sheets[1][:20] + "…"))[
        "9"
    ]
    assert row[1]["kind"] == ["files"]
    assert row[1]["preview"] == sheets
    assert row[1]["count"] == ["3"]
    assert row[1]["icon"] == [sheets[0]]
    assert row[0].startswith("3 files: sheet-1.png, sheet-2.png")


def test_plain_paths_and_text(board: Board) -> None:
    folder = board.dir / "forks" / "tmux"
    folder.mkdir(parents=True)
    board.blobs.update({"2": b"/no/such/path", "3": b"git log --oneline -20"})
    rows = board.rows(
        ("1", str(folder)), ("2", "/no/such/path"), ("3", "git log --oneline -20")
    )
    assert rows["1"][0] == "tmux/"
    assert rows["1"][1]["kind"] == ["folder"]
    assert rows["2"][1]["kind"] == ["text"]  # not a file: left as typed
    assert rows["3"][0] == "git log --oneline -20"
    assert rows["3"][1]["kind"] == ["text"]


def test_text_keeps_its_lines_privately(board: Board) -> None:
    # cliphist's preview joins lines and cuts at 100 characters; the pane gets the whole text
    full = "def f():\n    return 1\n\n\tdone\n" + "x" * 300
    board.blobs["5"] = full.encode()
    row = board.rows(
        (
            "5",
            "def f(): return 1 done xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx…",
        )
    )["5"]
    path = Path(row[1]["text"][0])
    assert path.read_text(encoding="utf-8") == full
    assert path.stat().st_mode & MODE_BITS == OWNER_ONLY_FILE
    assert Path(board.cache).stat().st_mode & MODE_BITS == OWNER_ONLY_DIR
    _ = board.rows(("5", "def f(): return 1 done"))
    assert board.decoded == ["5"]  # decoded once


def test_cache_keeps_only_listed_entries(board: Board) -> None:
    board.blobs.update({"1": PNG, "2": PNG})
    _ = board.rows(
        ("1", "[[ binary data 1 KiB png 1x1 ]]"),
        ("2", "[[ binary data 1 KiB png 1x1 ]]"),
    )
    _ = board.rows(("2", "[[ binary data 1 KiB png 1x1 ]]"))
    assert sorted(p.name for p in Path(board.cache).iterdir()) == ["2.png"]


def test_pick_still_decodes(board: Board) -> None:
    # cliphist decode reads only "<id>\t": the options after the label must not change that
    board.blobs["4"] = PNG
    out = clipboard.run(
        b"4\t[[ binary data 1 KiB png 1x1 ]]", board.decode, root=board.cache
    )
    assert out[0].startswith("4\t")
    assert "\n" not in out[0]


# --- launcher-clipboard --restore and --offer ---


type CliphistEntry = tuple[str, str, bytes]  # id, list text, bytes


class FakeCliphist:
    """cliphist over a list of (id, list text, bytes), newest first; store
    moves identical bytes to the top under a new id, as cliphist does."""

    def __init__(self, entries: list[CliphistEntry]) -> None:
        self.entries = list(entries)
        self.next = max(int(e[0]) for e in entries) + 1

    def __call__(self, *args: str, data: bytes | None = None) -> bytes:
        if args == ("list",):
            return b"\n".join(f"{i}\t{t}".encode() for i, t, _ in self.entries) + b"\n"
        if args == ("decode",) and data is not None:
            cid = data.decode().split("\t")[0]
            return next(r for i, _, r in self.entries if i == cid)
        if args == ("store",):
            old = next(e for e in self.entries if e[2] == data)
            self.entries.remove(old)
            self.entries.insert(0, (str(self.next), old[1], old[2]))
            self.next += 1
            return b""
        raise AssertionError(args)


class IntruderCliphist(FakeCliphist):
    """A copy lands between the pick's store and the listing after it."""

    @override
    def __call__(self, *args: str, data: bytes | None = None) -> bytes:
        out = super().__call__(*args, data=data)
        if args == ("store",):
            self.entries.insert(
                0, (str(self.next), "copied meanwhile", b"copied meanwhile")
            )
            self.next += 1
        return out


class Restore:
    """restore() into a cache dir, with what it served and what it wl-copied."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.root = str(tmp / "cache")
        self.served: list[Forms] = []
        self.copied: list[bytes] = []

    def restore(self, cliphist: FakeCliphist, cid: str, *, offer: bool = False) -> None:
        clipboard.restore(
            cid,
            cliphist,
            self.served.append,
            self.copied.append,
            self.root,
            offer=offer,
        )

    def types(self) -> list[str]:
        return [m for m, _ in self.served[0]]

    def cached(self, name: str) -> str:
        return str(Path(self.root) / name)


@pytest.fixture
def rs(tmp_path: Path) -> Restore:
    return Restore(tmp_path)


def test_image_data_goes_up_as_bytes_file_and_path(rs: Restore) -> None:
    ch = FakeCliphist(
        [("7", "hello", b"hello"), ("5", "[[ binary data 40 B png 1x1 ]]", PNG)]
    )
    rs.restore(ch, "5")
    assert ch.entries[0][0] == "8"  # moved to the top, new id
    path = rs.cached("8.png")
    assert Path(path).read_bytes() == PNG
    forms = dict(rs.served[0])
    assert rs.types()[0] == "image/png"
    assert forms["image/png"] == PNG
    assert forms["text/uri-list"] == f"file://{path}".encode()
    assert forms["text/plain"] == path.encode()
    assert clipboard.MARKER in forms
    assert rs.copied == []


def assert_gif_goes_up_as_file_and_path(rs: Restore, path: str) -> None:
    assert Path(path).read_bytes() == GIF_ANIM
    forms = dict(rs.served[0])
    assert "image/gif" not in forms
    assert rs.types()[0] == "text/uri-list"
    assert forms["text/uri-list"] == f"file://{path}".encode()
    assert forms["text/plain"] == path.encode()


def test_gif_restore_goes_up_as_file_and_path_not_bytes(rs: Restore) -> None:
    ch = FakeCliphist([("6", "[[ binary data 1 KiB gif 1x1 ]]", GIF_ANIM)])
    rs.restore(ch, "6")
    assert_gif_goes_up_as_file_and_path(rs, rs.cached("7.gif"))


def test_gif_offer_goes_up_as_file_and_path_not_bytes(rs: Restore) -> None:
    ch = FakeCliphist([("6", "[[ binary data 1 KiB gif 1x1 ]]", GIF_ANIM)])
    rs.restore(ch, "6", offer=True)
    assert_gif_goes_up_as_file_and_path(rs, rs.cached("6.gif"))


def test_cached_file_follows_the_new_id(rs: Restore) -> None:
    Path(rs.root).mkdir(parents=True)
    _ = Path(rs.cached("5.png")).write_bytes(PNG)
    ch = FakeCliphist([("5", "[[ binary data 40 B png 1x1 ]]", PNG)])
    rs.restore(ch, "5")
    assert sorted(p.name for p in Path(rs.root).iterdir()) == ["6.png"]


def test_cached_file_follows_the_pick_when_a_copy_lands_meanwhile(rs: Restore) -> None:
    ch = IntruderCliphist(
        [("7", "hello", b"hello"), ("5", "[[ binary data 40 B png 1x1 ]]", PNG)]
    )
    rs.restore(ch, "5")
    bumped = next(i for i, _, raw in ch.entries if raw == PNG)
    assert [p.name for p in Path(rs.root).iterdir()] == [f"{bumped}.png"]
    path = dict(rs.served[0])["text/plain"].decode()
    assert path == rs.cached(f"{bumped}.png")
    assert Path(path).read_bytes() == PNG


def test_sniffed_webp_is_image_data(rs: Restore) -> None:
    ch = FakeCliphist([("3", "RIFF�", WEBP)])
    rs.restore(ch, "3")
    assert rs.types()[0] == "image/webp"


def test_gif_link_goes_as_file_and_path_never_bytes(rs: Restore) -> None:
    gif = rs.tmp / "rec ording.gif"
    _ = gif.write_bytes(GIF_ANIM)
    uri = gif.as_uri().encode()
    ch = FakeCliphist([("4", uri.decode(), uri)])
    rs.restore(ch, "4")
    forms = dict(rs.served[0])
    assert rs.types()[0] == "text/uri-list"
    assert forms["text/uri-list"] == uri
    assert forms["text/plain;charset=utf-8"] == str(gif).encode()
    assert "image/gif" not in forms


def test_still_image_link_also_offers_bytes(rs: Restore) -> None:
    png = rs.tmp / "shot.png"
    _ = png.write_bytes(PNG)
    uri = png.as_uri().encode()
    rs.restore(FakeCliphist([("4", uri.decode(), uri)]), "4")
    assert dict(rs.served[0])["image/png"] == PNG


def test_several_links_give_paths_one_per_line(rs: Restore) -> None:
    a, b = (str(rs.tmp / n) for n in ("sheet-1.png", "sheet-2.png"))
    raw = f"file://{a}\r\nfile://{b}".encode()
    rs.restore(FakeCliphist([("9", raw.decode(), raw)]), "9")
    forms = dict(rs.served[0])
    assert forms["text/plain"] == f"{a}\n{b}".encode()
    assert "image/png" not in forms


def test_text_goes_through_wl_copy(rs: Restore) -> None:
    ch = FakeCliphist([("2", "/etc/hostname", b"/etc/hostname"), ("1", "hi", b"hi")])
    rs.restore(ch, "2")
    rs.restore(ch, "1")
    assert rs.copied == [b"/etc/hostname", b"hi"]
    assert rs.served == []


def test_offer_keeps_the_entry_and_its_id(rs: Restore) -> None:
    ch = FakeCliphist(
        [("5", "[[ binary data 40 B png 1x1 ]]", PNG), ("4", "hi", b"hi")]
    )
    rs.restore(ch, "5", offer=True)
    assert [e[0] for e in ch.entries] == ["5", "4"]
    assert dict(rs.served[0])["text/plain"] == rs.cached("5.png").encode()


def test_offer_leaves_text_alone(rs: Restore) -> None:
    ch = FakeCliphist([("4", "hi", b"hi")])
    rs.restore(ch, "4", offer=True)
    assert (rs.served, rs.copied) == ([], [])


def test_failed_serve_falls_back_to_wl_copy(rs: Restore) -> None:
    def broken(_forms: Forms) -> None:
        msg = "no data-control"
        raise OSError(msg)

    ch = FakeCliphist([("5", "[[ binary data 40 B png 1x1 ]]", PNG)])
    clipboard.restore("5", ch, broken, rs.copied.append, rs.root)
    assert rs.copied == [PNG]
