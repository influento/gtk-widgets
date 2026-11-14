"""A minimal Wayland client over the wire protocol (stdlib only).

No libwayland, no GTK: it talks straight to the compositor socket, so a CLI
that uses it starts in a few ms (capture's screencopy grab, the launcher's
clipboard restore).

Messages are native-endian 32-bit words: object id, then size << 16 | opcode,
then the arguments (strings and arrays are length-prefixed and padded to 4
bytes); file descriptors travel beside them as SCM_RIGHTS.
"""

import builtins
import os
import socket
import struct
from collections.abc import Callable, Iterable
from pathlib import Path


class WaylandError(Exception):
    pass


def pad(n: int) -> int:
    return (n + 3) & ~3


def string(s: str) -> bytes:
    raw = s.encode() + b"\0"
    return struct.pack("=I", len(raw)) + raw.ljust(pad(len(raw)), b"\0")


class Reader:
    """The arguments of one event, read in order. fd() takes the next file
    descriptor that came with the events. Its int() hides the builtin in the
    class body, hence builtins.int there."""

    def __init__(self, body: bytes, fds: list[builtins.int]) -> None:
        self.body = body
        self.pos = 0
        self.fds = fds

    def uint(self) -> builtins.int:
        v: builtins.int
        (v,) = struct.unpack_from("=I", self.body, self.pos)
        self.pos += 4
        return v

    def int(self) -> builtins.int:
        v: builtins.int
        (v,) = struct.unpack_from("=i", self.body, self.pos)
        self.pos += 4
        return v

    def string(self) -> str:
        n = self.uint()
        raw = self.body[self.pos : self.pos + n]
        self.pos += pad(n)
        return raw.rstrip(b"\0").decode(errors="replace")

    def fd(self) -> builtins.int:
        if not self.fds:
            raise WaylandError("an event names a file descriptor that did not arrive")
        return self.fds.pop(0)


type Handler = Callable[[int, Reader], None]  # (opcode, the event's arguments)


class Connection:
    """The client side of one Wayland connection: object ids and dispatch."""

    DISPLAY = 1

    def __init__(self) -> None:
        display = Path(os.environ.get("WAYLAND_DISPLAY", "wayland-0"))
        if not display.is_absolute():
            runtime = os.environ.get("XDG_RUNTIME_DIR")
            if not runtime:
                raise WaylandError("XDG_RUNTIME_DIR is not set")
            display = Path(runtime) / display
        self.sock = socket.socket(
            socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC
        )
        try:
            self.sock.connect(str(display))
        except OSError as e:
            self.sock.close()
            raise WaylandError(f"cannot connect to Wayland at {display}: {e}") from None
        self.next_id = 2
        self.handlers: dict[int, Handler] = {self.DISPLAY: self._display_event}
        self.buf = b""
        self.fds: list[int] = []  # received, not yet taken by an event
        self.registry: int | None = None

    def close(self) -> None:
        for fd in self.fds:
            os.close(fd)
        self.fds = []
        self.sock.close()

    def new_id(self, handler: Handler) -> int:
        oid = self.next_id
        self.next_id += 1
        self.handlers[oid] = handler
        return oid

    def send(
        self, oid: int, opcode: int, args: bytes = b"", fds: Iterable[int] = ()
    ) -> None:
        msg = struct.pack("=II", oid, (8 + len(args)) << 16 | opcode) + args
        if fds:
            socket.send_fds(self.sock, [msg], list(fds))
        else:
            self.sock.sendall(msg)

    def _display_event(self, opcode: int, r: Reader) -> None:
        if opcode == 0:  # error(object, code, message)
            obj, code, message = r.uint(), r.uint(), r.string()
            raise WaylandError(
                f"Wayland protocol error on object {obj} ({code}): {message}"
            )
        # 1: delete_id; ids are never reused here

    def dispatch(self) -> None:
        """Read once from the socket and handle every complete event."""
        chunk, fds, _flags, _addr = socket.recv_fds(self.sock, 65536, 16)
        if not chunk:
            raise WaylandError("the compositor closed the connection")
        self.fds += fds
        self.buf += chunk
        while len(self.buf) >= 8:
            oid: int
            word: int
            oid, word = struct.unpack_from("=II", self.buf)
            size = word >> 16
            if len(self.buf) < size:
                break
            body, self.buf = self.buf[8:size], self.buf[size:]
            handler = self.handlers.get(oid)
            if handler is not None:
                handler(word & 0xFFFF, Reader(body, self.fds))

    def roundtrip(self) -> None:
        done: list[bool] = []

        def on_done(_opcode: int, _r: Reader) -> None:
            done.append(True)

        cb = self.new_id(on_done)
        self.send(self.DISPLAY, 0, struct.pack("=I", cb))  # wl_display.sync
        while not done:
            self.dispatch()

    def globals(self) -> list[tuple[int, str, int]]:
        """[(name, interface, version)] the compositor announces."""
        found: list[tuple[int, str, int]] = []

        def on_registry(opcode: int, r: Reader) -> None:
            if opcode == 0:  # global(name, interface, version)
                found.append((r.uint(), r.string(), r.uint()))

        self.registry = self.new_id(on_registry)
        self.send(self.DISPLAY, 1, struct.pack("=I", self.registry))  # get_registry
        self.roundtrip()
        return found

    def bind(self, name: int, interface: str, version: int, handler: Handler) -> int:
        if self.registry is None:
            raise RuntimeError("bind() before globals(): no registry yet")
        oid = self.new_id(handler)
        self.send(
            self.registry,
            0,
            struct.pack("=I", name)
            + string(interface)
            + struct.pack("=II", version, oid),
        )
        return oid
