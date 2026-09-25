"""Frozen frames as the user sees them, and lossless crops saved as PNG.

The pixels are never scaled: a frame is turned upright by whole-pixel
flips and quarter turns only, a crop is a slice of its rows, and the PNG
encoder gets those bytes as they are.
"""

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402

import screencopy  # noqa: E402

_MEMORY_FORMATS = {
    "BGRA": Gdk.MemoryFormat.B8G8R8X8,  # an output's alpha means nothing: opaque
    "BGRX": Gdk.MemoryFormat.B8G8R8X8,
    "RGBA": Gdk.MemoryFormat.R8G8B8X8,
    "RGBX": Gdk.MemoryFormat.R8G8B8X8,
}

# wl_output.transform -> (flip around the vertical axis first, then turn the
# picture this many degrees counter-clockwise): the inverse of the transform,
# which turns the buffer into the picture on screen (checked against grim)
_UPRIGHT = {
    0: (False, 0), 1: (False, 270), 2: (False, 180), 3: (False, 90),
    4: (True, 0), 5: (True, 90), 6: (True, 180), 7: (True, 270),
}
_ROTATIONS = {
    90: GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE,
    180: GdkPixbuf.PixbufRotation.UPSIDEDOWN,
    270: GdkPixbuf.PixbufRotation.CLOCKWISE,
}


class Picture:
    """An output's frozen frame, upright: rows of stride bytes in a
    GdkMemoryFormat, width x height physical pixels."""

    def __init__(self, output, data, width, height, stride, fmt, bpp):
        self.output = output
        self.data = data
        self.width = width
        self.height = height
        self.stride = stride
        self.format = fmt
        self.bpp = bpp
        self._texture = None

    @property
    def texture(self):
        if self._texture is None:
            self._texture = Gdk.MemoryTexture.new(
                self.width, self.height, self.format, GLib.Bytes.new(self.data), self.stride)
        return self._texture

    def crop(self, x, y, w, h):
        """The w x h rectangle at (x, y) as a texture of its own. It shares the
        rows' stride, so it is one contiguous slice of the frame's bytes."""
        if not (0 <= x and 0 <= y and w > 0 and h > 0
                and x + w <= self.width and y + h <= self.height):
            raise ValueError(f"crop {w}x{h}+{x}+{y} outside {self.width}x{self.height}")
        start = y * self.stride + x * self.bpp
        end = start + (h - 1) * self.stride + w * self.bpp
        return Gdk.MemoryTexture.new(w, h, self.format, GLib.Bytes.new(self.data[start:end]),
                                     self.stride)


def upright(frame):
    """Picture of a screencopy.Frame with y_invert and the output transform
    applied. A normal output keeps the compositor's bytes untouched."""
    fmt = _MEMORY_FORMATS[screencopy.SHM_FORMATS[frame.format][1]]
    flip, turn = _UPRIGHT.get(frame.output.transform, (False, 0))
    if not (frame.y_invert or flip or turn):
        return Picture(frame.output, frame.data, frame.width, frame.height, frame.stride, fmt, 4)
    # Lossless flips and quarter turns go through GdkPixbuf, which wants RGB
    tex = Gdk.MemoryTexture.new(frame.width, frame.height, fmt, GLib.Bytes.new(frame.data),
                                frame.stride)
    down = Gdk.TextureDownloader.new(tex)
    down.set_format(Gdk.MemoryFormat.R8G8B8)
    rgb, stride = down.download_bytes()
    pb = GdkPixbuf.Pixbuf.new_from_bytes(rgb, GdkPixbuf.Colorspace.RGB, False, 8,
                                         frame.width, frame.height, stride)
    if frame.y_invert:
        pb = pb.flip(False)
    if flip:
        pb = pb.flip(True)
    if turn:
        pb = pb.rotate_simple(_ROTATIONS[turn])
    return Picture(frame.output, pb.read_pixel_bytes().get_data(), pb.get_width(),
                   pb.get_height(), pb.get_rowstride(), Gdk.MemoryFormat.R8G8B8, 3)


def save_png(texture, path):
    if not texture.save_to_png(path):
        raise OSError(f"could not write {path}")
