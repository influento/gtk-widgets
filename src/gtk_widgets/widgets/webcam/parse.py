"""The webcam settings file: its model and parser (stdlib: the effects
engine reads it too)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from gtk_widgets.lib.parse import (
    ParseError,
    as_bool,
    as_float,
    as_int,
    as_str,
    as_str_or_none,
    is_object,
)


class Effect(StrEnum):
    OFF = "off"  # the camera's picture as is
    BLUR = "blur"
    IMAGE = "image"
    COLOUR = "colour"
    ANIMATED = "animated"  # a GIF or video, looped


class Led(StrEnum):
    OFF = "off"
    ON = "on"
    AUTO = "auto"  # on while streaming


DEFAULT_BLUR = 0.5
DEFAULT_COLOUR = "1e1e2e"


@dataclass(slots=True)
class Settings:
    """The file's fields, in its order."""

    # control key -> value, the last ones set: reapplied on replug
    controls: dict[str, int] = field(default_factory=dict[str, int])
    led: Led | None = None  # None: never set here, the camera's own
    # preset name -> control values
    presets: dict[str, dict[str, int]] = field(
        default_factory=dict[str, dict[str, int]]
    )
    effect: Effect = Effect.OFF
    blur: float = DEFAULT_BLUR  # 0..1: blur radius as a share of the largest
    image: str | None = None  # background image path
    animation: str | None = None  # background GIF or video path
    colour: str = DEFAULT_COLOUR  # background colour, hex without #
    mirror_preview: bool = False  # the popup's preview flipped left to right
    mirror_output: bool = False  # webcam-effects flips what apps get


def _values(data: object, path: str) -> dict[str, int] | ParseError:
    if not is_object(data):
        return ParseError(f"{path}: not an object")
    values: dict[str, int] = {}
    for key, value in data.items():
        match as_int(value, f"{path}.{key}"):
            case ParseError() as e:
                return e
            case int() as number:
                values[key] = number
    return values


def _presets(data: object) -> dict[str, dict[str, int]] | ParseError:
    if not is_object(data):
        return ParseError(".presets: not an object")
    presets: dict[str, dict[str, int]] = {}
    for name, values in data.items():
        match _values(values, f".presets.{name}"):
            case ParseError() as e:
                return e
            case found:
                presets[name] = found
    return presets


def _choice[E: StrEnum](
    kind: type[E], data: Mapping[str, object], key: str, default: E | None
) -> E | ParseError | None:
    match as_str_or_none(data.get(key, default), f".{key}"):
        case ParseError() as e:
            return e
        case None:
            return None
        case text if text in {e.value for e in kind}:
            return kind(text)
        case text:
            return ParseError(f".{key}: unknown value {text!r}")


def parse_settings(data: object) -> Settings | ParseError:
    if not is_object(data):
        return ParseError("not an object")
    d = Settings()
    effect = _choice(Effect, data, "effect", d.effect)
    match (
        _values(data.get("controls", {}), ".controls"),
        _choice(Led, data, "led", d.led),
        _presets(data.get("presets", {})),
        Effect.OFF if effect is None else effect,
        as_float(data.get("blur", d.blur), ".blur"),
        as_str_or_none(data.get("image", d.image), ".image"),
        as_str_or_none(data.get("animation", d.animation), ".animation"),
        as_str(data.get("colour", d.colour), ".colour"),
        as_bool(data.get("mirror_preview", d.mirror_preview), ".mirror_preview"),
        as_bool(data.get("mirror_output", d.mirror_output), ".mirror_output"),
    ):
        case (
            dict() as controls,
            (Led() | None) as led,
            dict() as presets,
            Effect() as effect,
            float() as blur,
            (str() | None) as image,
            (str() | None) as animation,
            str() as colour,
            bool() as mirror_preview,
            bool() as mirror_output,
        ):
            return Settings(
                controls,
                led,
                presets,
                effect,
                min(max(blur, 0.0), 1.0),
                image,
                animation,
                colour,
                mirror_preview,
                mirror_output,
            )
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


LINK_SCHEMES = ("https://", "http://")


def parse_link(text: str) -> str | ParseError:
    """A .url file: the link on its first non-empty line."""
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not line.startswith(LINK_SCHEMES):
        return ParseError(f"not an http(s) link: {line[:80]!r}")
    return line


def parse_url_line(output: str) -> str | ParseError:
    """yt-dlp's answer to --get-url or --print thumbnail: a URL on its first
    line."""
    first = output.strip().partition("\n")[0].strip()
    if not first.startswith(LINK_SCHEMES):
        return ParseError("yt-dlp gave no URL")
    return first


@dataclass(frozen=True, slots=True)
class LinkInfo:
    title: str
    thumbnail: str | None  # its URL


def parse_link_info(output: str) -> LinkInfo | ParseError:
    """yt-dlp's answer to --print title --print thumbnail: one per line,
    "NA" for one the site does not give."""
    lines = [line.strip() for line in output.strip().splitlines()]
    if len(lines) < len(("title", "thumbnail")) or not lines[0]:
        return ParseError("yt-dlp gave no title")
    thumbnail = lines[1] if lines[1].startswith(LINK_SCHEMES) else None
    return LinkInfo(lines[0], thumbnail)
