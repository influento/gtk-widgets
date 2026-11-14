"""Tests for the launcher's clipboard server (widgets/launcher/selection.py).

The real CLI (`python3 selection.py MIME=FILE`) runs as a subprocess and
forks its serving child, as launcher-clipboard does. The test plays the
compositor on a unix socket in a temp dir (WAYLAND_DISPLAY is its absolute
path) and answers only what selection.py asks: the registry with the
data-control manager and a seat, sync, and later the source's send (also
an unparsable one) and cancelled events. Every wait is bounded and only fails the test.

  uv run pytest -c pytest.toml tests/launcher_selection_test.py
"""

import fcntl
import os
import select
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from gtk_widgets.lib.wayland import Reader, string
from gtk_widgets.widgets.launcher import selection

TIMEOUT = 5  # seconds for any one wait
MIB = 1 << 20
HEADER = 8  # bytes of a Wayland message header: object id, size << 16 | opcode
SIZE_SHIFT = 16
OPCODE_MASK = 0xFFFF
DISPLAY = 1  # wl_display's object id
SYNCS_AFTER_SELECTION = 2


def wait_readable(fd: int | socket.socket, deadline: float, what: str) -> None:
    left = deadline - time.monotonic()
    if left <= 0 or not select.select([fd], [], [], left)[0]:
        msg = f"timed out waiting for {what}"
        raise AssertionError(msg)


def header(oid: int, size: int, opcode: int) -> bytes:
    return struct.pack("=II", oid, size << SIZE_SHIFT | opcode)


class FakeCompositor:
    """One client connection, ext-data-control only."""

    MANAGER, SEAT = 1, 2  # global names

    def __init__(self, path: str) -> None:
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen(1)
        self.conn: socket.socket | None = None
        self.buf = b""
        self.bound: dict[int, int] = {}  # global name -> client object id
        self.registry: int | None = None
        self.source: int | None = None
        self.device: int | None = None
        self.selected: int | None = None
        self.syncs = 0
        # (mime, fd): sent with the done after set_selection
        self.send_with_done: tuple[str, int] | None = None

    def client(self) -> socket.socket:
        if self.conn is None:
            msg = "no client has connected"
            raise AssertionError(msg)
        return self.conn

    def source_id(self) -> int:
        if self.source is None:
            msg = "the client made no data source"
            raise AssertionError(msg)
        return self.source

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
        self.listener.close()

    def event(
        self, oid: int, opcode: int, args: bytes = b"", fds: list[int] | None = None
    ) -> None:
        msg = header(oid, HEADER + len(args), opcode) + args
        _ = socket.send_fds(self.client(), [msg], fds or [])

    def _request(self, oid: int, opcode: int, r: Reader) -> None:
        if oid == DISPLAY and opcode == 0:  # wl_display.sync(callback)
            done = header(r.uint(), 12, 0) + struct.pack("=I", 0)
            if self.selected is not None and self.send_with_done:
                # done and a paste request in one read, as a fast reader can make it
                (mime, fd), self.send_with_done = self.send_with_done, None
                args = string(mime)
                send = header(self.source_id(), HEADER + len(args), 0) + args
                _ = socket.send_fds(self.client(), [done + send], [fd])
            else:
                self.client().sendall(done)
            self.syncs += 1
        elif oid == DISPLAY and opcode == 1:  # wl_display.get_registry(registry)
            self.registry = r.uint()
            for name, interface in (
                (self.MANAGER, "ext_data_control_manager_v1"),
                (self.SEAT, "wl_seat"),
            ):
                self.event(
                    self.registry,
                    0,
                    struct.pack("=I", name) + string(interface) + struct.pack("=I", 1),
                )
        elif oid == self.registry and opcode == 0:  # bind(name, interface, version, id)
            name = r.uint()
            _ = r.string()
            _ = r.uint()
            self.bound[name] = r.uint()
        elif oid == self.bound.get(self.MANAGER):
            if opcode == 0:  # create_data_source(id)
                self.source = r.uint()
            elif opcode == 1:  # get_data_device(id, seat)
                self.device = r.uint()
        elif (
            oid == self.device and self.device is not None and opcode == 0
        ):  # set_selection
            self.selected = r.uint()

    def _read(self, deadline: float) -> bool:
        """Handle what the client sent; False at EOF."""
        conn = self.client()
        wait_readable(conn, deadline, "the client")
        chunk = conn.recv(65536)
        self.buf += chunk
        while len(self.buf) >= HEADER:
            oid, word = struct.unpack_from("=II", self.buf)
            size = word >> SIZE_SHIFT
            if len(self.buf) < size:
                break
            body, self.buf = self.buf[HEADER:size], self.buf[size:]
            self._request(oid, word & OPCODE_MASK, Reader(body, []))
        return bool(chunk)

    def take_selection(self) -> None:
        """Accept the client and answer it until its selection is set and
        the roundtrip after it is done."""
        deadline = time.monotonic() + TIMEOUT
        wait_readable(self.listener, deadline, "the client to connect")
        self.conn, _ = self.listener.accept()
        while not (
            self.source is not None
            and self.selected == self.source
            and self.syncs >= SYNCS_AFTER_SELECTION
        ):
            if not self._read(deadline):
                msg = "the client closed before setting the selection"
                raise AssertionError(msg)

    def wait_eof(self) -> None:
        """Until the client closes its connection (it let go of the clipboard)."""
        deadline = time.monotonic() + TIMEOUT
        while self._read(deadline):
            pass

    def cancel(self) -> None:
        self.event(self.source_id(), 1)  # cancelled


def drain(fd: int) -> bytes:
    """Read fd to EOF (bounded)."""
    deadline = time.monotonic() + TIMEOUT
    out = bytearray()
    while True:
        wait_readable(fd, deadline, "the pasted data")
        chunk = os.read(fd, 65536)
        if not chunk:
            return bytes(out)
        out += chunk


class Serve:
    """The fake compositor in a temp dir, and the pipe ends the test keeps."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.compositor = FakeCompositor(str(tmp / "wayland"))
        self.fds: list[int] = []

    def close(self) -> None:
        # EOF on its socket ends a serving child a failed test leaves behind
        self.compositor.close()
        for fd in self.fds:
            os.close(fd)

    def offer(self, mime: str, data: bytes) -> None:
        """Run the CLI with one form; returns once its child serves it."""
        path = self.tmp / "form"
        _ = path.write_bytes(data)
        env = dict(os.environ, WAYLAND_DISPLAY=self.compositor.listener.getsockname())
        cli = subprocess.Popen(
            [sys.executable, "-m", selection.__name__, f"{mime}={path}"], env=env
        )
        self.compositor.take_selection()
        assert cli.wait(TIMEOUT) == 0

    def pipe(self, flags: int = 0) -> tuple[int, int]:
        r, w = os.pipe2(flags | os.O_CLOEXEC)
        self.fds.append(r)
        return r, w

    def paste(self, mime: str, w: int) -> None:
        """The compositor's send(mime, fd); the test keeps no write end."""
        self.compositor.event(self.compositor.source_id(), 0, string(mime), [w])
        os.close(w)


@pytest.fixture
def serve() -> Iterator[Serve]:
    # A socket path has a 108-byte limit: a short temp dir, not tmp_path
    with tempfile.TemporaryDirectory() as tmp:
        s = Serve(Path(tmp))
        try:
            yield s
        finally:
            s.close()


def test_paste_in_progress_completes_after_clipboard_changes(serve: Serve) -> None:
    data = os.urandom(MIB)
    serve.offer("image/png", data)
    r, w = serve.pipe()
    serve.paste("image/png", w)
    serve.compositor.cancel()
    serve.compositor.wait_eof()  # let go of the clipboard before the paste ends
    got = drain(r)
    assert len(got) == len(data)
    assert got == data


def test_paste_into_a_non_blocking_pipe_gets_the_whole_form(serve: Serve) -> None:
    # an app may make its pipe O_NONBLOCK (both ends); the flag comes with the fd
    data = os.urandom(MIB)
    serve.offer("image/png", data)
    r, w = serve.pipe(os.O_NONBLOCK)
    serve.paste("image/png", w)
    # until the writer gave up (POLLHUP) or blocks on a full pipe
    size = fcntl.fcntl(r, fcntl.F_GETPIPE_SZ)
    poll = select.poll()
    poll.register(r, select.POLLHUP)
    deadline = time.monotonic() + TIMEOUT
    while not poll.poll(0):
        queued: int = struct.unpack("=i", fcntl.ioctl(r, termios.FIONREAD, b"\0" * 4))[
            0
        ]
        if queued >= size:
            break
        if time.monotonic() > deadline:
            msg = "timed out waiting for the writer"
            raise AssertionError(msg)
        time.sleep(0.01)
    got = drain(r)
    assert len(got) == len(data)
    assert got == data
    serve.compositor.cancel()
    serve.compositor.wait_eof()


def test_paste_requested_before_the_fork_is_served_by_the_child(serve: Serve) -> None:
    data = os.urandom(MIB)
    r, w = serve.pipe()
    serve.compositor.send_with_done = ("image/png", w)
    serve.offer("image/png", data)
    os.close(w)
    got = drain(r)  # also fails while a process holds w without writing
    assert len(got) == len(data)
    assert got == data
    serve.compositor.cancel()
    serve.compositor.wait_eof()


def test_error_in_the_child_still_finishes_pastes_under_way(serve: Serve) -> None:
    data = os.urandom(MIB)
    serve.offer("image/png", data)
    r, w = serve.pipe()
    # a paste request and, in the same read, a send with no arguments
    # (unparsable); in separate reads the drain would race the exit
    source, args = serve.compositor.source_id(), string("image/png")
    _ = socket.send_fds(
        serve.compositor.client(),
        [header(source, HEADER + len(args), 0) + args + header(source, HEADER, 0)],
        [w],
    )
    os.close(w)
    serve.compositor.wait_eof()
    got = drain(r)
    assert len(got) == len(data)
    assert got == data
