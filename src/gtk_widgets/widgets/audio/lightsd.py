"""audio-lights: keep the QuadCast S lights at the settings file's effect.

Sends a frame every 55 ms over libusb (ctypes, stdlib) as HID SET_REPORT
control transfers to the lights interface, which no kernel driver binds, so
the mic's audio and mute button are untouched. Follows the settings file by
its mtime; while the mic is unplugged (or taken by another program) it tries
again every few seconds. Run by the user unit that lights.py writes.

Voice level reads the sound server: a thread polls its sources for the
mic, and a peak meter on it (the popup's Meters) gives the level.
"""

import ctypes
import math
import signal
import sys
import threading
import time
from collections.abc import Callable
from functools import partial

from gi.repository import GLib

from gtk_widgets.lib import pulsectl
from gtk_widgets.lib.pulsectl import _pulsectl as c
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.widgets.audio.lights import (
    PACKET_SIZE,
    PRODUCT,
    SETTINGS_FILE,
    VENDOR,
    Status,
    colour_packet,
    header_packet,
    load,
    parts_at,
)
from gtk_widgets.widgets.audio.meters import Meters

LIBUSB = "libusb-1.0.so.0"
INTERFACE = 0
FRAME_MS = 55
RETRY_S = 3.0
SETTINGS_CHECK_S = 0.25
TIMEOUT_MS = 1000
# HID class request SET_REPORT (host to interface), feature report 0
SET_REPORT_TYPE, SET_REPORT, FEATURE_REPORT_0 = 0x21, 0x09, 0x0300
STATUS_POLL_S = 0.5
PULSE_EFFECTS = ("voice",)
# The mic's audio side, as the sound server names it
MIC_VENDOR, MIC_PRODUCT = "0x0951", "0x171d"
LEVEL_SILENT_DB, LEVEL_LOUD_DB = -50.0, -10.0  # voice: 0 and full brightness
LEVEL_RELEASE = 0.85  # voice level kept per frame after a peak
METER_KEY = "mic"


class Usb:
    """The few libusb calls the lights take, typed."""

    def __init__(self, lib: ctypes.CDLL) -> None:
        self._lib = lib
        lib.libusb_init.argtypes = [ctypes.c_void_p]
        lib.libusb_exit.argtypes = [ctypes.c_void_p]
        lib.libusb_strerror.argtypes = [ctypes.c_int]
        lib.libusb_strerror.restype = ctypes.c_char_p
        lib.libusb_open_device_with_vid_pid.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint16,
            ctypes.c_uint16,
        ]
        lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        for name in (
            "libusb_set_auto_detach_kernel_driver",
            "libusb_claim_interface",
            "libusb_release_interface",
        ):
            getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.libusb_close.argtypes = [ctypes.c_void_p]
        lib.libusb_control_transfer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint8,
            ctypes.c_uint8,
            ctypes.c_uint16,
            ctypes.c_uint16,
            ctypes.c_char_p,
            ctypes.c_uint16,
            ctypes.c_uint,
        ]
        if (rc := lib.libusb_init(None)) != 0:
            raise OSError(f"libusb_init: {self.error(rc)}")

    def error(self, code: int) -> str:
        text: bytes | None = self._lib.libusb_strerror(code)
        return text.decode() if text else f"libusb error {code}"

    def open_mic(self) -> int | str:
        """The claimed mic's handle, or why it could not be opened."""
        handle: int | None = self._lib.libusb_open_device_with_vid_pid(
            None, VENDOR, PRODUCT
        )
        if not handle:
            return "the mic is not plugged in, or not accessible (udev rule)"
        _ = self._lib.libusb_set_auto_detach_kernel_driver(handle, 1)
        if (rc := self._lib.libusb_claim_interface(handle, INTERFACE)) != 0:
            self._lib.libusb_close(handle)
            return f"claim: {self.error(rc)} (another program drives the lights?)"
        return handle

    def send(self, handle: int, packet: bytes) -> str | None:
        sent: int = self._lib.libusb_control_transfer(
            handle,
            SET_REPORT_TYPE,
            SET_REPORT,
            FEATURE_REPORT_0,
            INTERFACE,
            packet,
            PACKET_SIZE,
            TIMEOUT_MS,
        )
        if sent == PACKET_SIZE:
            return None
        return self.error(sent) if sent < 0 else f"sent {sent} of {PACKET_SIZE} bytes"

    def close(self, handle: int) -> None:
        _ = self._lib.libusb_release_interface(handle, INTERFACE)
        self._lib.libusb_close(handle)

    def exit(self) -> None:
        self._lib.libusb_exit(None)


class Watcher:
    """Polls the sound server on its own thread while Voice level is on, for
    the mic's source (it changes when the mic or the server comes back)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wanted = False
        self.mic: int | None = None  # the mic's source index
        self.connections = 0  # bumps on each new connection: meters reconnect

    def start(self, on_bug: Callable[[str], bool | None]) -> None:
        in_background(self._run, on_bug)

    def want(self, *, on: bool) -> None:
        with self._lock:
            self._wanted = on

    def _run(self) -> None:
        pulse: pulsectl.Pulse | None = None
        while True:
            with self._lock:
                wanted = self._wanted
            if not wanted:
                if pulse is not None:
                    pulse.close()
                    pulse = None
            else:
                try:
                    if pulse is None:
                        pulse = pulsectl.Pulse("gtk-widgets-mic-lights")
                        with self._lock:
                            self.connections += 1
                    self._poll(pulse)
                # a call on a dropped connection raises libpulse's CallError
                except pulsectl.PulseError, c.pa.CallError:
                    if pulse is not None:
                        pulse.close()
                    pulse = None
            time.sleep(STATUS_POLL_S)

    def _poll(self, pulse: pulsectl.Pulse) -> None:
        sources = pulse.source_list()
        mic = next(
            (
                s
                for s in sources
                if s.proplist.get("device.vendor.id") == MIC_VENDOR
                and s.proplist.get("device.product.id") == MIC_PRODUCT
                and s.proplist.get("device.class") == "sound"
            ),
            None,
        )
        with self._lock:
            self.mic = mic.index if mic is not None else None


class Daemon:
    def __init__(self, usb: Usb, loop: GLib.MainLoop) -> None:
        self._usb, self._loop = usb, loop
        self._mtime = settings_mtime()  # before load: a save in between is seen
        self._lights = load()
        self._checked = self._retry_at = 0.0
        self._handle: int | None = None
        self._problem = ""
        self._start = time.monotonic()
        self._header = header_packet()
        self._level = 0.0
        self._watcher = Watcher()
        self._watcher.start(self._on_bug)
        self._meters: Meters[str] | None = None
        self._meter_for: tuple[int, int] | None = None  # (connection, source)
        self._follow()

    def tick(self) -> bool:
        now = time.monotonic()
        if now - self._checked >= SETTINGS_CHECK_S:
            self._checked = now
            if (mtime := settings_mtime()) != self._mtime:
                self._lights, self._mtime = load(), mtime
                self._follow()
        if not self._lights.on:
            self._loop.quit()
            return GLib.SOURCE_REMOVE
        self._sync_meter()
        if self._handle is None and not self._open(now):
            return GLib.SOURCE_CONTINUE
        if self._handle is not None:
            self._send(self._handle, now)
        return GLib.SOURCE_CONTINUE

    def close(self) -> None:
        if self._meters is not None:
            self._meters.stop()
        if self._handle is not None:
            self._usb.close(self._handle)
            self._handle = None

    def _follow(self) -> None:
        self._watcher.want(on=self._lights.effect in PULSE_EFFECTS)

    def _open(self, now: float) -> bool:
        if now < self._retry_at:
            return False
        match self._usb.open_mic():
            case str() as problem:
                self._report(problem)
                self._retry_at = now + RETRY_S
                return False
            case handle:
                self._handle, self._problem = handle, ""
                print("lights on", flush=True)
                return True

    def _send(self, handle: int, now: float) -> None:
        self._level *= LEVEL_RELEASE
        status = Status(self._level)
        top, bottom = parts_at(self._lights, now - self._start, status)
        frame = colour_packet(top, bottom, self._lights.brightness)
        problem = self._usb.send(handle, self._header) or self._usb.send(handle, frame)
        if problem:
            self._report(f"send: {problem}")
            self._usb.close(handle)
            self._handle = None

    def _report(self, problem: str) -> None:
        if problem != self._problem:
            print(problem, file=sys.stderr, flush=True)
            self._problem = problem

    def _sync_meter(self) -> None:
        """A peak meter on the mic while the effect is voice, a new one after
        the sound server or the mic comes back."""
        mic, connection = self._watcher.mic, self._watcher.connections
        want = (
            (connection, mic)
            if self._lights.effect == "voice" and mic is not None
            else None
        )
        if want == self._meter_for:
            return
        if self._meters is not None:
            self._meters.stop()
            self._meters = None
        self._meter_for = want
        if want is not None:
            self._meters = Meters[str](self._on_peaks)
            self._meters.start(self._on_bug)
            self._meters.set_targets({METER_KEY: (want[1], None, False)})

    def _on_peaks(self) -> bool:
        if self._meters is not None:
            peak = self._meters.take_peaks().get(METER_KEY, 0.0)
            db = 20 * math.log10(max(peak, 1e-9))
            level = (db - LEVEL_SILENT_DB) / (LEVEL_LOUD_DB - LEVEL_SILENT_DB)
            self._level = max(self._level, min(1.0, max(0.0, level)))
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _on_bug(message: str) -> bool:
        print(message, file=sys.stderr, flush=True)
        return GLib.SOURCE_REMOVE


def quit_loop(loop: GLib.MainLoop) -> bool:
    loop.quit()
    return GLib.SOURCE_REMOVE


def settings_mtime() -> tuple[int, int]:
    """Changes with every save: each one replaces the file (a new inode), also
    within one tick of the clock."""
    try:
        stat = SETTINGS_FILE.stat()
    except OSError:
        return (0, 0)
    return (stat.st_ino, stat.st_mtime_ns)


def main() -> int:
    try:
        lib = ctypes.CDLL(LIBUSB)
    except OSError as e:
        print(f"{LIBUSB} not found ({e}): sudo pacman -S libusb", file=sys.stderr)
        return 1
    usb = Usb(lib)
    loop = GLib.MainLoop()
    daemon = Daemon(usb, loop)
    for signum in (signal.SIGTERM, signal.SIGINT):
        _ = GLib.unix_signal_add(
            GLib.PRIORITY_DEFAULT, signum, partial(quit_loop, loop)
        )
    failed: list[Exception] = []
    _ = GLib.timeout_add(FRAME_MS, partial(frame, daemon, loop, failed))
    try:
        loop.run()
    finally:
        daemon.close()
        usb.exit()
    return 1 if failed else 0


def frame(daemon: Daemon, loop: GLib.MainLoop, failed: list[Exception]) -> bool:
    """A bug in a frame ends the daemon (exit 1, so systemd restarts it): GLib
    would drop the timer and leave it running with no frames."""
    try:
        return daemon.tick()
    except Exception as e:
        failed.append(e)
        loop.quit()
        raise


if __name__ == "__main__":
    sys.exit(main())
