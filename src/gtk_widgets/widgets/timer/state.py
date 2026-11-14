"""Shared state model for the timer widget.

State persists in $XDG_RUNTIME_DIR (session-scoped — cleared on logout).
Both the popup and the status script read/write this file.
"""

import fcntl
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager

_RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STATE_PATH = os.path.join(_RUNTIME_DIR, "gtk-widgets-timer.json")
LOCK_PATH = STATE_PATH + ".lock"

SOUND_CANDIDATES = [
    "/usr/share/sounds/freedesktop/stereo/complete.oga",
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/bell.oga",
]

DEFAULT_STATE = {
    "mode": "timer",
    "running": False,
    "started_at": None,
    "accumulated": 0.0,
    "duration": 0.0,
    "fired": False,
}


def load():
    try:
        with open(STATE_PATH) as f:
            data = json.load(f)
        return {**DEFAULT_STATE, **data}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_STATE)


def save(state):
    tmp = f"{STATE_PATH}.tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_PATH)


def elapsed(state, now=None):
    """Seconds counted so far (running + paused segments combined)."""
    now = now if now is not None else time.time()
    e = state["accumulated"]
    if state["running"] and state["started_at"] is not None:
        e += now - state["started_at"]
    return max(0.0, e)


def remaining(state, now=None):
    """Seconds left on the timer. Negative-clamped to 0."""
    return max(0.0, state["duration"] - elapsed(state, now))


def display_seconds(state, now=None):
    """Seconds to show in the status bar, depending on mode."""
    if state["mode"] == "stopwatch":
        return elapsed(state, now)
    return remaining(state, now)


def is_idle(state):
    """No mode is active — show the idle icon."""
    if state["mode"] == "stopwatch":
        return not state["running"] and state["accumulated"] == 0.0
    return state["duration"] == 0.0


def format_hms(seconds):
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def start(state, now=None):
    if state["running"]:
        return state
    now = now if now is not None else time.time()
    state["running"] = True
    state["started_at"] = now
    return state


def pause(state, now=None):
    if not state["running"]:
        return state
    now = now if now is not None else time.time()
    state["accumulated"] += now - (state["started_at"] or now)
    state["running"] = False
    state["started_at"] = None
    return state


def reset(state):
    state["running"] = False
    state["started_at"] = None
    state["accumulated"] = 0.0
    state["duration"] = 0.0
    state["fired"] = False
    return state


def set_mode(state, mode):
    if mode == state["mode"]:
        return state
    reset(state)
    state["mode"] = mode
    return state


def set_duration(state, seconds):
    """Configure timer duration. Resets progress."""
    state["running"] = False
    state["started_at"] = None
    state["accumulated"] = 0.0
    state["duration"] = float(seconds)
    state["fired"] = False
    return state


@contextmanager
def _locked():
    with open(LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def fire_alarm():
    """Notification + sound. Both are optional and best-effort."""
    if shutil.which("notify-send"):
        subprocess.Popen(
            ["notify-send", "-u", "critical", "-a", "Timer", "Timer", "Time's up!"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    sound = next((p for p in SOUND_CANDIDATES if os.path.exists(p)), None)
    if sound and shutil.which("paplay"):
        subprocess.Popen(
            ["paplay", sound],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def check_expired(state, now=None):
    """Pause a running timer that has reached zero and fire the alarm once.

    Both the popup (250 ms tick) and the status script (waybar interval) call
    this, so whichever notices first fires. The file lock plus the persisted
    ``fired`` flag guarantee a single alarm even if both notice at once.
    Returns True if this call paused the timer.
    """
    if state["mode"] != "timer" or not state["running"] or remaining(state, now) > 0.0:
        return False
    pause(state, now)
    with _locked():
        already_fired = load()["fired"]
        state["fired"] = True
        save(state)
    if not already_fired:
        fire_alarm()
    return True
