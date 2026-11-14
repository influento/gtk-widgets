#!/usr/bin/env python3
"""launcher — app launcher (drun) and dmenu picker.

  launcher                          show the app launcher, or hide it
  launcher --daemon                 start the resident instance hidden (autostart)
  launcher --dmenu [--prompt TEXT] [--after-tab] [--action LABEL] [--delete CMD]
                                    pick a stdin line: print it as read, or
                                    print nothing and exit 1 on Esc;
                                    --after-tab shows and searches only what
                                    follows a line's first tab (cliphist ids);
                                    --action adds a LABEL button that prints
                                    nothing and exits 10; --delete gives rows
                                    a cross (and Ctrl+d) that drops the row and
                                    runs CMD with its line on stdin

One resident Gtk.Application (dev.dotfiles.launcher) builds the window once
and shows/hides it. This entry point stays stdlib-only until it has to become
that instance, because importing gi alone takes ~60 ms: a toggle or a dmenu
request goes to the running instance over a Unix socket (protocol.py). With
no instance running, a toggle starts one and shows it, and a dmenu request
runs as a one-shot process of its own.
"""

import os
import socket
import sys

from gtk_widgets.widgets.launcher import protocol

USAGE = (
    "usage: launcher [--daemon | --dmenu [--prompt TEXT] [--after-tab] [--action LABEL]"
    " [--delete CMD]]"
)
_PRELOAD = "libgtk4-layer-shell.so.0"


# an option that takes a value (as the next argument, or after "=" when long)
_VALUE_OPTIONS = {
    "--prompt": "prompt",
    "-p": "prompt",
    "--action": "action",
    "--delete": "delete",
}


def parse_args(argv: list[str]) -> tuple[str, str, bool, str, str]:
    """-> (mode, prompt, after_tab, action, delete); mode is toggle, daemon or dmenu."""
    mode, after_tab = "toggle", False
    values = {"prompt": "", "action": "", "delete": ""}
    args = list(argv)
    while args:
        arg = args.pop(0)
        name, eq, inline = arg.partition("=")
        if arg in ("--daemon", "--dmenu") and mode == "toggle":
            mode = arg.removeprefix("--")
        elif arg in _VALUE_OPTIONS and args:
            values[_VALUE_OPTIONS[arg]] = args.pop(0)
        elif eq and name.startswith("--") and name in _VALUE_OPTIONS:
            values[_VALUE_OPTIONS[name]] = inline
        elif arg == "--after-tab":
            after_tab = True
        elif arg in ("-h", "--help"):
            print((__doc__ or "").strip())
            sys.exit(0)
        else:
            sys.exit(USAGE)
    prompt, action, delete = values["prompt"], values["action"], values["delete"]
    if (prompt or after_tab or action or delete) and mode != "dmenu":
        sys.exit(USAGE)
    return mode, prompt, after_tab, action, delete


def _reply(sock: socket.socket, lines: list[bytes], delete: str) -> bytes | None:
    """Read the instance's answer, running --delete for each "del" before it.
    -> the final line, or None when the instance went away."""
    with sock.makefile("rb") as f:
        while True:
            line = f.readline()
            if not line.endswith(b"\n"):
                return None
            if not line.startswith(b"del "):
                return line
            try:
                index = int(line[4:])
            except ValueError:
                continue
            if delete and 0 <= index < len(lines):
                protocol.run_delete(delete, lines[index])


def client(
    mode: str, prompt: str, *, after_tab: bool, action: str, delete: str
) -> int | None:
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
            sock.sendall(
                protocol.header(
                    "dmenu",
                    len(data),
                    prompt,
                    t0,
                    int(after_tab),
                    action,
                    int(bool(delete)),
                )
                + data
            )
            reply = _reply(sock, lines, delete)
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
    if index == protocol.ACTION and action:
        return protocol.ACTION_STATUS
    if not 0 <= index < len(lines):
        return 1
    sys.stdout.buffer.write(lines[index] + b"\n")
    sys.stdout.flush()
    return 0


def detach() -> None:
    """Continue as the resident instance in a forked child with a session of
    its own: the caller (a terminal, sway's exec) returns at once, and the
    apps launched later outlive a Ctrl+C or a closed terminal there."""
    if os.fork():
        os._exit(0)
    os.setsid()


def _main() -> int:
    mode, prompt, after_tab, action, delete = parse_args(sys.argv[1:])
    try:
        status = client(mode, prompt, after_tab=after_tab, action=action, delete=delete)
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
        os.execv(sys.executable, [sys.executable, *sys.argv])
    from gtk_widgets.widgets.launcher.ui import app

    if mode == "dmenu":
        return app.run_dmenu_once(
            prompt, after_tab=after_tab, action=action, delete=delete
        )
    return app.run_resident(hidden=mode == "daemon")


def main() -> int | str | None:
    try:
        return _main()
    except BrokenPipeError:
        return 1
    except OSError as e:
        return f"launcher: {e}"
