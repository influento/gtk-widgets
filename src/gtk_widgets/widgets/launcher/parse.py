"""The launch counts file (usage.json): its model and parser."""

from dataclasses import dataclass

from gtk_widgets.lib.parse import ParseError, as_float, is_object


@dataclass(frozen=True, slots=True)
class Launches:
    """One app's decayed launch count. The fields are in the file's order."""

    score: float  # valid at `time`
    time: float  # seconds since the epoch


def parse_usage(data: object) -> dict[str, Launches] | ParseError:
    """{desktop id: {score, time}}; an entry of another shape is dropped."""
    if not is_object(data):
        return ParseError("not an object")
    usage: dict[str, Launches] = {}
    for key, value in data.items():
        if not is_object(value):
            continue
        match (
            as_float(value.get("score"), f".{key}.score"),
            as_float(value.get("time"), f".{key}.time"),
        ):
            case float() as score, float() as time:
                usage[key] = Launches(score, time)
            case _:
                pass
    return usage
