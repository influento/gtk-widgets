"""The wf-recorder side of capture gif: which region to ask for, the command
line, start and stop. No GTK here, so the region maths can be tested alone.

wf-recorder's -g takes a logical rectangle. The compositor (wlroots'
screencopy) turns it into buffer pixels by multiplying x, y, width and
height by the output's scale in single precision and truncating each, and
wf-recorder then drops an odd last column or row (its frames have even
sizes). At a fractional scale a physical selection is rarely whole logical
pixels, so the recording asks for a logical rectangle that encloses it and
crops the exact physical rectangle out of that buffer with -F crop. Both
steps are computed here the way they happen there (checked on a headless
sway at 1.3: 2900 * 1.3 gives buffer column 3769, not 3770).
"""

import math
import os
import shutil
import signal
import struct
import subprocess

type Rect = tuple[int, int, int, int]  # x, y, w, h

MAX_SECONDS = 60  # hard cap: the recording stops itself, as if stopped by hand
FPS = 30  # constant frame rate (wf-recorder -r)
STOP_TIMEOUT_S = 10
_LEFT_STEPS = 16  # logical starts tried left of the first fit


def _f32(x: float) -> float:
    """x rounded to a C float."""
    (f,) = struct.unpack("=f", struct.pack("=f", x))
    return f


def _buffer(value: int, scale: float) -> int:
    """A logical coordinate or length in buffer pixels, as the compositor
    computes it: int *= float in single precision, truncated."""
    return int(_f32(value * _f32(scale)))


def _even(n: int) -> int:
    return n - n % 2


def _axis(
    start: int, size: int, scale: float, logical: int
) -> tuple[int, int, int, int]:
    """One axis of plan(): (logical start, logical length, buffer start,
    recorded size). The recorded size is size unless the selection reaches
    a far edge the buffer can't (the strip past the last whole logical
    pixel at a fractional scale)."""
    end = start + size
    first = min(math.floor(start / scale), logical - 1)
    while first > 0 and _buffer(first, scale) > start:
        first -= 1
    best: tuple[int, int, int, int] | None = None
    # A logical start a few pixels further left can let an even buffer
    # length reach the end (the far edge at 1.25 needs 8)
    for lstart in range(first, max(first - _LEFT_STEPS, -1), -1):
        bstart = _buffer(lstart, scale)
        length = max(1, math.ceil((end - bstart) / scale) - 1)
        while lstart + length <= logical:
            reach = bstart + _even(_buffer(length, scale))
            if reach >= end:
                return lstart, length, bstart, size
            if best is None or reach > best[2] + best[3]:
                best = (lstart, length, bstart, reach - bstart)
            length += 1
    if best is None or best[2] + best[3] <= start:
        raise ValueError(
            f"no logical region records pixels {start}..{end - 1} at scale {scale}"
        )
    lstart, length, bstart, _ = best
    return lstart, length, bstart, best[2] + best[3] - start


class Plan:
    """box: the logical rectangle for -g, output-local; crop: the rectangle
    cut from wf-recorder's buffer; rect: the physical rectangle recorded
    (the selection, less a far edge the buffer can't reach)."""

    def __init__(self, box: Rect, crop: Rect, rect: Rect) -> None:
        self.box = box
        self.crop = crop
        self.rect = rect


def plan(rect: Rect, scale: float, logical_size: tuple[int, int]) -> Plan:
    """Plan for a physical selection rect = (x, y, w, h) on an output with
    this exact scale and logical size (w, h)."""
    x, y, w, h = rect
    lx, lw, bx, w = _axis(x, w, scale, logical_size[0])
    ly, lh, by, h = _axis(y, h, scale, logical_size[1])
    return Plan((lx, ly, lw, lh), (x - bx, y - by, w, h), (x, y, w, h))


def command(output: str, origin: tuple[int, int], p: Plan, path: str) -> list[str]:
    """wf-recorder's command line for Plan p on output (its name) at logical
    layout position origin, writing the lossless RGB intermediate to path.
    -D (no damage tracking): with it, wf-recorder waits for the next screen
    update before it looks at SIGINT, so on a still screen it never stops."""
    x, y, w, h = p.box
    cx, cy, cw, ch = p.crop
    return [
        "wf-recorder",
        "-y",
        "-D",
        "-o",
        output,
        "-g",
        f"{origin[0] + x},{origin[1] + y} {w}x{h}",
        "-r",
        str(FPS),
        "-x",
        "bgr0",
        "-c",
        "libx264rgb",
        "-p",
        "crf=0",
        "-p",
        "preset=ultrafast",
        "-F",
        f"crop={cw}:{ch}:{cx}:{cy}",
        "-f",
        path,
    ]


class Recorder:
    """A wf-recorder process. Its output goes to a temporary file, shown
    when it fails."""

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.proc: subprocess.Popen[bytes] | None = None
        self._log = os.memfd_create("wf-recorder-log", os.MFD_CLOEXEC)

    def _started(self) -> subprocess.Popen[bytes]:
        if self.proc is None:
            raise RuntimeError("wf-recorder was not started")
        return self.proc

    def start(self) -> None:
        """Raises OSError when wf-recorder can't be started."""
        argv = self.argv
        if shutil.which("setpriv"):
            # Stops cleanly if we die without stopping it
            argv = ["setpriv", "--pdeathsig", "INT", *argv]
        self.proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=self._log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def exited(self) -> bool:
        return self._started().poll() is not None

    def stop(self, timeout: float = STOP_TIMEOUT_S) -> int:
        """SIGINT (wf-recorder finalises the file on it), then wait. Returns
        the exit status."""
        proc = self._started()
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGINT)
            try:
                proc.wait(timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        return proc.returncode

    def output(self) -> str:
        size = os.fstat(self._log).st_size
        return os.pread(self._log, size, 0).decode(errors="replace")

    def region_error(self) -> str | None:
        """wf-recorder records the whole output instead of a region it finds
        invalid, which the crop would not notice: the complaint, or None."""
        want = self.argv[self.argv.index("-g") + 1]
        for line in self.output().splitlines():
            if line.startswith("selected region ") and line.split(" ", 2)[2] != want:
                return f"wf-recorder recorded {line.split(' ', 2)[2]!r}, not {want!r}"
        return None
