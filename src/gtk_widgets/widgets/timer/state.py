"""Shared state model for the timer widget.

State persists in $XDG_RUNTIME_DIR (session-scoped — cleared on logout).
Both the popup and the status script read/write this file.
"""

import fcntl
import json
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.timer.parse import Mode, State, parse_state

_RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()))
STATE_PATH = _RUNTIME_DIR / "gtk-widgets-timer.json"
LOCK_PATH = STATE_PATH.with_name(f"{STATE_PATH.name}.lock")

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
]


def load() -> State:
    """The saved state; a missing, unreadable or malformed file is a fresh one.
    A field the file lacks takes its default."""
    try:
        data: object = json.loads(STATE_PATH.read_text())
    except FileNotFoundError, json.JSONDecodeError:
        return State()
    match parse_state(data):
        case ParseError():
            return State()
        case state:
            return state


def save(state: State) -> None:
    tmp = STATE_PATH.with_name(f"{STATE_PATH.name}.tmp")
    with tmp.open("w") as f:
        json.dump(asdict(state), f)
    tmp.replace(STATE_PATH)


def elapsed(state: State, now: float | None = None) -> float:
    """Seconds counted so far (running + paused segments combined)."""
    now = now if now is not None else time.time()
    e = state.accumulated
    if state.running and state.started_at is not None:
        e += now - state.started_at
    return max(0.0, e)


def remaining(state: State, now: float | None = None) -> float:
    """Seconds left on the timer. Negative-clamped to 0."""
    return max(0.0, state.duration - elapsed(state, now))


def display_seconds(state: State, now: float | None = None) -> float:
    """Seconds to show in the status bar, depending on mode."""
    if state.mode == "stopwatch":
        return elapsed(state, now)
    return remaining(state, now)


def is_idle(state: State) -> bool:
    """No mode is active — show the idle icon."""
    if state.mode == "stopwatch":
        return not state.running and state.accumulated == 0.0
    return state.duration == 0.0


def format_hms(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def start(state: State, now: float | None = None) -> State:
    if state.running:
        return state
    now = now if now is not None else time.time()
    state.running = True
    state.started_at = now
    return state


def pause(state: State, now: float | None = None) -> State:
    if not state.running:
        return state
    now = now if now is not None else time.time()
    state.accumulated += now - (state.started_at or now)
    state.running = False
    state.started_at = None
    return state


def reset(state: State) -> State:
    state.running = False
    state.started_at = None
    state.accumulated = 0.0
    state.duration = 0.0
    state.fired = False
    return state


def set_mode(state: State, mode: Mode) -> State:
    if mode == state.mode:
        return state
    reset(state)
    state.mode = mode
    return state


def set_duration(state: State, seconds: float) -> State:
    """Configure timer duration. Resets progress."""
    state.running = False
    state.started_at = None
    state.accumulated = 0.0
    state.duration = float(seconds)
    state.fired = False
    return state


@contextmanager
def _locked() -> Generator[None]:
    with LOCK_PATH.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def fire_alarm() -> None:
    """Notification + sound. Both are optional and best-effort."""
    if shutil.which("notify-send"):
        subprocess.Popen(
            ["notify-send", "-u", "critical", "-a", "Timer", "Timer", "Time's up!"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    sound = next((p for p in SOUND_CANDIDATES if Path(p).exists()), None)
    if sound and shutil.which("paplay"):
        subprocess.Popen(
            ["paplay", sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def check_expired(state: State, now: float | None = None) -> bool:
    """Pause a running timer that has reached zero and fire the alarm once.

    Both the popup (250 ms tick) and the status script (waybar interval) call
    this, so whichever notices first fires. The file lock plus the persisted
    ``fired`` flag guarantee a single alarm even if both notice at once.
    Returns True if this call paused the timer.
    """
    if state.mode != "timer" or not state.running or remaining(state, now) > 0.0:
        return False
    pause(state, now)
    with _locked():
        already_fired = load().fired
        state.fired = True
        save(state)
    if not already_fired:
        fire_alarm()
    return True
