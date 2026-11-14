"""Selection maths between surface (logical) and buffer (physical) pixels.

No GTK here, so it can be tested on its own. The compositor puts logical
coordinate x at physical x * scale, with the output's exact fractional scale.
A selection covers every physical pixel under the two corners the pointer
was at, both included, so a drag to the far edge of the output reaches its
last pixel. Nothing is scaled: a selection is whole physical pixels, and the
preview shows those same pixels.
"""

import math
import struct

# A logical coordinate times the scale can land a hair below the pixel edge
# it stands for (x = 10 at 1.3 gives 12.999999999999998 or 13.000000000000002)
_EPS = 1e-6


def pixel_at(pos, scale):
    """The physical pixel under logical coordinate pos."""
    return math.floor(pos * scale + _EPS)


def selection(start, end, scale, surface_size, buffer_size):
    """The physical rectangle (x, y, w, h) between two logical points.

    Points outside the surface (a drag carried onto another output) are
    clamped to it. surface_size is the output's logical size, buffer_size
    the frame's physical size. The strip a fractional scale leaves past the
    logical edge (the last physical column of a 3840 px output at 1.3 shows
    no surface) is out of reach, like on screen."""
    rect = []
    for axis in (0, 1):
        # The pixel under the last logical position before the edge
        last = min(math.ceil(surface_size[axis] * scale - _EPS) - 1, buffer_size[axis] - 1)
        a = min(max(pixel_at(start[axis], scale), 0), last)
        b = min(max(pixel_at(end[axis], scale), 0), last)
        rect.append((min(a, b), abs(a - b) + 1))
    (x, w), (y, h) = rect
    return x, y, w, h


def _f32(x):
    """x rounded to a C float."""
    return struct.unpack("=f", struct.pack("=f", x))[0]


def _device(v, scale):
    """Where wlroots' scene puts logical coordinate v on the output
    (scale_box(): the int times the float scale in single precision, C
    round(), halves away from zero)."""
    p = _f32(_f32(v) * _f32(scale))
    return math.floor(abs(p) + 0.5) * (1 if p >= 0 else -1)


def placed(rect, scale, buffer_size):
    """The physical pixels a logical rectangle (x, y, w, h) of the layout
    (a window, output-local) is drawn on, clipped to the buffer: both edges
    are rounded, so neighbours share no pixel and leave no gap. None when
    nothing of it is on the buffer."""
    x, y, w, h = rect
    x0, y0 = max(_device(x, scale), 0), max(_device(y, scale), 0)
    x1 = min(_device(x + w, scale), buffer_size[0])
    y1 = min(_device(y + h, scale), buffer_size[1])
    return (x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


def to_logical(rect, scale):
    """A physical rectangle in logical coordinates (fractional), for drawing."""
    return tuple(v / scale for v in rect)


def loupe_place(pointer, size, surface, gap):
    """Top-left (logical) of a box of size (w, h) beside pointer: gap below
    and right of it, on the other side of the pointer on an axis where it
    would leave the surface, then kept inside it. It never covers the
    pointer unless the surface is too small to hold it anywhere else."""
    place = []
    for p, s, total in zip(pointer, size, surface):
        v = p + gap
        if v + s > total:
            v = p - gap - s
        place.append(min(max(v, 0), max(total - s, 0)))
    return tuple(place)
