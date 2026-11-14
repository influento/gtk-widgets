"""Output scales and window rectangles from sway's IPC socket (stdlib, a few ms).

The exact fractional scale per output is what the selection maths needs.
GDK's Gdk.Monitor.get_scale() is physical height / logical height (1600 /
1230 = 1.3008 on a 3840x1600 output at 1.3), which puts the far edge 2 px
off; the surface's wp_fractional_scale is rounded to 1/120.
"""

import os
import socket
import struct

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.capture.parse import (
    Node,
    Output,
    Rect,
    parse_outputs,
    parse_tree,
)

_MAGIC = b"i3-ipc"
_GET_OUTPUTS = 3
_GET_TREE = 4
_HEADER = 14  # magic, payload length, type
_LENGTH_AT = 6  # the payload length's offset in the header
_TIMEOUT_S = 1
_STEPS = 120  # scales per 1: wp_fractional_scale's unit
_SNAP = 1e-5


def output_scales() -> dict[str, float]:
    """{output name: scale} of the active outputs, or {} without sway."""
    return {name: o.scale for name, o in outputs().items()}


def outputs() -> dict[str, Output]:
    """{output name: Output} of the active outputs, or {} without sway."""
    raw = _query(_GET_OUTPUTS)
    match parse_outputs(raw) if raw is not None else ParseError("no sway"):
        case ParseError():
            return {}
        case found:
            return {o.name: o._replace(scale=exact_scale(o.scale)) for o in found}


def windows() -> dict[str, list[Rect]]:
    """{output name: [(x, y, w, h), ...]}: the windows shown on each output,
    topmost first, as logical rectangles relative to the output (not
    clipped: one that runs past the output's edge also covers the strip of
    physical pixels past its last whole logical pixel). A rectangle is the window's content: no sway border or title bar,
    no client-side shadow (sway's window_rect is the xdg geometry). Popups
    (menus, tooltips) are not in the tree. {} without sway."""
    raw = _query(_GET_TREE)
    tree = parse_tree(raw) if raw is not None else ParseError("no sway")
    if isinstance(tree, ParseError):
        return {}
    found: dict[str, list[Rect]] = {}
    for output in tree.nodes:
        if output.type != "output" or (output.name or "").startswith("__"):
            continue
        box = output.rect
        fullscreen: list[Node] = []
        floating: list[Node] = []
        tiled: list[Node] = []
        for ws in output.nodes:
            # workspaces in the tree carry no "visible"; the output names its own
            if ws.type != "workspace" or ws.name != output.current_workspace:
                continue
            for node in ws.nodes:
                _views(node, tiled, fullscreen)
            # floating_nodes are in stacking order, the top one last
            for node in reversed(ws.floating_nodes):
                _views(node, floating, fullscreen)
        rects: list[Rect] = []
        for view in fullscreen or floating + tiled:
            x, y, w, h = _content(view)
            if (
                x < box[0] + box[2]
                and y < box[1] + box[3]
                and x + w > box[0]
                and y + h > box[1]
            ):
                rects.append((x - box[0], y - box[1], w, h))
        found[output.name or ""] = rects
    return found


def _views(node: Node, into: list[Node], fullscreen: list[Node]) -> None:
    """Append the shown views under node to into (fullscreen ones to fullscreen)."""
    if node.view:
        if node.visible:
            (fullscreen if node.fullscreen else into).append(node)
        return
    for child in node.nodes:
        _views(child, into, fullscreen)
    for child in reversed(node.floating_nodes):
        _views(child, into, fullscreen)


def _content(view: Node) -> Rect:
    """The view's content in layout coordinates: window_rect is relative to
    its container's rect (which takes in the border and title bar)."""
    r, w = view.rect, view.window_rect
    if w is None or not w[2] or not w[3]:
        return r
    return r[0] + w[0], r[1] + w[1], w[2], w[3]


def _query(kind: int) -> bytes | None:
    """sway's JSON reply to an empty message of this type, or None."""
    path = os.environ.get("SWAYSOCK")
    if not path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(_TIMEOUT_S)
            sock.connect(path)
            sock.sendall(_MAGIC + struct.pack("=II", 0, kind))
            header = _recv(sock, _HEADER)
            length: int
            (length,) = struct.unpack_from("=I", header, _LENGTH_AT)
            return _recv(sock, length)
    except OSError:
        return None


def exact_scale(scale: float) -> float:
    """sway keeps the scale as a C float: 1.3 comes back as 1.2999999523162842,
    which would put logical 100 at physical 129.99999. It sets scales in
    steps of 1/120 (wp_fractional_scale's unit; 1.33 becomes 4/3), so snap to
    the step when that is what it is."""
    step = round(scale * _STEPS) / _STEPS
    return step if abs(step - scale) < _SNAP else round(scale, 6)


def _recv(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("sway closed the IPC socket")
        buf += chunk
    return buf
