"""Live camera preview: ffmpeg decodes small RGB frames on a pipe, shown as
textures in a Gtk.Picture."""

import contextlib
import subprocess
from collections import deque
from collections.abc import Callable
from pathlib import Path

from gi.repository import Gdk, GLib, GObject

from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.widget_base import Gtk
from gtk_widgets.widgets.webcam import links

WIDTH, HEIGHT = 640, 360
FPS = 15
FRAME_BYTES = WIDTH * HEIGHT * 3


def _ffmpeg(device: Path, *, camera: bool) -> list[str]:
    # The camera itself: its MJPEG mode at the preview's size (raw YUYV is
    # slow over USB). The engine's loopback: whatever it writes, scaled.
    source = (
        [
            "-input_format",
            "mjpeg",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            "30",
        ]
        if camera
        else []
    )
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
        *source,
        "-i",
        str(device),
        "-vf",
        f"fps={FPS},scale={WIDTH}:{HEIGHT}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
    ]


class Preview:
    """Frames from one device into `picture` until stop(); on_end(message)
    runs on the main thread when ffmpeg stops by itself."""

    def __init__(
        self,
        picture: Gtk.Picture,
        on_end: Callable[[str], None],
        on_bug: Callable[[str], bool | None],
    ) -> None:
        self._picture = picture
        self._on_end = on_end
        self._on_bug = on_bug
        self._proc: subprocess.Popen[bytes] | None = None

    def start(self, device: Path, *, camera: bool) -> None:
        self.stop()
        proc = subprocess.Popen(
            _ffmpeg(device, camera=camera),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._proc = proc
        in_background(lambda: self._read(proc), self._on_bug)
        in_background(lambda: self._watch(proc), self._on_bug)

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            proc.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                _ = proc.wait(2)
            if proc.poll() is None:
                proc.kill()
                _ = proc.wait()

    def _read(self, proc: subprocess.Popen[bytes]) -> None:
        out = proc.stdout
        if out is None:
            return
        while len(frame := out.read(FRAME_BYTES)) == FRAME_BYTES:
            _ = GLib.idle_add(self._show, proc, frame)

    def _watch(self, proc: subprocess.Popen[bytes]) -> None:
        """Drain ffmpeg's errors as they come (a full pipe would stop it) and
        report the last one when it exits."""
        last: deque[str] = deque(maxlen=1)
        if proc.stderr is not None:
            for raw in proc.stderr:
                if line := raw.decode(errors="replace").strip():
                    last.append(line)
        _ = proc.wait()
        _ = GLib.idle_add(self._ended, proc, last[0] if last else "no picture")

    def _show(self, proc: subprocess.Popen[bytes], frame: bytes) -> bool:
        if proc is self._proc:
            texture = Gdk.MemoryTexture.new(
                WIDTH,
                HEIGHT,
                Gdk.MemoryFormat.R8G8B8,
                GLib.Bytes.new(frame),
                WIDTH * 3,
            )
            self._picture.set_paintable(texture)
        return GLib.SOURCE_REMOVE

    def _ended(self, proc: subprocess.Popen[bytes], message: str) -> bool:
        if proc is self._proc:  # not stopped on purpose
            self._proc = None
            self._on_end(message)
        return GLib.SOURCE_REMOVE


class _Thumbnail(GObject.Object, Gdk.Paintable):
    """A texture that tells the picture its size request, not its pixels, as
    its size: a Gtk.Picture asks for its paintable's size, which would widen
    the popup by the texture's (larger, for a sharp thumbnail) one."""

    def __init__(self, texture: Gdk.Texture, width: int, height: int) -> None:
        super().__init__()
        self._texture = texture
        self._width = width
        self._height = height

    def do_get_intrinsic_width(self) -> int:
        return self._width

    def do_get_intrinsic_height(self) -> int:
        return self._height

    def do_get_flags(self) -> Gdk.PaintableFlags:
        return Gdk.PaintableFlags.CONTENTS | Gdk.PaintableFlags.SIZE

    def do_snapshot(self, snapshot: Gdk.Snapshot, width: float, height: float) -> None:
        self._texture.snapshot(snapshot, width, height)


def show_thumbnail(
    picture: Gtk.Picture,
    path: Path,
    scale: int,
    on_bug: Callable[[str], bool | None],
) -> None:
    """An image's, a GIF's or video's first frame or a link's thumbnail in
    `picture`, filling its size request, decoded off the main thread at
    `scale` times that size (a small texture, not a whole picture in
    memory); nothing when it cannot be read."""
    size = picture.get_size_request()
    width, height = (n * scale for n in size)

    def load() -> None:
        source = links.thumbnail(path) if links.is_link(path) else path
        if source is None:
            return
        done = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vf",
                (
                    f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}"
                ),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
        if done.returncode == 0 and len(done.stdout) == width * height * 3:
            texture = Gdk.MemoryTexture.new(
                width,
                height,
                Gdk.MemoryFormat.R8G8B8,
                GLib.Bytes.new(done.stdout),
                width * 3,
            )
            _ = GLib.idle_add(_show_texture, picture, _Thumbnail(texture, *size))

    in_background(load, on_bug)


def _show_texture(picture: Gtk.Picture, thumbnail: _Thumbnail) -> bool:
    picture.set_paintable(thumbnail)
    return GLib.SOURCE_REMOVE
