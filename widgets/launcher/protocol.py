"""Wire format between the launcher CLI and the resident instance.

Stdlib only: the CLI side must start in a few ms. A request is one header
line of tab-separated fields, for dmenu followed by the stdin bytes:

  toggle \t <t0>
  dmenu  \t <payload length> \t <prompt> \t <t0> \t <after tab: 1 or 0> \t <action>
         \t <delete: 1 or 0>

t0 (optional, from $LAUNCHER_T0 in ns since the epoch) makes the instance
print how long after it the first frame was drawn. The instance answers a
dmenu request with the chosen line's index, -1 (Esc) or ACTION (the action
button, shown when <action> is not empty), and a newline. With <delete> 1
it first sends "del <index>" and a newline for each row deleted (the row's
cross or Ctrl+d); the CLI runs its --delete command for each.
"""

import os
import shlex
import socket
import sys

ACTION = -2  # dmenu reply: the --action button was pressed
ACTION_STATUS = 10  # the CLI's exit status for it (rofi's first custom key)


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


def run_delete(cmd, line):
    """Run a --delete command (split like a shell would, run without one)
    with the deleted line and a newline on stdin; its stdout goes to stderr,
    so it can't end up in the pick."""
    import subprocess
    try:
        done = subprocess.run(shlex.split(cmd), input=line + b"\n", stdout=sys.stderr,
                              check=False)
    except (OSError, ValueError) as e:
        print(f"launcher: --delete: {e}", file=sys.stderr)
        return
    if done.returncode:
        print(f"launcher: --delete exited {done.returncode}", file=sys.stderr)
