"""Webcam mirror: the preview's mirrored style flips the picture left to
right, and the settings file keeps both mirror switches."""

import subprocess
import time
from pathlib import Path

from gi.repository import Gdk, GLib

import gtk_widgets.widgets.webcam.main as webcam_main
from gtk_widgets.lib.ui.widget_base import Gtk, install_css, load_css
from gtk_widgets.widgets.webcam import settings
from gtk_widgets.widgets.webcam.main import MIRRORED
from gtk_widgets.widgets.webcam.parse import Settings

RED = (255, 0, 0)
BLUE = (0, 0, 255)
SIZE = 40
WAIT_S = 5
EDGE_PX = 20  # past sway's window border


def _picture() -> Gdk.Texture:
    """Left half red, right half blue."""
    row = bytes(RED) * (SIZE // 2) + bytes(BLUE) * (SIZE // 2)
    return Gdk.MemoryTexture.new(
        SIZE,
        SIZE,
        Gdk.MemoryFormat.R8G8B8,
        GLib.Bytes.new(row * SIZE),
        SIZE * 3,
    )


def _settle(window: Gtk.Window) -> None:
    """Run the main loop until the window has drawn twice: a style
    change applies at the next allocation."""
    frames = window.get_frame_clock()
    assert frames is not None
    start = frames.get_frame_counter()
    deadline = time.monotonic() + WAIT_S
    while frames.get_frame_counter() < start + 2 and time.monotonic() < deadline:
        window.queue_draw()
        _ = GLib.MainContext.default().iteration(may_block=False)


def _left_pixel(shot: Path) -> tuple[int, int, int]:
    """A pixel near the screen's left edge, halfway down: inside the
    picture, at the window's left (sway tiles it over the screen)."""
    _ = subprocess.run(["grim", str(shot)], check=True)
    texture = Gdk.Texture.new_from_filename(str(shot))
    downloader = Gdk.TextureDownloader.new(texture)
    downloader.set_format(Gdk.MemoryFormat.R8G8B8)
    pixels, stride = downloader.download_bytes()
    data = pixels.get_data() or b""
    at = texture.get_height() // 2 * stride + EDGE_PX * 3
    r, g, b = data[at : at + 3]
    return (r, g, b)


def test_mirrored_preview_shows_the_left_half_on_the_right(tmp_path: Path) -> None:
    install_css(load_css(Path(webcam_main.__file__).with_name("style.css")))
    picture = Gtk.Picture(
        paintable=_picture(), can_shrink=True, content_fit=Gtk.ContentFit.FILL
    )
    picture.set_size_request(SIZE, SIZE)
    preview = Gtk.Box()
    preview.add_css_class("preview")
    preview.append(picture)
    window = Gtk.Window(child=preview)
    window.present()
    deadline = time.monotonic() + WAIT_S
    while not window.get_mapped() and time.monotonic() < deadline:
        _ = GLib.MainContext.default().iteration(may_block=False)
    try:
        _settle(window)
        assert _left_pixel(tmp_path / "plain.png") == RED
        picture.add_css_class(MIRRORED)
        _settle(window)
        assert _left_pixel(tmp_path / "mirrored.png") == BLUE
    finally:
        window.destroy()


def test_mirror_switches_are_saved_and_read_back(tmp_path: Path) -> None:
    path = tmp_path / "webcam.json"
    settings.save(Settings(mirror_preview=True, mirror_output=True), path)
    loaded = settings.load(path)
    assert isinstance(loaded, Settings)
    assert (loaded.mirror_preview, loaded.mirror_output) == (True, True)
