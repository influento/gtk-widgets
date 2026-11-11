"""Own the clipboard with several forms of one item (stdlib only).

wl-copy offers one MIME type (plus text aliases for a text type), so a file
can't be offered as a file, a path and image bytes at once. This takes the
selection over the ext-data-control protocol (or wlr-data-control, the same
opcodes), which needs no window and no focus, offers every form, and serves
whichever one an app asks for until another client takes the clipboard.

  serve([(mime, bytes), ...])   returns in the caller once the selection is
                                set; a forked child serves it

The test entry point offers forms by hand:

  python3 selection.py MIME=FILE MIME:=TEXT ...
"""

import os
import struct
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", ".."))

from lib.wayland import Connection, WaylandError, string  # noqa: E402

# ext_data_control_manager_v1 first; zwlr_data_control_manager_v1 has the same
# requests and events at the same opcodes
MANAGERS = ("ext_data_control_manager_v1", "zwlr_data_control_manager_v1")

# What wl-copy offers for text: apps ask for any of these
TEXT_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING", "TEXT")


def _write(fd, data):
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except OSError:
        pass  # the app closed its end early


def _take(forms):
    """Connect and set the selection. Returns (conn, state) once the
    compositor has it."""
    conn = Connection()
    found = conn.globals()
    manager = seat = None
    for want in MANAGERS:
        for name, interface, version in found:
            if interface == want and manager is None:
                manager = conn.bind(name, interface, 1, lambda op, r: None)
    for name, interface, version in found:
        if interface == "wl_seat" and seat is None:
            seat = conn.bind(name, interface, 1, lambda op, r: None)
    if manager is None:
        conn.close()
        raise WaylandError("the compositor has no data-control protocol")
    if seat is None:
        conn.close()
        raise WaylandError("the compositor offers no seat")

    data = dict(forms)
    state = {"done": False}

    def on_source(opcode, r):
        if opcode == 0:  # send(mime_type, fd)
            mime, fd = r.string(), r.fd()
            threading.Thread(target=_write, args=(fd, data.get(mime, b"")), daemon=True).start()
        elif opcode == 1:  # cancelled: another client owns the clipboard now
            state["done"] = True

    def on_device(opcode, r):
        if opcode == 2:  # finished: the device is gone
            state["done"] = True

    source = conn.new_id(on_source)
    conn.send(manager, 0, struct.pack("=I", source))  # create_data_source
    for mime, _ in forms:
        conn.send(source, 0, string(mime))  # offer
    device = conn.new_id(on_device)
    conn.send(manager, 1, struct.pack("=II", device, seat))  # get_data_device
    conn.send(device, 0, struct.pack("=I", source))  # set_selection
    conn.roundtrip()
    return conn, state


def serve(forms, fork=True):
    """Put forms ([(mime, bytes)], in order of preference) on the clipboard.
    With fork, return once it is set and serve from a child process, as
    wl-copy does; without, serve until the clipboard is replaced."""
    conn, state = _take(forms)
    if fork:
        if os.fork():
            conn.sock.detach()  # the child owns the socket now
            return
        os.setsid()
        null = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(null, fd)
        os.close(null)
    try:
        while not state["done"]:
            conn.dispatch()
    except WaylandError:
        pass
    finally:
        conn.close()
    if fork:
        os._exit(0)


def main(args):
    forms = []
    for arg in args:
        if ":=" in arg:
            mime, text = arg.split(":=", 1)
            forms.append((mime, text.encode()))
        else:
            mime, path = arg.split("=", 1)
            with open(path, "rb") as f:
                forms.append((mime, f.read()))
    if not forms:
        sys.exit(__doc__)
    serve(forms)


if __name__ == "__main__":
    main(sys.argv[1:])
