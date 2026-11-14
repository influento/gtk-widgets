#!/usr/bin/env python3
"""Tests for the launcher's clipboard server (widgets/launcher/selection.py).

The real CLI (`python3 selection.py MIME=FILE`) runs as a subprocess and
forks its serving child, as launcher-clipboard does. The test plays the
compositor on a unix socket in a temp dir (WAYLAND_DISPLAY is its absolute
path) and answers only what selection.py asks: the registry with the
data-control manager and a seat, sync, and later the source's send (also
an unparsable one) and cancelled events. Every wait is bounded and only fails the test.

  python3 tests/launcher_selection_test.py
"""

import fcntl
import os
import pathlib
import select
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

from gtk_widgets.lib.wayland import Reader, string
from gtk_widgets.widgets.launcher import selection

TIMEOUT = 5  # seconds for any one wait
MIB = 1 << 20


def wait_readable(fd, deadline, what):
    left = deadline - time.monotonic()
    if left <= 0 or not select.select([fd], [], [], left)[0]:
        raise AssertionError(f"timed out waiting for {what}")


class FakeCompositor:
    """One client connection, ext-data-control only."""

    MANAGER, SEAT = 1, 2  # global names

    def __init__(self, path):
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen(1)
        self.conn = None
        self.buf = b""
        self.bound = {}  # global name -> client object id
        self.registry = self.source = self.device = self.selected = None
        self.syncs = 0
        self.send_with_done = None  # (mime, fd): sent with the done after set_selection

    def close(self):
        if self.conn is not None:
            self.conn.close()
        self.listener.close()

    def event(self, oid, opcode, args=b"", fds=()):
        msg = struct.pack("=II", oid, (8 + len(args)) << 16 | opcode) + args
        socket.send_fds(self.conn, [msg], list(fds))

    def _request(self, oid, opcode, r):
        if oid == 1 and opcode == 0:  # wl_display.sync(callback)
            done = struct.pack("=III", r.uint(), 12 << 16 | 0, 0)
            if self.selected is not None and self.send_with_done:
                # done and a paste request in one read, as a fast reader can make it
                (mime, fd), self.send_with_done = self.send_with_done, None
                args = string(mime)
                send = struct.pack("=II", self.source, (8 + len(args)) << 16 | 0) + args
                socket.send_fds(self.conn, [done + send], [fd])
            else:
                self.conn.sendall(done)
            self.syncs += 1
        elif oid == 1 and opcode == 1:  # wl_display.get_registry(registry)
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
            r.string()
            r.uint()
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

    def _read(self, deadline):
        """Handle what the client sent; False at EOF."""
        wait_readable(self.conn, deadline, "the client")
        chunk = self.conn.recv(65536)
        self.buf += chunk
        while len(self.buf) >= 8:
            oid, word = struct.unpack_from("=II", self.buf)
            size = word >> 16
            if len(self.buf) < size:
                break
            body, self.buf = self.buf[8:size], self.buf[size:]
            self._request(oid, word & 0xFFFF, Reader(body, []))
        return bool(chunk)

    def take_selection(self):
        """Accept the client and answer it until its selection is set and
        the roundtrip after it is done."""
        deadline = time.monotonic() + TIMEOUT
        wait_readable(self.listener, deadline, "the client to connect")
        self.conn, _ = self.listener.accept()
        while not (
            self.source is not None and self.selected == self.source and self.syncs >= 2
        ):
            if not self._read(deadline):
                raise AssertionError("the client closed before setting the selection")

    def wait_eof(self):
        """Until the client closes its connection (it let go of the clipboard)."""
        deadline = time.monotonic() + TIMEOUT
        while self._read(deadline):
            pass


def drain(fd):
    """Read fd to EOF (bounded)."""
    deadline = time.monotonic() + TIMEOUT
    out = bytearray()
    while True:
        wait_readable(fd, deadline, "the pasted data")
        chunk = os.read(fd, 65536)
        if not chunk:
            return bytes(out)
        out += chunk


class Serve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.compositor = FakeCompositor(os.path.join(self.tmp.name, "wayland"))
        self.fds = []

    def tearDown(self):
        # EOF on its socket ends a serving child a failed test leaves behind
        self.compositor.close()
        for fd in self.fds:
            os.close(fd)
        self.tmp.cleanup()

    def offer(self, mime, data):
        """Run the CLI with one form; returns once its child serves it."""
        path = os.path.join(self.tmp.name, "form")
        with pathlib.Path(path).open("wb") as f:
            f.write(data)
        env = dict(os.environ, WAYLAND_DISPLAY=self.compositor.listener.getsockname())
        cli = subprocess.Popen(
            [sys.executable, "-m", selection.__name__, f"{mime}={path}"], env=env
        )
        self.compositor.take_selection()
        self.assertEqual(cli.wait(TIMEOUT), 0)

    def pipe(self, flags=0):
        r, w = os.pipe2(flags | os.O_CLOEXEC)
        self.fds.append(r)
        return r, w

    def paste(self, mime, w):
        """The compositor's send(mime, fd); the test keeps no write end."""
        self.compositor.event(self.compositor.source, 0, string(mime), [w])
        os.close(w)

    def test_paste_in_progress_completes_after_clipboard_changes(self):
        data = os.urandom(MIB)
        self.offer("image/png", data)
        r, w = self.pipe()
        self.paste("image/png", w)
        self.compositor.event(self.compositor.source, 1)  # cancelled
        self.compositor.wait_eof()  # let go of the clipboard before the paste ends
        got = drain(r)
        self.assertEqual(len(got), len(data))
        self.assertEqual(got, data)

    def test_paste_into_a_non_blocking_pipe_gets_the_whole_form(self):
        # an app may make its pipe O_NONBLOCK (both ends); the flag comes with the fd
        data = os.urandom(MIB)
        self.offer("image/png", data)
        r, w = self.pipe(os.O_NONBLOCK)
        self.paste("image/png", w)
        # until the writer gave up (POLLHUP) or blocks on a full pipe
        size = fcntl.fcntl(r, fcntl.F_GETPIPE_SZ)
        poll = select.poll()
        poll.register(r, select.POLLHUP)
        deadline = time.monotonic() + TIMEOUT
        while not poll.poll(0):
            queued = struct.unpack("=i", fcntl.ioctl(r, termios.FIONREAD, b"\0" * 4))[0]
            if queued >= size:
                break
            if time.monotonic() > deadline:
                raise AssertionError("timed out waiting for the writer")
            time.sleep(0.01)
        got = drain(r)
        self.assertEqual(len(got), len(data))
        self.assertEqual(got, data)
        self.compositor.event(self.compositor.source, 1)  # cancelled
        self.compositor.wait_eof()

    def test_paste_requested_before_the_fork_is_served_by_the_child(self):
        data = os.urandom(MIB)
        r, w = self.pipe()
        self.compositor.send_with_done = ("image/png", w)
        self.offer("image/png", data)
        os.close(w)
        got = drain(r)  # also fails while a process holds w without writing
        self.assertEqual(len(got), len(data))
        self.assertEqual(got, data)
        self.compositor.event(self.compositor.source, 1)  # cancelled
        self.compositor.wait_eof()

    def test_error_in_the_child_still_finishes_pastes_under_way(self):
        data = os.urandom(MIB)
        self.offer("image/png", data)
        r, w = self.pipe()
        # a paste request and, in the same read, a send with no arguments
        # (unparsable); in separate reads the drain would race the exit
        source, args = self.compositor.source, string("image/png")
        socket.send_fds(
            self.compositor.conn,
            [
                struct.pack("=II", source, (8 + len(args)) << 16 | 0)
                + args
                + struct.pack("=II", source, 8 << 16 | 0)
            ],
            [w],
        )
        os.close(w)
        self.compositor.wait_eof()
        got = drain(r)
        self.assertEqual(len(got), len(data))
        self.assertEqual(got, data)


if __name__ == "__main__":
    unittest.main()
