"""Webcam backgrounds: link files played through yt-dlp, a link added from
the popup, and the background grid. yt-dlp is a stand-in script on PATH
that serves a local clip, so no test reaches the network."""

import os
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from gtk_widgets.lib.ui.widget_base import Gtk
from gtk_widgets.widgets.webcam import links
from gtk_widgets.widgets.webcam.effects import Animation
from gtk_widgets.widgets.webcam.gallery import REMOVE_GLYPH, Gallery

LINK = "https://example.com/video"
WAIT_S = 10  # each wait below takes ~1-3 s when the code is right


@pytest.fixture(autouse=True)
def threads_end_with_their_test() -> Iterator[None]:
    """Wait for the threads a test started (thumbnail loaders, players):
    one still starting ffmpeg while the next test changes PATH fails with
    "Bad address", and the error lands on that next test."""
    before = set(threading.enumerate())
    yield
    deadline = time.monotonic() + WAIT_S
    for thread in set(threading.enumerate()) - before:
        thread.join(max(0.0, deadline - time.monotonic()))


def _wait_for(done: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + WAIT_S
    while not done():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def _script(path: Path, body: str) -> None:
    _ = path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    path.chmod(0o755)


@pytest.fixture
def clip(tmp_path: Path) -> Path:
    """A 1 s video, streamable from a pipe."""
    path = tmp_path / "clip.mp4"
    _ = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=30:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def yt_dlp_serving(tmp_path: Path, clip: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A yt-dlp on PATH that writes the clip to stdout; returns the file
    each run appends a line to."""
    runs = tmp_path / "runs.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _script(bin_dir / "yt-dlp", f"echo run >> '{runs}'\ncat '{clip}'")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return runs


@pytest.fixture
def no_yt_dlp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH with ffmpeg but no yt-dlp."""
    bin_dir = tmp_path / "nobin"
    bin_dir.mkdir()
    for tool in ("ffmpeg", "bash", "cat"):
        found = subprocess.run(
            ["which", tool], capture_output=True, text=True, check=True
        ).stdout.strip()
        (bin_dir / tool).symlink_to(found)
    monkeypatch.setenv("PATH", str(bin_dir))


@pytest.fixture
def unstreamable_clip(tmp_path: Path) -> Path:
    """A 1 s MP4 with its index at the end: ffmpeg gets no frame of it
    from a pipe."""
    path = tmp_path / "late.mp4"
    _ = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=30:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "4M",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture
def yt_dlp_downloading(
    tmp_path: Path, unstreamable_clip: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """A yt-dlp on PATH that serves the unstreamable clip to stdout or to
    the --output file; returns the file each run appends its arguments to.
    HOME is tmp_path, so copies go under it."""
    runs = tmp_path / "args.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _script(
        bin_dir / "yt-dlp",
        f"""echo "$*" >> '{runs}'
out=-
while (($#)); do
  if [[ $1 == --output ]]; then out=$2; fi
  shift
done
if [[ $out == - ]]; then cat '{unstreamable_clip}'
else cp '{unstreamable_clip}' "${{out//%(ext)s/mp4}}"; fi""",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("HOME", str(tmp_path))
    return runs


def test_link_that_cannot_stream_plays_from_a_downloaded_copy(
    tmp_path: Path, yt_dlp_downloading: Path
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    downloads = tmp_path / ".cache/gtk-widgets/webcam/downloads"
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: player.latest() is not None), (
            yt_dlp_downloading.read_text() if yt_dlp_downloading.exists() else ""
        )
        assert any(downloads.iterdir())
    finally:
        player.close()
    assert _wait_for(lambda: not any(downloads.iterdir())), list(downloads.rglob("*"))


def test_yt_dlp_never_reads_the_users_config(
    tmp_path: Path, yt_dlp_downloading: Path
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: player.latest() is not None)
    finally:
        player.close()
    _ = links.add_link(LINK, tmp_path / "backgrounds")
    runs = yt_dlp_downloading.read_text().splitlines()
    assert len(runs) >= 3, runs  # stream, copy, the popup's check
    assert all("--ignore-config" in run.split() for run in runs), runs


REFUSED = "ERROR: [Site] x: Unable to download webpage: HTTP Error 403: Forbidden"
NO_CURL_CFFI = (
    'ERROR: Impersonate target "chrome" is not available. Use'
    " --list-impersonate-targets to see available targets. You may be missing"
    " dependencies required to support this target."
)


def _picky_site(as_chrome: str) -> str:
    """A yt-dlp whose site answers 403 unless it runs with --impersonate;
    `as_chrome` is the script run then."""
    return f"""for arg in "$@"; do
  if [[ $arg == --impersonate ]]; then {as_chrome}; exit; fi
done
echo '{REFUSED}' >&2
exit 1"""


@pytest.fixture
def yt_dlp_as_chrome(
    tmp_path: Path, clip: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A yt-dlp that serves the clip (stdout) or its title and no
    thumbnail (--print) only as Chrome."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    serve = f"""if [[ " $* " == *" --print "* ]]; then printf 'A Title\\nNA\\n'
  else cat '{clip}'; fi"""
    _script(bin_dir / "yt-dlp", _picky_site(serve))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")


@pytest.fixture
def yt_dlp_without_curl_cffi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A yt-dlp whose site answers 403 and that cannot be Chrome."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fail = f"echo '{NO_CURL_CFFI}' >&2; exit 1"
    _script(bin_dir / "yt-dlp", _picky_site(fail))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")


@pytest.mark.usefixtures("yt_dlp_as_chrome")
def test_link_refused_by_its_site_plays_as_chrome(tmp_path: Path) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: player.latest() is not None)
    finally:
        player.close()


@pytest.mark.usefixtures("yt_dlp_as_chrome")
def test_adding_a_link_refused_by_its_site_checks_it_as_chrome(
    tmp_path: Path,
) -> None:
    added = links.add_link(LINK, tmp_path / "backgrounds")
    assert isinstance(added, Path), added
    assert added.name == "A Title.url"
    assert added.read_text() == f"{LINK}\n"


@pytest.mark.usefixtures("yt_dlp_without_curl_cffi")
def test_adding_a_refused_link_without_curl_cffi_says_so(tmp_path: Path) -> None:
    added = links.add_link(LINK, tmp_path / "backgrounds")
    assert isinstance(added, links.LinkError)
    assert "python-curl_cffi" in str(added)


@pytest.mark.usefixtures("yt_dlp_without_curl_cffi")
def test_refused_link_without_curl_cffi_says_so_in_the_log(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        said: list[str] = []
        assert _wait_for(
            lambda: (
                said.append(capfd.readouterr().err)
                or "python-curl_cffi" in "".join(said)
            )
        ), said
    finally:
        player.close()


def _runs(log: Path) -> int:
    return len(log.read_text().split()) if log.exists() else 0


def test_short_link_clip_starts_again_when_it_ends(
    tmp_path: Path, yt_dlp_serving: Path
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: _runs(yt_dlp_serving) >= 3), (
            f"a 1 s clip played {_runs(yt_dlp_serving)} times in {WAIT_S} s"
        )
    finally:
        player.close()


def test_upper_case_link_file_plays_as_a_link(
    tmp_path: Path, yt_dlp_serving: Path
) -> None:
    link = tmp_path / "Clip.URL"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        assert _wait_for(lambda: player.latest() is not None)
        assert _runs(yt_dlp_serving) >= 1
    finally:
        player.close()


@pytest.mark.usefixtures("no_yt_dlp")
def test_link_player_keeps_going_without_yt_dlp(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text(f"{LINK}\n")
    player = Animation(str(link))
    try:
        # It says why, and tries again (after LINK_RETRY_S) instead of dying
        said: list[str] = []
        assert _wait_for(
            lambda: (
                said.append(capfd.readouterr().err)
                or "".join(said).count("yt-dlp") >= 2
            )
        ), said
    finally:
        player.close()


@pytest.mark.usefixtures("no_yt_dlp")
def test_adding_a_link_without_yt_dlp_says_so(tmp_path: Path) -> None:
    added = links.add_link(LINK, tmp_path)
    assert isinstance(added, links.LinkError)
    assert "yt-dlp" in str(added)


@pytest.mark.usefixtures("no_yt_dlp")
def test_link_thumbnail_without_yt_dlp_is_none(tmp_path: Path) -> None:
    link = tmp_path / "clip.url"
    _ = link.write_text("https://example.com/no-thumbnail-cached\n")
    assert links.thumbnail(link) is None


def test_adding_a_link_to_a_read_only_folder_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _script(bin_dir / "yt-dlp", "printf 'A Title\\nNA\\n'")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    folder = tmp_path / "backgrounds"
    folder.mkdir()
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        added = links.add_link(LINK, folder)
    finally:
        folder.chmod(stat.S_IRWXU)
    assert isinstance(added, links.LinkError)
    assert not any(folder.iterdir())


def test_clicking_the_chosen_background_again_keeps_it_chosen(
    tmp_path: Path,
) -> None:
    for name in ("a.gif", "b.gif"):
        _ = (tmp_path / name).write_bytes(b"")
    chosen: list[str | None] = [str(tmp_path / "a.gif")]
    gallery = Gallery(
        tmp_path,
        suffixes={".gif"},
        kind="GIFs",
        chosen=lambda: chosen[0],
        choose=lambda path: chosen.__setitem__(0, path),
        show_error=lambda text: print(text, file=sys.stderr),
    )
    buttons = _toggles(gallery.box)
    assert [b.get_active() for b in buttons] == [True, False]
    buttons[0].emit("clicked")
    assert [b.get_active() for b in buttons] == [True, False]
    assert chosen[0] == str(tmp_path / "a.gif")
    buttons[1].emit("clicked")
    assert [b.get_active() for b in buttons] == [False, True]
    assert chosen[0] == str(tmp_path / "b.gif")


def _toggles(widget: Gtk.Widget) -> list[Gtk.ToggleButton]:
    """The grid's tile buttons, in order."""
    found: list[Gtk.ToggleButton] = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.ToggleButton):
            found.append(child)
        else:
            found += _toggles(child)
        child = child.get_next_sibling()
    return found


def test_the_cross_removes_a_background_at_once(tmp_path: Path) -> None:
    for name in ("a.gif", "b.gif"):
        _ = (tmp_path / name).write_bytes(b"")
    chosen: list[str | None] = [str(tmp_path / "a.gif")]
    gallery = Gallery(
        tmp_path,
        suffixes={".gif"},
        kind="GIFs",
        chosen=lambda: chosen[0],
        choose=lambda path: chosen.__setitem__(0, path),
        show_error=lambda text: print(text, file=sys.stderr),
    )
    _crosses(gallery.box)[0].emit("clicked")
    assert not (tmp_path / "a.gif").exists()
    assert chosen[0] is None
    assert [b.get_tooltip_text() for b in _toggles(gallery.box)] == ["b.gif"]


def _crosses(widget: Gtk.Widget) -> list[Gtk.Button]:
    """The tiles' remove buttons, in order."""
    found: list[Gtk.Button] = []
    child = widget.get_first_child()
    while child is not None:
        if type(child) is Gtk.Button and child.get_label() == REMOVE_GLYPH:
            found.append(child)
        else:
            found += _crosses(child)
        child = child.get_next_sibling()
    return found
