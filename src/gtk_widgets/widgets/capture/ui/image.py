"""Frozen frames as the user sees them, and lossless crops saved as PNG.

The pixels are never scaled: a frame is turned upright by whole-pixel
flips and quarter turns only, a crop is a slice of its rows, and the PNG
encoder gets those bytes as they are.
"""

from gi.repository import Gdk, GdkPixbuf, GLib

from gtk_widgets.widgets.capture import screencopy

_MEMORY_FORMATS = {
    "BGRA": Gdk.MemoryFormat.B8G8R8X8,  # an output's alpha means nothing: opaque
    "BGRX": Gdk.MemoryFormat.B8G8R8X8,
    "RGBA": Gdk.MemoryFormat.R8G8B8X8,
    "RGBX": Gdk.MemoryFormat.R8G8B8X8,
}

# wl_output.transform -> (flip around the vertical axis first, then turn the
# picture this many degrees counter-clockwise): the inverse of the transform,
# which turns the buffer into the picture on screen (checked on a headless
# sway in all eight transforms)
_UPRIGHT = {
    0: (False, 0),
    1: (False, 270),
    2: (False, 180),
    3: (False, 90),
    4: (True, 0),
    5: (True, 90),
    6: (True, 180),
    7: (True, 270),
}
_BPP_SHM = 4  # the screencopy formats: 4 bytes a pixel
_BPP_RGB = 3  # GdkPixbuf's RGB without alpha
_ROTATIONS = {
    90: GdkPixbuf.PixbufRotation.COUNTERCLOCKWISE,
    180: GdkPixbuf.PixbufRotation.UPSIDEDOWN,
    270: GdkPixbuf.PixbufRotation.CLOCKWISE,
}


class Picture:
    """An output's frozen frame, upright: rows of stride bytes in a
    GdkMemoryFormat, width x height physical pixels."""

    def __init__(
        self,
        output: screencopy.Output,
        data: bytes,
        size: tuple[int, int],
        stride: int,
        fmt: Gdk.MemoryFormat,
        *,
        bpp: int,
    ) -> None:
        self.output = output
        self.data = data
        self.width, self.height = size
        self.stride = stride
        self.format = fmt
        self.bpp = bpp  # bytes per pixel
        self._texture: Gdk.Texture | None = None

    @property
    def texture(self) -> Gdk.Texture:
        if self._texture is None:
            self._texture = Gdk.MemoryTexture.new(
                self.width,
                self.height,
                self.format,
                GLib.Bytes.new(self.data),
                self.stride,
            )
        return self._texture

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        """(r, g, b) of the pixel at (x, y)."""
        i = y * self.stride + x * self.bpp
        a, b, c = self.data[i : i + 3]
        return (c, b, a) if self.format == Gdk.MemoryFormat.B8G8R8X8 else (a, b, c)

    def crop(self, x: int, y: int, w: int, h: int) -> Gdk.Texture:
        """The w x h rectangle at (x, y) as a texture of its own. It shares the
        rows' stride, so it is one contiguous slice of the frame's bytes."""
        if not (
            x >= 0
            and y >= 0
            and w > 0
            and h > 0
            and x + w <= self.width
            and y + h <= self.height
        ):
            raise ValueError(f"crop {w}x{h}+{x}+{y} outside {self.width}x{self.height}")
        start = y * self.stride + x * self.bpp
        end = start + (h - 1) * self.stride + w * self.bpp
        return Gdk.MemoryTexture.new(
            w, h, self.format, GLib.Bytes.new(self.data[start:end]), self.stride
        )


def upright(frame: screencopy.Frame) -> Picture:
    """Picture of a screencopy.Frame with y_invert and the output transform
    applied. A normal output keeps the compositor's bytes untouched."""
    fmt = _MEMORY_FORMATS[screencopy.SHM_FORMATS[frame.format][1]]
    flip, turn = _UPRIGHT.get(frame.output.transform, (False, 0))
    if not (frame.y_invert or flip or turn):
        return Picture(
            frame.output,
            frame.data,
            (frame.width, frame.height),
            frame.stride,
            fmt,
            bpp=_BPP_SHM,
        )
    # Lossless flips and quarter turns go through GdkPixbuf, which wants RGB
    tex = Gdk.MemoryTexture.new(
        frame.width, frame.height, fmt, GLib.Bytes.new(frame.data), frame.stride
    )
    down = Gdk.TextureDownloader.new(tex)
    down.set_format(Gdk.MemoryFormat.R8G8B8)
    rgb, stride = down.download_bytes()
    rgb_pb = GdkPixbuf.Pixbuf.new_from_bytes(
        rgb,
        GdkPixbuf.Colorspace.RGB,
        has_alpha=False,
        bits_per_sample=8,
        width=frame.width,
        height=frame.height,
        rowstride=stride,
    )
    pb = rgb_pb.flip(horizontal=False) if frame.y_invert else rgb_pb
    if pb is not None and flip:
        pb = pb.flip(horizontal=True)
    if pb is not None and turn:
        pb = pb.rotate_simple(_ROTATIONS[turn])
    if pb is None:  # GdkPixbuf's allocation failed
        raise MemoryError("GdkPixbuf could not turn the frame upright")
    return Picture(
        frame.output,
        pb.read_pixel_bytes().get_data() or b"",
        (pb.get_width(), pb.get_height()),
        pb.get_rowstride(),
        Gdk.MemoryFormat.R8G8B8,
        bpp=_BPP_RGB,
    )


def save_png(texture: Gdk.Texture, path: str) -> None:
    if not texture.save_to_png(path):
        raise OSError(f"could not write {path}")
