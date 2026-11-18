"""The popup's state file: its model and parser."""

import re
from dataclasses import dataclass, field
from typing import Literal

from gtk_widgets.lib.parse import (
    ParseError,
    as_array,
    as_bool,
    as_float,
    as_int,
    as_str,
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


type Effect = Literal["solid", "pulse", "cycle", "wave", "blink", "lightning", "voice"]
EFFECTS: tuple[Effect, ...] = (
    "solid",
    "pulse",
    "cycle",
    "wave",
    "blink",
    "lightning",
    "voice",
)
MAX_EFFECT_COLOURS = 3
PERCENT = 100


@dataclass(slots=True)
class Lights:
    """The mic lights file's fields, in its order. Colours are #rrggbb
    ("#000000" = dark). top/bottom: each part's colour (solid, voice);
    colours: 1-3 colours the animated effects use; speed and brightness in
    percent."""

    on: bool = False
    effect: Effect = "solid"
    top: str = "#ff0000"
    bottom: str = "#0030ff"
    colours: list[str] = field(default_factory=lambda: ["#ff0000", "#0030ff"])
    speed: int = 50
    brightness: int = 100


def _hex_colour(value: object, path: str) -> str | ParseError:
    match as_str(value, path):
        case ParseError() as error:
            return error
        case text if re.fullmatch(r"#[0-9a-f]{6}", text):
            return text
        case _:
            return ParseError(f"{path}: not a #rrggbb colour")


def _effect(value: object, path: str) -> Effect | ParseError:
    """An effect name no longer offered (dropped) is solid, so the lights stay
    on with the file's other settings."""
    match as_str(value, path):
        case ParseError() as error:
            return error
        case name:
            for effect in EFFECTS:
                if effect == name:
                    return effect
            return "solid"


def _colours(value: object, path: str) -> list[str] | ParseError:
    match as_array(value, path):
        case ParseError() as error:
            return error
        case items if not 1 <= len(items) <= MAX_EFFECT_COLOURS:
            return ParseError(f"{path}: not 1-{MAX_EFFECT_COLOURS} colours")
        case items:
            colours: list[str] = []
            for n, item in enumerate(items):
                match _hex_colour(item, f"{path}[{n}]"):
                    case ParseError() as error:
                        return error
                    case colour:
                        colours.append(colour)
            return colours


def _percent(value: object, path: str) -> int | ParseError:
    match as_int(value, path):
        case int() as number if 0 <= number <= PERCENT:
            return number
        case ParseError() as error:
            return error
        case _:
            return ParseError(f"{path}: not 0-{PERCENT}")


def parse_lights(data: object) -> Lights | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    d = Lights()
    match (
        as_bool(data.get("on", d.on), ".on"),
        _effect(data.get("effect", d.effect), ".effect"),
        _hex_colour(data.get("top", d.top), ".top"),
        _hex_colour(data.get("bottom", d.bottom), ".bottom"),
        _colours(data.get("colours", d.colours), ".colours"),
        _percent(data.get("speed", d.speed), ".speed"),
        _percent(data.get("brightness", d.brightness), ".brightness"),
    ):
        case (
            bool() as on,
            (
                "solid" | "pulse" | "cycle" | "wave" | "blink" | "lightning" | "voice"
            ) as effect,
            str() as top,
            str() as bottom,
            list() as colours,
            int() as speed,
            int() as brightness,
        ):
            return Lights(on, effect, top, bottom, colours, speed, brightness)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))
