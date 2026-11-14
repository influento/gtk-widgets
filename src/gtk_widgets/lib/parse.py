"""Checks for outside JSON data (stdlib only): the project's stand-in for a
schema library. A parser builds its dataclass from these readers and returns
ParseError, naming the field, instead of raising. Parsing lives only in
modules named parse.py, where the gate lets a function take `object`.

isinstance(True, int) is True, so the number readers refuse bools.
"""

from collections.abc import Mapping
from typing import TypeIs


class ParseError(ValueError):
    """Outside data does not have the expected shape."""


def is_object(value: object) -> TypeIs[Mapping[str, object]]:
    """A JSON object: a mapping whose keys are all strings."""
    return _is_mapping(value) and all(isinstance(k, str) for k in value)


def is_array(value: object) -> TypeIs[list[object]]:
    return isinstance(value, list)


def _is_mapping(value: object) -> TypeIs[Mapping[object, object]]:
    return isinstance(value, Mapping)


def as_str(value: object, path: str) -> str | ParseError:
    return value if isinstance(value, str) else ParseError(f"{path}: not a string")


def as_bool(value: object, path: str) -> bool | ParseError:
    return value if isinstance(value, bool) else ParseError(f"{path}: not a boolean")


def as_int(value: object, path: str) -> int | ParseError:
    return value if type(value) is int else ParseError(f"{path}: not an integer")


def as_float(value: object, path: str) -> float | ParseError:
    """A number; an int is taken as a float."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return ParseError(f"{path}: not a number")
    return float(value)


def parse_colors(data: object) -> dict[str, str] | ParseError:
    """A theme file: {"colors": {NAME: hex without the #, ...}}."""
    found = data.get("colors") if is_object(data) else None
    if not is_object(found):
        return ParseError(".colors: not an object")
    palette: dict[str, str] = {}
    for name, value in found.items():
        match as_str(value, f".colors.{name}"):
            case ParseError() as e:
                return e
            case colour:
                palette[name] = colour
    return palette
