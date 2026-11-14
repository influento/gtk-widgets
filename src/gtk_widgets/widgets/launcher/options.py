"""dmenu row options, and the text helpers their labels use (stdlib, no GTK).

A dmenu input line may carry options after a NUL byte, in rofi's format:

  text \\0 key \\x1f value \\x1f key \\x1f value ...

A key may repeat (preview, one per file). The launcher reads:

  kind     image, gif, files, file, folder, missing, binary or text
  icon     an image file for the row's thumbnail
  preview  a file for the preview pane, one per file
  detail   the row's right-hand column
  count    a count badge on the thumbnail (several files)
  meta     extra search words
  info     the pane's caption source ("image data": the row text names it)
  text     a file with the row's whole text, shown as is in the pane

The line is still printed byte-exact on a pick, options included.
"""

from pathlib import Path
from typing import BinaryIO

PIC_KINDS = frozenset({"image", "gif", "files"})
TIMES = "\u00d7"  # the sign between an image's width and height in a label
GIF_HEADER = 13  # signature, version, logical screen descriptor
IMAGE_DESCRIPTOR = 9

KIB = 1024

type Options = dict[str, list[str]]  # key -> its values, in line order


def human(n: float) -> str:
    """A byte count as it reads: 512 B, 1.5 KiB."""
    for unit in ("B", "KiB", "MiB"):
        if n < KIB:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= KIB
    return f"{n:.1f} GiB"


def short(path: str) -> str:
    """path with the home folder written as ~."""
    home = str(Path.home())
    return (
        "~" + path[len(home) :] if path == home or path.startswith(home + "/") else path
    )


def parent(path: str) -> str:
    """The folder part of a path, as os.path.dirname gives it."""
    head = path[: path.rfind("/") + 1]
    return head.rstrip("/") or head


def name_of(path: str) -> str:
    """The last part of a path, as os.path.basename gives it."""
    return path.rpartition("/")[2]


def split(text: str) -> tuple[str, Options]:
    """'text\\0k\\x1fv...' -> (text, {key: [values]}). Without a NUL: (text, {})."""
    text, sep, rest = text.partition("\0")
    opts: Options = {}
    if sep:
        parts = rest.split("\x1f")
        for key, value in zip(parts[0::2], parts[1::2], strict=False):
            if key:
                opts.setdefault(key, []).append(value)
    return text, opts


def first(opts: Options, key: str, default: str = "") -> str:
    values = opts.get(key)
    return values[0] if values else default


def gif_animated(path: str) -> bool:
    """True when the GIF at path has more than one frame. Reads only up to
    the second image descriptor, so a long recording costs one frame."""
    try:
        with Path(path).open("rb") as f:
            head = f.read(GIF_HEADER)
            if len(head) < GIF_HEADER or head[:3] != b"GIF":
                return False
            if head[10] & 0x80:  # global colour table
                f.seek(3 * (2 << (head[10] & 7)), 1)
            frames = 0
            while True:
                block = f.read(1)
                if not block or block == b"\x3b":  # trailer
                    return False
                if block == b"\x2c":  # image descriptor
                    frames += 1
                    if frames > 1:
                        return True
                    desc = f.read(IMAGE_DESCRIPTOR)
                    if len(desc) < IMAGE_DESCRIPTOR:
                        return False
                    if desc[8] & 0x80:  # local colour table
                        f.seek(3 * (2 << (desc[8] & 7)), 1)
                    f.read(1)  # LZW minimum code size
                elif block == b"\x21":  # extension
                    f.read(1)
                else:
                    return False
                _skip_sub_blocks(f)
    except OSError:
        return False


def _skip_sub_blocks(f: BinaryIO) -> None:
    """Past a block's data sub-blocks, up to its zero-size terminator."""
    while True:
        size = f.read(1)
        if not size or size[0] == 0:
            return
        f.seek(size[0], 1)
