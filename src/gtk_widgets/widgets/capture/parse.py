"""sway's IPC replies (GET_OUTPUTS, GET_TREE) and ffprobe's and ffmpeg's
listings of a recording: their models and parsers.

The models are NamedTuples, not dataclasses: capture imports this before it
grabs the screen, and dataclasses (with inspect) would cost it ~5 ms.
"""

import json
from collections.abc import Mapping
from fractions import Fraction
from typing import NamedTuple

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

type Rect = tuple[int, int, int, int]  # x, y, w, h


class Output(NamedTuple):
    """An active output: rect in logical (layout) pixels, transform sway's
    name for it ("normal", "90", ...)."""

    name: str
    scale: float  # a C float from sway (1.2999999523162842); swayipc snaps it
    rect: Rect
    transform: str


class Node(NamedTuple):
    """A node of sway's tree. window_rect is relative to rect; for a view it
    leaves out the border and title bar."""

    type: str
    name: str | None
    rect: Rect
    window_rect: Rect | None
    view: bool  # a window (it has a "shell")
    visible: bool  # views only: false for a hidden tab
    fullscreen: bool
    current_workspace: str | None  # outputs only
    nodes: tuple[Node, ...]
    floating_nodes: tuple[Node, ...]  # in stacking order, the top one last


def _rect(value: object, path: str) -> Rect | ParseError:
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    match (
        as_int(value.get("x"), f"{path}.x"),
        as_int(value.get("y"), f"{path}.y"),
        as_int(value.get("width"), f"{path}.width"),
        as_int(value.get("height"), f"{path}.height"),
    ):
        case int() as x, int() as y, int() as w, int() as h:
            return x, y, w, h
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def _json(raw: bytes) -> object:
    try:
        data: object = json.loads(raw)
    except ValueError as e:
        return ParseError(f"not JSON: {e}")
    return data


def parse_outputs(raw: bytes) -> list[Output] | ParseError:
    """The active outputs of a GET_OUTPUTS reply (sway lists inactive ones
    with a scale of -1)."""
    items = as_array(_json(raw), "outputs")
    if isinstance(items, ParseError):
        return items
    found: list[Output] = []
    for i, item in enumerate(items):
        path = f"outputs[{i}]"
        if not is_object(item):
            return ParseError(f"{path}: not an object")
        if item.get("active") is not True:
            continue
        output = _output(item, path)
        if isinstance(output, ParseError):
            return output
        if output.scale > 0:
            found.append(output)
    return found


def _output(item: Mapping[str, object], path: str) -> Output | ParseError:
    transform = item.get("transform", "normal")
    match (
        as_str(item.get("name"), f"{path}.name"),
        as_float(item.get("scale"), f"{path}.scale"),
        _rect(item.get("rect"), f"{path}.rect"),
        as_str(transform, f"{path}.transform"),
    ):
        case str() as name, float() as scale, (
            int(),
            int(),
            int(),
            int(),
        ) as rect, str() as t:
            return Output(name, scale, rect, t)
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


def parse_tree(raw: bytes) -> Node | ParseError:
    """A GET_TREE reply."""
    return _node(_json(raw), "tree")


def _node(data: object, path: str) -> Node | ParseError:
    if isinstance(data, ParseError):
        return data
    if not is_object(data):
        return ParseError(f"{path}: not an object")
    children: list[tuple[Node, ...]] = []
    for key in ("nodes", "floating_nodes"):
        items = as_array(data.get(key), f"{path}.{key}")
        if isinstance(items, ParseError):
            return items
        nodes: list[Node] = []
        for i, item in enumerate(items):
            node = _node(item, f"{path}.{key}[{i}]")
            if isinstance(node, ParseError):
                return node
            nodes.append(node)
        children.append(tuple(nodes))
    window_rect = data.get("window_rect")
    visible = data.get("visible", False)
    match (
        as_str(data.get("type"), f"{path}.type"),
        as_str_or_none(data.get("name"), f"{path}.name"),
        _rect(data.get("rect"), f"{path}.rect"),
        None if window_rect is None else _rect(window_rect, f"{path}.window_rect"),
        as_bool(visible, f"{path}.visible"),
        as_int(data.get("fullscreen_mode", 0), f"{path}.fullscreen_mode"),
        as_str_or_none(data.get("current_workspace"), f"{path}.current_workspace"),
    ):
        case (
            str() as kind,
            str() | None as name,
            (int(), int(), int(), int()) as rect,
            (int(), int(), int(), int()) | None as window,
            bool() as shown,
            int() as fullscreen,
            str() | None as workspace,
        ):
            return Node(
                kind,
                name,
                rect,
                window,
                "shell" in data,
                shown,
                fullscreen != 0,
                workspace,
                children[0],
                children[1],
            )
        case fields:
            return next(f for f in fields if isinstance(f, ParseError))


_NA = "N/A"
_FRAMEMD5_TB = "#tb 0:"
_PTS_FIELD = 2  # framemd5: stream, dts, pts, duration, size, hash


def parse_span(text: str) -> tuple[Fraction, Fraction] | ParseError:
    """(first frame's time, end time) in seconds, from ffprobe's compact
    listing of the stream's time_base and its packets' pts and duration."""
    tb: Fraction | None = None
    starts: list[int] = []
    ends: list[int] = []
    try:
        for line in text.splitlines():
            fields = dict(f.split("=", 1) for f in line.split("|") if "=" in f)
            if "time_base" in fields:
                tb = Fraction(fields["time_base"])
            elif fields.get("pts", _NA) != _NA:
                pts = int(fields["pts"])
                duration = fields.get("duration", _NA)
                starts.append(pts)
                ends.append(pts + (int(duration) if duration != _NA else 0))
    except ValueError as e:
        return ParseError(f"ffprobe: {e}")
    if tb is None or not starts:
        return ParseError("ffprobe: no time base or no packets")
    return min(starts) * tb, max(ends) * tb


def parse_size(text: str) -> tuple[int, int] | ParseError:
    """(width, height) from ffprobe's "W,H" line."""
    match text.strip().split(","):
        case [w, h]:
            try:
                return int(w), int(h)
            except ValueError:
                pass
        case _:
            pass
    return ParseError(f"ffprobe: not a size: {text!r}")


def framemd5_tb(line: str) -> Fraction | ParseError | None:
    """The time base a framemd5 listing's "#tb 0:" line gives, or None for
    another line."""
    if not line.startswith(_FRAMEMD5_TB):
        return None
    try:
        return Fraction(line.split(":", 1)[1].strip())
    except ValueError as e:
        return ParseError(f"framemd5: {e}")


def framemd5_pts(line: str) -> int | ParseError | None:
    """The pts of a framemd5 listing's frame line, or None for a comment or
    a blank line."""
    if not line.strip() or line.startswith("#"):
        return None
    try:
        return int(line.split(",")[_PTS_FIELD])
    except (ValueError, IndexError) as e:
        return ParseError(f"framemd5: {e}")
