"""Region picker over the frozen frames: one overlay per output.

Each output gets a layer-shell surface on the OVERLAY layer, covering the
whole output (bars too) and taking the keyboard, that shows the frame
grabbed before anything of ours mapped, dimmed outside the selection. A drag
selects and releasing commits; Esc or a right click cancels. The selection
stays on the output the drag started on (outputs can differ in scale).
"""

import os
import sys
import time

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import (Gdk, Gtk, Gtk4LayerShell, install_css, load_css,  # noqa: E402
                             render_css)
from gi.repository import Gio, Graphene, Gsk  # noqa: E402

import geometry  # noqa: E402
import image  # noqa: E402

APP_ID = "dev.dotfiles.capture"
FRAME_WIDTH = 2  # logical px, drawn outside the selected pixels
_CSS = """
window {
  background-color: transparent;
}
"""


class Canvas(Gtk.Widget):
    """The frozen frame, the shade and the selection frame, in one snapshot."""

    def __init__(self, picture, scale, shade_probe):
        super().__init__()
        self.picture = picture
        self._scale = scale
        self.rect = None  # the selection in physical pixels
        self._shade_probe = shade_probe
        self.add_css_class("capture-canvas")
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair"))

    @property
    def scale(self):
        """The output's scale: sway's, else the surface's wp_fractional_scale
        (exact in 1/120 steps; Gdk.Monitor.get_scale() is a ratio of rounded
        sizes, see swayipc.py)."""
        if self._scale:
            return self._scale
        surface = self.get_native().get_surface()
        return surface.get_scale() if surface else 1

    def do_snapshot(self, snapshot):
        w, h = self.get_width(), self.get_height()
        pic = self.picture
        # Texture pixel k lands on device pixel k when GTK renders at the
        # output's scale (checked by screencopy at 1.25, 1.3, 1.5), provided
        # the texture is drawn at its own size under a 1/scale transform: into
        # a rectangle of the logical size GTK 4.22 resamples it. Otherwise the
        # preview is soft; the saved image never comes from it.
        surface = self.get_native().get_surface()
        filt = (Gsk.ScalingFilter.NEAREST
                if surface and abs(surface.get_scale() - self.scale) < 1e-3
                else Gsk.ScalingFilter.LINEAR)
        snapshot.save()
        snapshot.scale(1 / self.scale, 1 / self.scale)
        snapshot.append_scaled_texture(pic.texture, filt, _rect(0, 0, pic.width, pic.height))
        snapshot.restore()

        shade = self._shade_probe.get_color()
        if self.rect is None:
            snapshot.append_color(shade, _rect(0, 0, w, h))
            return
        x, y, sw, sh = geometry.to_logical(self.rect, self.scale)
        for r in ((0, 0, w, y), (0, y + sh, w, h - y - sh),
                  (0, y, x, sh), (x + sw, y, w - x - sw, sh)):
            if r[2] > 0 and r[3] > 0:
                snapshot.append_color(shade, _rect(*r))
        f = FRAME_WIDTH
        outline = Gsk.RoundedRect()
        outline.init_from_rect(_rect(x - f, y - f, sw + 2 * f, sh + 2 * f), 0)
        color = self.get_color()
        snapshot.append_border(outline, [f] * 4, [color] * 4)


def _rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


class Picker(Gtk.Application):
    """Shows one overlay per frame; result is (Picture, (x, y, w, h)) or None."""

    def __init__(self, frames, scales, t0=None):
        # One at a time is main.py's lock; no D-Bus name to wait for
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.frames = frames
        self.scales = scales
        self.t0 = t0
        self.result = None
        self.windows = []
        self._active = None  # the Canvas a drag started on
        self._start = None

    def do_activate(self):
        if self.windows:
            return
        install_css(render_css(_CSS) + load_css(os.path.join(_DIR, "style.css")))
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        by_name = {monitors.get_item(i).get_connector(): monitors.get_item(i)
                   for i in range(monitors.get_n_items())}
        for frame in self.frames:
            monitor = by_name.get(frame.output.name)
            if monitor is None and len(self.frames) == 1 and len(by_name) == 1:
                monitor = next(iter(by_name.values()))
            if monitor is None:
                print(f"capture: no monitor for output {frame.output.name!r}", file=sys.stderr)
                continue
            self.windows.append(self._window(frame, monitor))
        if not self.windows:
            self.quit()
            return
        if self.t0:
            self._trace(self.windows[0])
        for win in self.windows:
            win.present()

    def _window(self, frame, monitor):
        picture = image.upright(frame)
        scale = self.scales.get(frame.output.name)

        win = Gtk.ApplicationWindow(application=self, title=APP_ID)
        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_namespace(win, "capture")
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_monitor(win, monitor)
        for edge in (Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                     Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT):
            Gtk4LayerShell.set_anchor(win, edge, True)
        Gtk4LayerShell.set_exclusive_zone(win, -1)  # over the bar, at the output's origin
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)

        # A widget that is never drawn, for the shade colour from style.css
        shade_probe = Gtk.Box(can_target=False, halign=Gtk.Align.START,
                              valign=Gtk.Align.START)
        shade_probe.add_css_class("capture-shade")
        canvas = Canvas(picture, scale, shade_probe)
        overlay = Gtk.Overlay(child=canvas)
        overlay.add_overlay(shade_probe)
        win.set_child(overlay)

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._drag_begin, canvas)
        drag.connect("drag-update", self._drag_update, canvas)
        drag.connect("drag-end", self._drag_end, canvas)
        canvas.add_controller(drag)
        cancel = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        cancel.connect("pressed", lambda *_: self.quit())
        canvas.add_controller(cancel)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        win.add_controller(keys)
        return win

    def _on_key(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def _select(self, canvas, end):
        pic = canvas.picture
        canvas.rect = geometry.selection(self._start, end, canvas.scale,
                                         (canvas.get_width(), canvas.get_height()),
                                         (pic.width, pic.height))
        canvas.queue_draw()

    def _drag_begin(self, _gesture, x, y, canvas):
        if self._active is not None and self._active is not canvas:
            return
        self._active = canvas
        self._start = (x, y)
        self._select(canvas, (x, y))

    def _drag_update(self, _gesture, dx, dy, canvas):
        if self._active is canvas:
            self._select(canvas, (self._start[0] + dx, self._start[1] + dy))

    def _drag_end(self, _gesture, dx, dy, canvas):
        if self._active is not canvas:
            return
        if dx == 0 and dy == 0:  # a click, not a drag: start over
            self._active = canvas.rect = None
            canvas.queue_draw()
            return
        self._select(canvas, (self._start[0] + dx, self._start[1] + dy))
        self.result = (canvas.picture, canvas.rect)
        # Off the screen now: the PNG is written after the overlays are gone
        for win in self.windows:
            win.set_visible(False)
        self.quit()

    def _trace(self, win):
        """Print the time from t0 (ns since the epoch) to the first frame."""
        handler = None

        def painted(clock):
            clock.disconnect(handler)
            print(f"capture: frozen frame painted {(time.time_ns() - self.t0) / 1e6:.1f} ms"
                  " after launch", file=sys.stderr, flush=True)

        def realized(w):
            nonlocal handler
            handler = w.get_frame_clock().connect("after-paint", painted)
        win.connect("realize", realized)


def pick_region(frames, scales, t0=None):
    """Run the picker. Returns (Picture, (x, y, w, h)) or None if cancelled."""
    app = Picker(frames, scales, t0)
    app.run([sys.argv[0]])
    Gdk.Display.get_default().flush()  # the unmap goes out before the save
    return app.result
