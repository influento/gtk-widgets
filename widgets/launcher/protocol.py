"""Wire format between the launcher CLI and the resident instance.

Stdlib only: the CLI side must start in a few ms. A request is one header
line of tab-separated fields, for dmenu followed by the stdin bytes:

  toggle \t <t0>
  dmenu  \t <payload length> \t <prompt> \t <t0> \t <after tab: 1 or 0>

t0 (optional, from $LAUNCHER_T0 in ns since the epoch) makes the instance
print how long after it the first frame was drawn. The instance answers a
dmenu request with the chosen line's index, or -1, and a newline.
"""

import os
import socket


def socket_path():
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.join(runtime, "gtk-widgets-launcher.sock")


def connect():
    """A socket connected to the running instance, or None."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(socket_path())
    except OSError:
        sock.close()
        return None
    return sock


def header(*fields):
    clean = (str(f).replace("\t", " ").replace("\n", " ") for f in fields)
    return ("\t".join(clean) + "\n").encode("utf-8", "surrogateescape")


def parse_header(line):
    return line.decode("utf-8", "replace").split("\t")


def split_lines(data):
    """stdin bytes -> lines without their newline, exactly as read otherwise."""
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    return lines
