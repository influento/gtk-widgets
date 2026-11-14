"""Output scales and window rectangles from sway's IPC socket (stdlib, a few ms).

The exact fractional scale per output is what the selection maths needs.
GDK's Gdk.Monitor.get_scale() is physical height / logical height (1600 /
1230 = 1.3008 on a 3840x1600 output at 1.3), which puts the far edge 2 px
off; the surface's wp_fractional_scale is rounded to 1/120.
"""

import json
import os
import socket
import struct

_MAGIC = b"i3-ipc"
_GET_OUTPUTS = 3
_GET_TREE = 4


def output_scales():
    """{output name: scale} of the active outputs, or {} without sway."""
    return {name: o.scale for name, o in outputs().items()}


class Output:
    """An active output as sway lays it out: rect is (x, y, w, h) in logical
    (layout) pixels, transform sway's name for it ("normal", "90", ...)."""

    def __init__(self, raw):
        self.name = raw["name"]
        self.scale = exact_scale(float(raw["scale"]))
        r = raw["rect"]
        self.rect = (r["x"], r["y"], r["width"], r["height"])
        self.transform = raw.get("transform", "normal")


def outputs():
    """{output name: Output} of the active outputs, or {} without sway."""
    raw = _query(_GET_OUTPUTS)
    if raw is None:
        return {}
    return {o["name"]: Output(o) for o in raw if o.get("active") and o.get("scale", 0) > 0}


def windows():
    """{output name: [(x, y, w, h), ...]}: the windows shown on each output,
    topmost first, as logical rectangles relative to the output (not
    clipped: one that runs past the output's edge also covers the strip of
    physical pixels past its last whole logical pixel). A rectangle is the window's content: no sway border or title bar,
    no client-side shadow (sway's window_rect is the xdg geometry). Popups
    (menus, tooltips) are not in the tree. {} without sway."""
    tree = _query(_GET_TREE)
    if tree is None:
        return {}
    found = {}
    for output in tree.get("nodes", []):
        if output.get("type") != "output" or output.get("name", "").startswith("__"):
            continue
        o = output["rect"]
        box = (o["x"], o["y"], o["width"], o["height"])
        fullscreen, floating, tiled = [], [], []
        for ws in output.get("nodes", []):
            # workspaces in the tree carry no "visible"; the output names its own
            if ws.get("type") != "workspace" or ws.get("name") != output.get("current_workspace"):
                continue
            for node in ws.get("nodes", []):
                _views(node, tiled, fullscreen)
            # floating_nodes are in stacking order, the top one last
            for node in reversed(ws.get("floating_nodes", [])):
                _views(node, floating, fullscreen)
        rects = []
        for view in fullscreen or floating + tiled:
            x, y, w, h = _content(view)
            if x < box[0] + box[2] and y < box[1] + box[3] and x + w > box[0] and y + h > box[1]:
                rects.append((x - box[0], y - box[1], w, h))
        found[output["name"]] = rects
    return found


def _views(node, into, fullscreen):
    """Append the shown views under node to into (fullscreen ones to fullscreen)."""
    if "shell" in node:  # a view
        if node.get("visible"):
            (fullscreen if node.get("fullscreen_mode") else into).append(node)
        return
    for child in node.get("nodes", []):
        _views(child, into, fullscreen)
    for child in reversed(node.get("floating_nodes", [])):
        _views(child, into, fullscreen)


def _content(view):
    """The view's content in layout coordinates: window_rect is relative to
    its container's rect (which takes in the border and title bar)."""
    r, w = view["rect"], view.get("window_rect") or {}
    if not w.get("width") or not w.get("height"):
        return r["x"], r["y"], r["width"], r["height"]
    return r["x"] + w["x"], r["y"] + w["y"], w["width"], w["height"]


def _query(kind):
    """sway's JSON reply to an empty message of this type, or None."""
    path = os.environ.get("SWAYSOCK")
    if not path:
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            sock.connect(path)
            sock.sendall(_MAGIC + struct.pack("=II", 0, kind))
            header = _recv(sock, 14)
            (length,) = struct.unpack_from("=I", header, 6)
            return json.loads(_recv(sock, length))
    except (OSError, ValueError):
        return None


def exact_scale(scale):
    """sway keeps the scale as a C float: 1.3 comes back as 1.2999999523162842,
    which would put logical 100 at physical 129.99999. It sets scales in
    steps of 1/120 (wp_fractional_scale's unit; 1.33 becomes 4/3), so snap to
    the step when that is what it is."""
    step = round(scale * 120) / 120
    return step if abs(step - scale) < 1e-5 else round(scale, 6)


def _recv(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("sway closed the IPC socket")
        buf += chunk
    return buf
