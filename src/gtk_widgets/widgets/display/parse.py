"""swaymsg's output list, read for the active output's scale."""

from gtk_widgets.lib.parse import ParseError, as_bool, as_float, is_array, is_object


def parse_active_scale(data: object) -> float | ParseError | None:
    """`swaymsg -t get_outputs`: the first active output's scale (1.0 when it
    has none), None when no output is active."""
    if not is_array(data):
        return ParseError("not an array")
    for i, output in enumerate(data):
        if not is_object(output):
            return ParseError(f"[{i}]: not an object")
        active = as_bool(output.get("active", False), f"[{i}].active")
        if isinstance(active, ParseError):
            return active
        if active:
            return as_float(output.get("scale", 1.0), f"[{i}].scale")
    return None
