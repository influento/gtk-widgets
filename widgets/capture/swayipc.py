"""Output scales from sway's IPC socket (stdlib, a few ms).

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


def output_scales():
    """{output name: scale} of the active outputs, or {} without sway."""
    path = os.environ.get("SWAYSOCK")
    if not path:
        return {}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            sock.connect(path)
            sock.sendall(_MAGIC + struct.pack("=II", 0, _GET_OUTPUTS))
            header = _recv(sock, 14)
            (length,) = struct.unpack_from("=I", header, 6)
            outputs = json.loads(_recv(sock, length))
    except (OSError, ValueError):
        return {}
    return {o["name"]: exact_scale(float(o["scale"])) for o in outputs
            if o.get("active") and o.get("scale", 0) > 0}


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
