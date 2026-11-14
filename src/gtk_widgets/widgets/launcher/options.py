"""dmenu row options (stdlib, no GTK).

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

import pathlib

PIC_KINDS = frozenset({"image", "gif", "files"})


def split(text):
    """'text\\0k\\x1fv...' -> (text, {key: [values]}). Without a NUL: (text, {})."""
    text, sep, rest = text.partition("\0")
    opts = {}
    if sep:
        parts = rest.split("\x1f")
        for key, value in zip(parts[0::2], parts[1::2]):
            if key:
                opts.setdefault(key, []).append(value)
    return text, opts


def first(opts, key, default=""):
    values = opts.get(key)
    return values[0] if values else default


def gif_animated(path):
    """True when the GIF at path has more than one frame. Reads only up to
    the second image descriptor, so a long recording costs one frame."""
    try:
        with pathlib.Path(path).open("rb") as f:
            head = f.read(13)
            if len(head) < 13 or head[:3] != b"GIF":
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
                    desc = f.read(9)
                    if len(desc) < 9:
                        return False
                    if desc[8] & 0x80:  # local colour table
                        f.seek(3 * (2 << (desc[8] & 7)), 1)
                    f.read(1)  # LZW minimum code size
                elif block == b"\x21":  # extension
                    f.read(1)
                else:
                    return False
                while True:  # data sub-blocks
                    size = f.read(1)
                    if not size or size[0] == 0:
                        break
                    f.seek(size[0], 1)
    except OSError:
        return False
