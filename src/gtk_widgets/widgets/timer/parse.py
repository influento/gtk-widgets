"""The timer's state file: its model and parser."""

from dataclasses import dataclass
from typing import Literal

from gtk_widgets.lib.parse import ParseError, as_bool, as_float, as_str, is_object

type Mode = Literal["timer", "stopwatch"]


@dataclass(slots=True)
class State:
    """The state file's fields, in its order."""

    mode: Mode = "timer"
    running: bool = False
    started_at: float | None = None
    accumulated: float = 0.0
    duration: float = 0.0
    fired: bool = False


def parse_state(data: object) -> State | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    d = State()
    started_at = data.get("started_at", d.started_at)
    match (
        as_str(data.get("mode", d.mode), ".mode"),
        as_bool(data.get("running", d.running), ".running"),
        None if started_at is None else as_float(started_at, ".started_at"),
        as_float(data.get("accumulated", d.accumulated), ".accumulated"),
        as_float(data.get("duration", d.duration), ".duration"),
        as_bool(data.get("fired", d.fired), ".fired"),
    ):
        case (
            ("timer" | "stopwatch") as mode,
            bool() as running,
            (float() | None) as started,
            float() as accumulated,
            float() as duration,
            bool() as fired,
        ):
            return State(mode, running, started, accumulated, duration, fired)
        case fields:
            return next(
                (f for f in fields if isinstance(f, ParseError)),
                ParseError(".mode: not timer or stopwatch"),
            )
