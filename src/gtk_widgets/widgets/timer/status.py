#!/usr/bin/env python3
"""Waybar status output for the timer widget.

Outputs JSON: { "text": "...", "tooltip": "...", "class": "..." }
Also fires the alarm (notify-send + paplay) when a running timer hits zero.
Idempotent: the `fired` flag in the state file prevents repeat alarms.
"""

import json

from gtk_widgets.widgets.timer import state as ts

ICON_IDLE = "\uf017"  # nf-fa-clock_o
ICON_RUNNING = "\uf251"  # nf-fa-hourglass_half
ICON_PAUSED = "\uf04c"  # nf-fa-pause
ICON_DONE = "\uf0f3"  # nf-fa-bell


def main() -> None:
    state = ts.load()
    ts.check_expired(state)

    if ts.is_idle(state):
        print(json.dumps({"text": ICON_IDLE, "class": "idle"}))
        return

    secs = ts.display_seconds(state)
    text = f"{ICON_RUNNING if state.running else ICON_PAUSED}  {ts.format_hms(secs)}"

    cls = "running" if state.running else "paused"
    tooltip = f"{state.mode.capitalize()} ({cls})"

    if state.mode == "timer" and ts.remaining(state) == 0.0 and state.duration > 0:
        text = f"{ICON_DONE}  00:00:00"
        cls = "alarm"
        tooltip = "Timer finished"

    print(json.dumps({"text": text, "class": cls, "tooltip": tooltip}))
