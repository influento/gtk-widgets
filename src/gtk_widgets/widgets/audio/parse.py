"""The popup's state file: its model and parser."""

from dataclasses import dataclass

from gtk_widgets.lib.parse import ParseError, as_bool, as_str_or_none, is_object


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
