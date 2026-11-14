#!/usr/bin/env python3
"""launcher-clipboard — cliphist's history as dmenu lines with options.

  launcher-clipboard | launcher --dmenu --after-tab ...
  launcher-clipboard --restore ID
  launcher-clipboard --offer ID

Prints one line per `cliphist list` entry, newest first:

  <id> \\t <label> \\0 kind \\x1f <kind> \\x1f icon \\x1f <file> ...

(options.py has the keys). `cliphist decode` reads only the "<id>\\t" in front,
so a pick decodes as before. Kinds:

  image, gif   image data (cliphist's "[[ binary data ... png 1920x1080 ]]", or
               raw bytes it can't name: WebP, AVIF, HEIC, JXL), or a link to an
               image file, or a plain absolute path to one
  files        several file links in one entry (a recording's sheets)
  file, folder one link or plain path to a file or a directory
  missing      a link or path to a file that is gone
  binary       other raw bytes
  text         everything else: the row as cliphist shows it (one line, cut at
               100 characters), the pane the whole text (option text)

Image data and text are decoded once into $XDG_CACHE_HOME/launcher/clipboard/
<id>.<ext> (0700 folder, 0600 files: clipboard text, as private as cliphist's
own database); a file whose entry left the history is deleted on the next run.
Stdlib only: this runs before every clipboard pick.

--restore puts a picked entry back on the clipboard. Image data and file links
go up in several forms at once (selection.py), and each app takes the one it
reads: image data as its bytes + the cached file + that file's path; file links
as the files + their paths (+ the bytes of a single still image, for web
pages). Telegram and Obsidian then paste the image or the animated GIF, a
terminal the path; Claude Code attaches the image and keeps its path. GIF bytes
would paste as a still frame, so GIFs go only as files. The entry moves to the
top of the history (stored again: cliphist drops the older copy and gives it a
new id, and the cached file follows the id), and MARKER tells dotfiles'
cliphist-store not to store the forms as a new entry. Everything else (text,
plain paths, unknown bytes) goes through wl-copy as before.

--offer does the same for a copy cliphist-store has just stored (an image from
Chrome, a capture's file link), so a fresh copy pastes as a path too; it leaves
the entry where it is and any other copy alone (no wl-copy: that would be
stored again and loop).
"""

import contextlib
import os
import re
import subprocess
import sys
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from gtk_widgets.lib.wayland import WaylandError
from gtk_widgets.widgets.launcher import selection
from gtk_widgets.widgets.launcher.options import (
    TIMES,
    Options,
    human,
    name_of,
    parent,
    short,
)
from gtk_widgets.widgets.launcher.selection import Forms

CACHE = str(
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "launcher"
    / "clipboard"
)
BINARY = re.compile(r"^\[\[ binary data (\S+ \S+) (\w+) (\d+)x(\d+) \]\]$")
MARKER = "application/x-launcher-clipboard"
# Formats sent as image bytes as well as a file; GIF is left out on purpose
STILL_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "avif": "image/avif",
    "heic": "image/heic",
    "jxl": "image/jxl",
}
# What wl-copy offers for text: apps ask for any of these
TEXT_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING", "TEXT")
IMAGE_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
    ".heic",
    ".heif",
    ".jxl",
    ".bmp",
    ".tif",
    ".tiff",
    ".svg",
    ".ico",
    ".qoi",
    ".tga",
}
CLIPHIST_TIMEOUT_S = 10

# (kind, label, detail, options) of one entry: options.py has the kinds
type Entry = tuple[str, str, str, Options]
# how --restore puts an entry up: image data of a format, or file links
type RestoreKind = tuple[Literal["image"], str] | tuple[Literal["files"], list[str]]


class Cliphist(Protocol):
    """Runs `cliphist ARGS` with data on stdin; its stdout."""

    def __call__(self, *args: str, data: bytes | None = None) -> bytes: ...


def sniff(raw: bytes) -> str | None:
    """The image format of raw bytes, or None."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if raw[4:8] == b"ftyp" and raw[8:12] in (b"avif", b"avis"):
        return "avif"
    if raw[4:8] == b"ftyp" and raw[8:12] in (b"heic", b"heix", b"mif1", b"msf1"):
        return "heic"
    if raw[:2] == b"\xff\x0a" or raw[:12] == b"\0\0\0\x0cJXL \r\n\x87\n":
        return "jxl"
    for magic, fmt in (
        (b"\x89PNG", "png"),
        (b"\xff\xd8\xff", "jpeg"),
        (b"GIF8", "gif"),
        (b"BM", "bmp"),
    ):
        if raw.startswith(magic):
            return fmt
    return None


def is_image(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXT


class Cache:
    """Decoded entries in CACHE by id; keep() marks what is still listed."""

    def __init__(self, root: str, decode: Callable[[str], bytes]) -> None:
        self.root, self.decode = Path(root), decode
        self.kept: set[str] = set()
        self.root.mkdir(mode=0o700, exist_ok=True, parents=True)
        self.root.chmod(0o700)
        self.files: dict[str, str] = {}  # entry id -> file name
        for entry in self.root.iterdir():
            if not entry.name.endswith(".tmp"):  # a write cut short; prune() drops it
                self.files.setdefault(entry.name.split(".", 1)[0], entry.name)

    def data(self, cid: str, fmt: str | None = None) -> str:
        """The path of entry cid's bytes, decoded on the first call."""
        name = self.files.get(cid)
        if name is None:
            raw = self.decode(cid)
            name = f"{cid}.{fmt or sniff(raw) or 'bin'}"
            tmp = self.root / f"{name}.tmp"
            with os.fdopen(
                os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb"
            ) as f:
                f.write(raw)
            tmp.replace(self.root / name)
            self.files[cid] = name
        self.kept.add(name)
        return str(self.root / name)

    def prune(self) -> None:
        for entry in self.root.iterdir():
            if entry.name not in self.kept:
                with contextlib.suppress(OSError):
                    entry.unlink()


def _expand_home(text: str) -> str:
    """A leading ~ or ~user as the home folder, as os.path.expanduser does."""
    if text == "~" or text.startswith("~/"):
        return (str(Path.home()).rstrip("/") + text[1:]) or "/"
    if not text.startswith("~"):
        return text
    try:
        return str(Path(text).expanduser())
    except RuntimeError:  # no such user
        return text


def from_paths(paths: list[str]) -> Entry:
    """(kind, label, detail, options) for file paths."""
    if len(paths) == 1:
        p = paths[0]
        name = name_of(p.rstrip("/")) or p
        if not Path(p).exists():
            return (
                "missing",
                name,
                f"{short(parent(p))} · missing",
                {"preview": [p]},
            )
        if Path(p).is_dir():
            return (
                "folder",
                name + "/",
                short(parent(p.rstrip("/"))),
                {"preview": [p]},
            )
        if is_image(p):
            kind = "gif" if p.lower().endswith(".gif") else "image"
            return kind, name, short(parent(p)), {"preview": [p], "icon": [p]}
        return "file", name, short(parent(p)), {"preview": [p]}
    opts: Options = {"preview": list(paths), "count": [str(len(paths))]}
    thumb = next((p for p in paths if is_image(p) and Path(p).is_file()), None)
    if thumb:
        opts["icon"] = [thumb]
    label = f"{len(paths)} files: " + ", ".join(name_of(p) for p in paths)
    return "files", label, short(os.path.commonpath(paths)), opts


def uri_paths(text: str) -> list[str]:
    return [
        urllib.parse.unquote(u[len("file://") :])
        for u in re.split(r"[\r\n ]+", text)
        if u.startswith("file://")
    ]


def classify(cid: str, text: str, cache: Cache) -> Entry:
    """(kind, label, detail, options) for one `cliphist list` entry."""
    m = BINARY.match(text)
    if m:
        size, fmt, w, h = m.groups()
        path = cache.data(cid, fmt)
        return (
            ("gif" if fmt == "gif" else "image"),
            f"{fmt.upper()} image · {w}{TIMES}{h}",
            size,
            {
                "preview": [path],
                "icon": [path],
                "info": ["image data"],
                "meta": ["image", fmt],
            },
        )
    if "�" in text or any(ord(c) < 32 and c != "\t" for c in text):
        path = cache.data(cid)  # bytes cliphist couldn't name
        fmt = path.rsplit(".", 1)[-1]
        size = human(Path(path).stat().st_size)
        if fmt == "bin":
            return "binary", f"Binary data · {size}", "", {"meta": ["binary"]}
        return (
            ("gif" if fmt == "gif" else "image"),
            f"{fmt.upper()} image",
            size,
            {
                "preview": [path],
                "icon": [path],
                "info": ["image data"],
                "meta": ["image", fmt],
            },
        )
    if text.startswith("file://"):
        # cliphist cuts its preview at 100 characters with an ellipsis
        full = (
            cache.decode(cid).decode("utf-8", "replace") if text.endswith("…") else text
        )
        paths = uri_paths(full)
        if paths:
            return from_paths(paths)
    plain = _expand_home(text)
    if plain.startswith("/") and not text.endswith("…") and Path(plain).exists():
        return from_paths([plain])
    return "text", text, "", {"text": [cache.data(cid, "txt")]}


def line(cid: str, kind: str, label: str, detail: str, opts: Options) -> str:
    opts = {**opts, "kind": [kind]}
    if detail:
        opts["detail"] = [detail]
    fields = "\x1f".join(
        x for key, values in opts.items() for v in values for x in (key, v)
    )
    label = label.replace("\0", "").replace("\n", " ")
    return f"{cid}\t{label}\0{fields}"


def run(listing: bytes, decode: Callable[[str], bytes], root: str = CACHE) -> list[str]:
    """dmenu lines for `cliphist list` output (bytes); decode(id) -> bytes."""
    cache = Cache(root, decode)
    out: list[str] = []
    for raw in listing.split(b"\n"):
        raw_id, tab, raw_text = raw.partition(b"\t")
        if not tab:
            continue
        cid, text = raw_id.decode(), raw_text.decode("utf-8", "replace")
        try:
            out.append(line(cid, *classify(cid, text, cache)))
        except OSError, ValueError, subprocess.SubprocessError:
            out.append(f"{cid}\t{text}")  # as cliphist shows it
    cache.prune()
    return out


def restore_kind(text: str, raw: bytes) -> RestoreKind | None:
    """("image", fmt), ("files", [paths]) or None (wl-copy as is) for an entry
    whose `cliphist list` text is text and whose bytes are raw."""
    m = BINARY.match(text)
    fmt = m.group(2) if m else sniff(raw)
    if fmt:
        return "image", fmt
    if text.startswith("file://"):
        paths = uri_paths(raw.decode("utf-8", "replace"))
        if paths:
            return "files", paths
    return None


def _text_forms(text: str) -> Forms:
    return [(t, text.encode()) for t in TEXT_TYPES]


def image_forms(raw: bytes, fmt: str, path: str) -> Forms:
    """Image data: its bytes (still formats only), the cached file, the
    file's path."""
    forms: Forms = [(STILL_MIME[fmt], raw)] if fmt in STILL_MIME else []
    return [
        *forms,
        ("text/uri-list", Path(path).as_uri().encode()),
        *_text_forms(path),
        (MARKER, b""),
    ]


def file_forms(raw: bytes, paths: list[str]) -> Forms:
    """File links: the files as they were copied, their paths one per line,
    and a single still image's bytes too."""
    forms: Forms = [("text/uri-list", raw)]
    if len(paths) == 1:
        ext = Path(paths[0]).suffix.lower().lstrip(".")
        if ext in STILL_MIME and Path(paths[0]).is_file():
            forms.append((STILL_MIME[ext], Path(paths[0]).read_bytes()))
    return forms + _text_forms("\n".join(paths)) + [(MARKER, b"")]


def restore(
    cid: str,
    cliphist: Cliphist,
    serve: Callable[[Forms], None],
    wl_copy: Callable[[bytes], None],
    root: str = CACHE,
    *,
    offer: bool = False,
) -> None:
    """Put entry cid back on the clipboard (see the module notes). With
    offer (a copy cliphist-store has just stored), only image data and file
    links go up, without moving the entry: anything else is left as the app
    offered it."""
    text = next(
        (
            t
            for i, _, t in (ln.partition(b"\t") for ln in cliphist("list").split(b"\n"))
            if i.decode() == cid
        ),
        b"",
    ).decode("utf-8", "replace")
    raw = cliphist("decode", data=f"{cid}\t\n".encode())
    kind = restore_kind(text, raw)
    if kind is None:
        if not offer:
            wl_copy(raw)
        return
    top = cid
    if not offer:
        cliphist("store", data=raw)  # to the top, under a new id
        # The newest entry with the pick's text: a copy can land on top
        # meanwhile (no store, no match: cid is still the pick)
        top = next(
            (
                i.decode()
                for i, _, t in (
                    ln.partition(b"\t") for ln in cliphist("list").split(b"\n")
                )
                if t.decode("utf-8", "replace") == text
            ),
            cid,
        )
    match kind:
        case "image", fmt:
            path = Cache(root, lambda _: raw).data(cid, fmt)
            if top != cid:
                path = str(Path(path).replace(Path(root) / f"{top}.{fmt}"))
            forms = image_forms(raw, fmt, path)
        case "files", paths:
            forms = file_forms(raw, paths)
    try:
        serve(forms)
    except OSError:
        if not offer:
            wl_copy(raw)


def _main() -> None:
    def cliphist(*args: str, data: bytes | None = None) -> bytes:
        return subprocess.run(
            ["cliphist", *args],
            input=data,
            capture_output=True,
            timeout=CLIPHIST_TIMEOUT_S,
            check=False,
        ).stdout

    if sys.argv[1:2] in (["--restore"], ["--offer"]) and len(sys.argv) == 3:

        def wl_copy(raw: bytes) -> None:
            subprocess.run(["wl-copy"], input=raw, check=False)

        def serve(forms: Forms) -> None:
            try:
                selection.serve(forms)
            except WaylandError as e:
                raise OSError(str(e)) from None

        try:
            restore(
                sys.argv[2], cliphist, serve, wl_copy, offer=sys.argv[1] == "--offer"
            )
        except (OSError, subprocess.SubprocessError) as e:
            sys.exit(f"launcher-clipboard: {e}")
        return
    try:
        listing = cliphist("list")
    except (OSError, subprocess.SubprocessError) as e:
        sys.exit(f"launcher-clipboard: {e}")
    for out in run(listing, lambda cid: cliphist("decode", data=f"{cid}\t\n".encode())):
        sys.stdout.write(out + "\n")


def main() -> int | None:
    try:
        _main()
    except BrokenPipeError:
        return 1
    return None
