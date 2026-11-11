#!/usr/bin/env python3
"""launcher-clipboard — cliphist's history as dmenu lines with options.

  launcher-clipboard | launcher --dmenu --after-tab ...

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
"""

import os
import re
import subprocess
import sys
import urllib.parse

CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                     "launcher", "clipboard")
BINARY = re.compile(r"^\[\[ binary data (\S+ \S+) (\w+) (\d+)x(\d+) \]\]$")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".heic", ".heif", ".jxl",
             ".bmp", ".tif", ".tiff", ".svg", ".ico", ".qoi", ".tga"}


def human(n):
    for unit in ("B", "KiB", "MiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GiB"


def short(path):
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def sniff(raw):
    """The image format of raw bytes, or None."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    if raw[4:8] == b"ftyp" and raw[8:12] in (b"avif", b"avis"):
        return "avif"
    if raw[4:8] == b"ftyp" and raw[8:12] in (b"heic", b"heix", b"mif1", b"msf1"):
        return "heic"
    if raw[:2] == b"\xff\x0a" or raw[:12] == b"\0\0\0\x0cJXL \r\n\x87\n":
        return "jxl"
    for magic, fmt in ((b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpeg"), (b"GIF8", "gif"),
                       (b"BM", "bmp")):
        if raw.startswith(magic):
            return fmt
    return None


def is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXT


class Cache:
    """Decoded entries in CACHE by id; keep() marks what is still listed."""

    def __init__(self, root, decode):
        self.root, self.decode = root, decode
        self.kept = set()
        os.makedirs(root, mode=0o700, exist_ok=True)
        os.chmod(root, 0o700)
        self.files = {}
        for name in os.listdir(root):
            if not name.endswith(".tmp"):  # a write cut short; prune() drops it
                self.files.setdefault(name.split(".", 1)[0], name)

    def data(self, cid, fmt=None):
        """The path of entry cid's bytes, decoded on the first call."""
        name = self.files.get(cid)
        if name is None:
            raw = self.decode(cid)
            name = f"{cid}.{fmt or sniff(raw) or 'bin'}"
            tmp = os.path.join(self.root, name + ".tmp")
            with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
                f.write(raw)
            os.replace(tmp, os.path.join(self.root, name))
            self.files[cid] = name
        self.kept.add(name)
        return os.path.join(self.root, name)

    def prune(self):
        for name in os.listdir(self.root):
            if name not in self.kept:
                try:
                    os.remove(os.path.join(self.root, name))
                except OSError:
                    pass


def from_paths(paths):
    """(kind, label, detail, options) for file paths."""
    if len(paths) == 1:
        p = paths[0]
        name = os.path.basename(p.rstrip("/")) or p
        if not os.path.exists(p):
            return "missing", name, f"{short(os.path.dirname(p))} · missing", {"preview": [p]}
        if os.path.isdir(p):
            return "folder", name + "/", short(os.path.dirname(p.rstrip("/"))), {"preview": [p]}
        if is_image(p):
            kind = "gif" if p.lower().endswith(".gif") else "image"
            return kind, name, short(os.path.dirname(p)), {"preview": [p], "icon": [p]}
        return "file", name, short(os.path.dirname(p)), {"preview": [p]}
    opts = {"preview": list(paths), "count": [str(len(paths))]}
    thumb = next((p for p in paths if is_image(p) and os.path.isfile(p)), None)
    if thumb:
        opts["icon"] = [thumb]
    label = f"{len(paths)} files: " + ", ".join(os.path.basename(p) for p in paths)
    return "files", label, short(os.path.commonpath(paths)), opts


def uri_paths(text):
    return [urllib.parse.unquote(u[len("file://"):]) for u in re.split(r"[\r\n ]+", text)
            if u.startswith("file://")]


def classify(cid, text, cache):
    """(kind, label, detail, options) for one `cliphist list` entry."""
    m = BINARY.match(text)
    if m:
        size, fmt, w, h = m.groups()
        path = cache.data(cid, fmt)
        return ("gif" if fmt == "gif" else "image"), f"{fmt.upper()} image · {w}×{h}", size, {
            "preview": [path], "icon": [path], "info": ["image data"], "meta": ["image", fmt]}
    if "�" in text or any(ord(c) < 32 and c != "\t" for c in text):
        path = cache.data(cid)  # bytes cliphist couldn't name
        fmt = path.rsplit(".", 1)[-1]
        size = human(os.path.getsize(path))
        if fmt == "bin":
            return "binary", f"Binary data · {size}", "", {"meta": ["binary"]}
        return ("gif" if fmt == "gif" else "image"), f"{fmt.upper()} image", size, {
            "preview": [path], "icon": [path], "info": ["image data"], "meta": ["image", fmt]}
    if text.startswith("file://"):
        # cliphist cuts its preview at 100 characters with an ellipsis
        full = cache.decode(cid).decode("utf-8", "replace") if text.endswith("…") else text
        paths = uri_paths(full)
        if paths:
            return from_paths(paths)
    plain = os.path.expanduser(text)
    if plain.startswith("/") and not text.endswith("…") and os.path.exists(plain):
        return from_paths([plain])
    return "text", text, "", {"text": [cache.data(cid, "txt")]}


def line(cid, kind, label, detail, opts):
    opts = dict(opts, kind=[kind])
    if detail:
        opts["detail"] = [detail]
    fields = "\x1f".join(x for key, values in opts.items() for v in values for x in (key, v))
    label = label.replace("\0", "").replace("\n", " ")
    return f"{cid}\t{label}\0{fields}"


def run(listing, decode, root=CACHE):
    """dmenu lines for `cliphist list` output (bytes); decode(id) -> bytes."""
    cache = Cache(root, decode)
    out = []
    for raw in listing.split(b"\n"):
        cid, tab, text = raw.partition(b"\t")
        if not tab:
            continue
        cid, text = cid.decode(), text.decode("utf-8", "replace")
        try:
            out.append(line(cid, *classify(cid, text, cache)))
        except (OSError, ValueError, subprocess.SubprocessError):
            out.append(f"{cid}\t{text}")  # as cliphist shows it
    cache.prune()
    return out


def main():
    def cliphist(*args, data=None):
        return subprocess.run(["cliphist", *args], input=data, capture_output=True,
                              timeout=10).stdout

    try:
        listing = cliphist("list")
    except (OSError, subprocess.SubprocessError) as e:
        sys.exit(f"launcher-clipboard: {e}")
    for out in run(listing, lambda cid: cliphist("decode", data=f"{cid}\t\n".encode())):
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
