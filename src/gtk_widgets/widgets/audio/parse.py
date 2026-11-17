"""The popup's state file: its model and parser."""

from dataclasses import dataclass, field
from typing import Literal

from gtk_widgets.lib.parse import (
    ParseError,
    as_bool,
    as_float,
    as_str_or_none,
    is_object,
)


@dataclass(slots=True)
class State:
    """The state file's fields, in its order."""

    tab: str | None = None  # the tab shown last
    meters: bool = True


def parse_state(data: object) -> State | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    d = State()
    match (
        as_str_or_none(data.get("tab", d.tab), ".tab"),
        as_bool(data.get("meters", d.meters), ".meters"),
    ):
        case (str() | None) as tab, bool() as meters:
            return State(tab, meters)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


type NoiseFilter = Literal["off", "rnnoise", "deepfilter"]
NOISE_FILTERS: tuple[NoiseFilter, ...] = ("off", "rnnoise", "deepfilter")


@dataclass(slots=True)
class Voice:
    """The voice processing file's fields, in its order: the echo-cancelled mic,
    its noise filter and the WebRTC switches it runs with."""

    on: bool = False
    mic: str | None = None  # node name of the mic it cleans
    noise_filter: NoiseFilter = "rnnoise"
    gain_control: bool = False
    high_pass_filter: bool = True
    # filter control key (voice.py) -> value; a missing one takes its default
    controls: dict[str, float] = field(default_factory=dict[str, float])


def _noise_filter(value: object, path: str) -> NoiseFilter | ParseError:
    for name in NOISE_FILTERS:
        if value == name:
            return name
    return ParseError(f"{path}: not one of {', '.join(NOISE_FILTERS)}")


def _controls(value: object, path: str) -> dict[str, float] | ParseError:
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    controls: dict[str, float] = {}
    for key, item in value.items():
        match as_float(item, f"{path}.{key}"):
            case ParseError() as error:
                return error
            case number:
                controls[key] = number
    return controls


def parse_voice(data: object) -> Voice | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    d = Voice()
    match (
        as_bool(data.get("on", d.on), ".on"),
        as_str_or_none(data.get("mic", d.mic), ".mic"),
        _noise_filter(data.get("noise_filter", d.noise_filter), ".noise_filter"),
        as_bool(data.get("gain_control", d.gain_control), ".gain_control"),
        as_bool(data.get("high_pass_filter", d.high_pass_filter), ".high_pass_filter"),
        _controls(data.get("controls", {}), ".controls"),
    ):
        case (
            bool() as on,
            (str() | None) as mic,
            ("off" | "rnnoise" | "deepfilter") as noise_filter,
            bool() as gain,
            bool() as high_pass,
            dict() as controls,
        ):
            return Voice(on, mic, noise_filter, gain, high_pass, controls)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))
