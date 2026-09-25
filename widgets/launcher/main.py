#!/usr/bin/env python3
"""launcher — app launcher (drun) and dmenu picker.

  launcher                          show the app launcher, or hide it
  launcher --daemon                 start the resident instance hidden (autostart)
  launcher --dmenu [--prompt TEXT] [--after-tab]
                                    pick a stdin line: print it as read, or
                                    print nothing and exit 1 on Esc;
                                    --after-tab shows and searches only what
                                    follows a line's first tab (cliphist ids)

One resident Gtk.Application (dev.dotfiles.launcher) builds the window once
and shows/hides it. This entry point stays stdlib-only until it has to become
that instance, because importing gi alone takes ~60 ms: a toggle or a dmenu
request goes to the running instance over a Unix socket (protocol.py). With
no instance running, a toggle starts one and shows it, and a dmenu request
runs as a one-shot process of its own.
"""

import os
import sys

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _DIR)

import protocol  # noqa: E402

USAGE = "usage: launcher [--daemon | --dmenu [--prompt TEXT] [--after-tab]]"
_PRELOAD = "libgtk4-layer-shell.so.0"


def parse_args(argv):
    """-> (mode, prompt, after_tab); mode is toggle, daemon or dmenu."""
    mode, prompt, after_tab = "toggle", "", False
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--daemon" and mode == "toggle":
            mode = "daemon"
        elif arg == "--dmenu" and mode == "toggle":
            mode = "dmenu"
        elif arg in ("--prompt", "-p") and args:
            prompt = args.pop(0)
        elif arg.startswith("--prompt="):
            prompt = arg.split("=", 1)[1]
        elif arg == "--after-tab":
            after_tab = True
        elif arg in ("-h", "--help"):
            print(__doc__.strip())
            sys.exit(0)
        else:
            sys.exit(USAGE)
    if (prompt or after_tab) and mode != "dmenu":
        sys.exit(USAGE)
    return mode, prompt, after_tab


def _recv_line(sock):
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(64)
        if not chunk:
            return None
        buf += chunk
    return buf


def client(mode, prompt, after_tab):
    """Hand the request to the running instance. Returns the exit status, or
    None when no instance is listening."""
    sock = protocol.connect()
    if sock is None:
        return None
    t0 = os.environ.get("LAUNCHER_T0", "")
    with sock:
        if mode == "daemon":
            return 0  # already running
        if mode == "toggle":
            sock.sendall(protocol.header("toggle", t0))
            return 0
        data = sys.stdin.buffer.read()
        lines = protocol.split_lines(data)
        try:
            sock.sendall(protocol.header("dmenu", len(data), prompt, t0, int(after_tab)) + data)
            reply = _recv_line(sock)
        except OSError as e:
            reply = None
            print(f"launcher: {e}", file=sys.stderr)
    if reply is None:
        print("launcher: the running instance went away", file=sys.stderr)
        return 1
    try:
        index = int(reply)
    except ValueError:
        return 1
    if not 0 <= index < len(lines):
        return 1
    sys.stdout.buffer.write(lines[index] + b"\n")
    sys.stdout.flush()
    return 0


def detach():
    """Continue as the resident instance in a forked child with a session of
    its own: the caller (a terminal, sway's exec) returns at once, and the
    apps launched later outlive a Ctrl+C or a closed terminal there."""
    if os.fork():
        os._exit(0)
    os.setsid()


def main():
    mode, prompt, after_tab = parse_args(sys.argv[1:])
    try:
        status = client(mode, prompt, after_tab)
    except KeyboardInterrupt:
        return 130
    if status is not None:
        return status
    if mode != "dmenu" and os.getsid(0) != os.getpid():
        detach()
    # gtk4-layer-shell must be loaded before libwayland-client: preload it and
    # start over (apps.child_environment() keeps it out of launched apps)
    preload = os.environ.get("LD_PRELOAD", "")
    if _PRELOAD not in preload:
        os.environ["LD_PRELOAD"] = f"{preload}:{_PRELOAD}" if preload else _PRELOAD
        os.execv(sys.executable, [sys.executable] + sys.argv)
    import app
    if mode == "dmenu":
        return app.run_dmenu_once(prompt, after_tab)
    return app.run_resident(hidden=mode == "daemon")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(1)
    except OSError as e:
        sys.exit(f"launcher: {e}")
