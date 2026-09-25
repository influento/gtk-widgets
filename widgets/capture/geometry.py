"""Selection maths between surface (logical) and buffer (physical) pixels.

No GTK here, so it can be tested on its own. The compositor puts logical
coordinate x at physical x * scale, with the output's exact fractional scale.
A selection covers every physical pixel under the two corners the pointer
was at, both included, so a drag to the far edge of the output reaches its
last pixel. Nothing is scaled: a selection is whole physical pixels, and the
preview shows those same pixels.
"""

import math

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


def to_logical(rect, scale):
    """A physical rectangle in logical coordinates (fractional), for drawing."""
    return tuple(v / scale for v in rect)
