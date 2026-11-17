"""A popup that `widget-toggle` closes, as its hotkey does, stops its children.

`widget-toggle` runs the widget from `~/.local/bin` (here a fake HOME with
install.sh's launchers) on conftest's headless Sway, and a second
`widget-toggle` closes it. The child the popup started must be gone then.

  uv run pytest -c pytest.toml tests/widget_toggle_test.py
"""

import os
import struct
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from gtk_widgets.lib.paths import SRC
from gtk_widgets.lib.wayland import Connection

REPO = SRC.parent
# install.sh's launcher: widget-toggle closes only a process run from it
LAUNCHER = f"""#!/usr/bin/env python3
import sys
sys.path.insert(0, {str(SRC)!r})
from gtk_widgets.widgets.{{module}}.main import main
sys.exit(main())
"""
# An adapter that is on with no devices; a scan runs for its --timeout
FAKE_BLUETOOTHCTL = """#!/usr/bin/env python3
import sys, time
args = sys.argv[1:]
if args == ["show"]:
    print("Controller 00:00:00:00:00:01 (public)\\n\\tPowered: yes")
elif args[-2:] == ["scan", "on"]:
    time.sleep(float(args[args.index("--timeout") + 1]))
"""
OPEN_TIMEOUT = 15  # seconds for the popup to start its child
CLOSE_TIMEOUT = 5  # seconds for the popup and its child to go after the toggle
POLL = 0.1
CLICK_RETRY = 0.5  # seconds between clicks while the popup is not up yet
OUTPUT = (1280, 720)  # conftest's headless output, scale 1
SCAN_BUTTON = (640, 121)  # logical px: "Scan for devices" with no devices
EXTENT = 100_000
BTN_LEFT = 0x110

# zwlr_virtual_pointer_manager_v1 / zwlr_virtual_pointer_v1 requests
CREATE_POINTER = 0
MOTION_ABSOLUTE, BUTTON, FRAME, DESTROY = 1, 2, 4, 8
PRESSED, RELEASED = 1, 0


def click(x: int, y: int) -> None:
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

        ex, ey = (
            round(v / size * EXTENT) for v, size in zip((x, y), OUTPUT, strict=True)
        )
        event(MOTION_ABSOLUTE, struct.pack("=IIIII", now(), ex, ey, EXTENT, EXTENT))
        event(BUTTON, struct.pack("=III", now(), BTN_LEFT, PRESSED))
        event(BUTTON, struct.pack("=III", now(), BTN_LEFT, RELEASED))
        conn.send(pointer, DESTROY)
        conn.roundtrip()
    finally:
        conn.close()


def cmdline(pid: int) -> str:
    """The process's argv joined by spaces; "" once it is gone or a zombie."""
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except FileNotFoundError:
        return ""
    return raw.rstrip(b"\0").replace(b"\0", b" ").decode(errors="replace")


def children(pid: int) -> dict[int, str]:
    out = subprocess.run(
        ["ps", "-o", "pid=", "--ppid", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return {int(p): cmdline(int(p)) for p in out.split()}


class Desktop:
    """A fake HOME with the widgets' launchers and a private runtime dir."""

    def __init__(self, tmp_path: Path) -> None:
        self.runtime = tmp_path / "runtime"  # lock and pid files, away from the user's
        self.runtime.mkdir(mode=0o700)
        home = tmp_path / "home"
        self.bin = home / ".local" / "bin"
        self.bin.mkdir(parents=True)
        fakes = tmp_path / "fakes"
        fakes.mkdir()
        self.fakes = fakes
        self.env = {
            **os.environ,
            "HOME": str(home),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "PATH": f"{fakes}:{os.environ['PATH']}",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        }

    def install(self, widget: str, module: str) -> None:
        launcher = self.bin / widget
        _ = launcher.write_text(LAUNCHER.format(module=module), encoding="utf-8")
        launcher.chmod(0o755)

    def fake(self, name: str, script: str) -> None:
        path = self.fakes / name
        _ = path.write_text(script, encoding="utf-8")
        path.chmod(0o755)

    def toggle(self, widget: str) -> None:
        _ = subprocess.run(
            [str(REPO / "widget-toggle"), widget],
            env=self.env,
            check=True,
            timeout=CLOSE_TIMEOUT,
        )

    def widget_pid(self, widget: str) -> int:
        pid_file = self.runtime / f"gtk-widgets-{widget}-toggle.pid"
        deadline = time.monotonic() + OPEN_TIMEOUT
        while not (text := pid_file.read_text() if pid_file.exists() else "").strip():
            assert time.monotonic() < deadline, (
                f"widget-toggle {widget} started nothing"
            )
            time.sleep(POLL)
        return int(text)


def wait_child(
    pid: int, marker: str, poke: Callable[[], None] = lambda: None
) -> tuple[int, str]:
    """The widget's child whose argv holds marker, poking the popup until it starts."""
    deadline = time.monotonic() + OPEN_TIMEOUT
    while True:
        found = [(c, cmd) for c, cmd in children(pid).items() if marker in cmd]
        if found:
            return found[0]
        assert cmdline(pid), "the popup exited before it started its child"
        assert time.monotonic() < deadline, f"the popup never ran {marker!r}"
        poke()
        time.sleep(POLL)


def assert_closed_with_child(widget: str, pid: int, child: tuple[int, str]) -> None:
    deadline = time.monotonic() + CLOSE_TIMEOUT
    while cmdline(pid) or cmdline(child[0]) == child[1]:
        if time.monotonic() > deadline:
            break
        time.sleep(POLL)
    assert not cmdline(pid), f"{widget} is still open after the second widget-toggle"
    left = cmdline(child[0])
    assert left != child[1], f"{widget}'s child still runs after its close: {left}"


def test_usb_toggle_stops_its_udev_monitor(tmp_path: Path) -> None:
    desk = Desktop(tmp_path)
    desk.install("usb", "usb")
    desk.toggle("usb")
    pid = desk.widget_pid("usb")
    child = wait_child(pid, "udevadm monitor --subsystem-match=block")
    try:
        desk.toggle("usb")
        assert_closed_with_child("usb", pid, child)
    finally:
        for p in (pid, child[0]):
            if cmdline(p):
                os.kill(p, 15)


def test_bluetooth_toggle_stops_its_scan(tmp_path: Path) -> None:
    desk = Desktop(tmp_path)
    desk.install("bluetooth", "bluetooth")
    desk.fake("bluetoothctl", FAKE_BLUETOOTHCTL)
    desk.toggle("bluetooth")
    pid = desk.widget_pid("bluetooth")
    last_click = 0.0

    def press_scan() -> None:
        nonlocal last_click
        if time.monotonic() - last_click >= CLICK_RETRY:
            last_click = time.monotonic()
            click(*SCAN_BUTTON)

    child = wait_child(pid, "--timeout 10 scan on", press_scan)
    try:
        desk.toggle("bluetooth")
        assert_closed_with_child("bluetooth", pid, child)
    finally:
        for p in (pid, child[0]):
            if cmdline(p):
                os.kill(p, 15)
