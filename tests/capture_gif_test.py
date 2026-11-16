"""`capture gif` from the pick to the sheets on conftest's headless Sway.

A drag picks the region (a wlr virtual pointer, one connection per drag:
headless Sway has no pointer of its own), a second `capture gif` stops the
recording, as the hotkey does, and the first must then print its folder
with the GIF and a sheet in it. A hang anywhere (9384d52's sheets step) runs
into the timeout and fails the test.

  uv run pytest -c pytest.toml tests/capture_gif_test.py
"""

import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

from gtk_widgets.lib.paths import SRC
from gtk_widgets.lib.wayland import Connection

# install.sh's launcher: the stop finds the recording by its script's name
LAUNCHER = f"""import sys
sys.path.insert(0, {str(SRC)!r})
from gtk_widgets.widgets.capture.main import main
sys.exit(main())
"""
PICKER_TIMEOUT = 10  # seconds for the picker to map and take a drag
DRAG_RETRY = 0.5  # seconds between drags while the picker is not up yet
RECORD_SECONDS = 1
STOP_TIMEOUT = 5
SHEETS_TIMEOUT = 30  # seconds from the stop to the sheets; the GIF is tiny
OUTPUT = (1280, 720)  # conftest's headless output, scale 1
DRAG = ((200, 150), (500, 400))  # logical px
EXTENT = 100_000
BTN_LEFT = 0x110

# zwlr_virtual_pointer_manager_v1 / zwlr_virtual_pointer_v1 requests
CREATE_POINTER = 0
MOTION_ABSOLUTE, BUTTON, FRAME, DESTROY = 1, 2, 4, 8
PRESSED, RELEASED = 1, 0


def drag(start: tuple[int, int], end: tuple[int, int]) -> None:
    conn = Connection()
    try:
        names = {iface: name for name, iface, _version in conn.globals()}
        iface = "zwlr_virtual_pointer_manager_v1"
        manager = conn.bind(names[iface], iface, 1, lambda _o, _r: None)
        pointer = conn.new_id(lambda _o, _r: None)
        conn.send(manager, CREATE_POINTER, struct.pack("=II", 0, pointer))

        def event(opcode: int, args: bytes) -> None:
            conn.send(pointer, opcode, args)
            conn.send(pointer, FRAME)
            conn.roundtrip()
            time.sleep(0.05)

        def now() -> int:
            return int(time.monotonic() * 1000) & 0xFFFFFFFF

        def move(x: int, y: int) -> None:
            ex, ey = (
                round(v / size * EXTENT) for v, size in zip((x, y), OUTPUT, strict=True)
            )
            event(MOTION_ABSOLUTE, struct.pack("=IIIII", now(), ex, ey, EXTENT, EXTENT))

        move(*start)
        event(BUTTON, struct.pack("=III", now(), BTN_LEFT, PRESSED))
        move((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
        move(*end)
        event(BUTTON, struct.pack("=III", now(), BTN_LEFT, RELEASED))
        conn.send(pointer, DESTROY)
        conn.roundtrip()
    finally:
        conn.close()


def test_gif_records_and_makes_sheets(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"  # lock and pid files, away from the user's
    runtime.mkdir(mode=0o700)
    env = {
        **os.environ,
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",  # no notifications
    }
    capture = tmp_path / "capture"
    _ = capture.write_text(LAUNCHER, encoding="utf-8")
    out = tmp_path / "out"
    rec = subprocess.Popen(
        [sys.executable, str(capture), "gif", "--dir", str(out)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # its group: ffmpeg too goes on a failure
    )
    try:
        pid_file = runtime / "gtk-widgets-capture-gif.pid"
        deadline = time.monotonic() + PICKER_TIMEOUT
        while not pid_file.exists():
            assert rec.poll() is None, (
                f"capture gif exited {rec.returncode} before recording"
            )
            assert time.monotonic() < deadline, "no recording started after the drag"
            drag(*DRAG)
            time.sleep(DRAG_RETRY)
        time.sleep(RECORD_SECONDS)

        stop = subprocess.run(
            [sys.executable, str(capture), "gif"],
            env=env,
            capture_output=True,
            text=True,
            timeout=STOP_TIMEOUT,
            check=False,
        )
        assert stop.returncode == 0, stop.stderr

        try:
            stdout, stderr = rec.communicate(timeout=SHEETS_TIMEOUT)
        except subprocess.TimeoutExpired:
            msg = f"capture gif did not finish {SHEETS_TIMEOUT} s after the stop"
            raise AssertionError(msg) from None
    finally:
        if rec.poll() is None:
            os.killpg(rec.pid, signal.SIGKILL)
            _ = rec.communicate()

    assert rec.returncode == 0, stderr
    folder = Path(stdout.strip())
    assert folder.parent == out
    assert (folder / "recording.gif").stat().st_size > 0
    assert (folder / "sheet.png").stat().st_size > 0
