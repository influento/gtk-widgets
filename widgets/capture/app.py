"""Region picker over the frozen frames: one overlay per output; and the
indicator shown while capture gif records.

Each output gets a layer-shell surface on the OVERLAY layer, covering the
whole output (bars too) and taking the keyboard, that shows the frame
grabbed before anything of ours mapped, dimmed outside the selection. A drag
selects and releasing commits; Esc or a right click cancels. The selection
stays on the output the drag started on (outputs can differ in scale).

The indicator is another OVERLAY surface over the recorded output that takes
no keyboard and no pointer (empty input region), so the app being recorded
keeps both. It draws a frame just outside the recorded pixels and the
elapsed time beside it; wf-recorder crops its buffer to the selection, so
neither is in the recording.
"""

import math
import os
import signal
import sys
import threading
import time

_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import (Gdk, Gtk, Gtk4LayerShell, install_css, load_css,  # noqa: E402
                             render_css)
import cairo  # noqa: E402
from gi.repository import Gio, GLib, Graphene, Gsk  # noqa: E402

import geometry  # noqa: E402
import image  # noqa: E402

APP_ID = "dev.dotfiles.capture"
FRAME_WIDTH = 2  # logical px, drawn outside the selected pixels
LABEL_GAP = 6  # logical px between the indicator's frame and its label
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


def wait_unmapped():
    """Block until the compositor has handled the picker's unmap (a
    roundtrip); the next frame it renders is without it."""
    Gdk.Display.get_default().sync()


class FrameView(Gtk.Widget):
    """The recording frame, FRAME_WIDTH wide, just outside rect (physical
    pixels): its inner edges fall on the pixel edges around the selection. A
    side past the output's edge is clipped away with the surface."""

    def __init__(self, rect, scale):
        super().__init__(can_target=False)
        self.rect = rect
        self.scale = scale
        self.add_css_class("capture-frame")

    def logical(self):
        """rect in the surface's coordinates, and how far out the frame starts.
        The surface draws at the output's scale when the compositor sends it
        (wp_fractional_scale); otherwise it is resampled, so the frame keeps a
        logical pixel away from the recorded ones."""
        surface = self.get_native().get_surface() if self.get_native() else None
        exact = surface is None or abs(surface.get_scale() - self.scale) < 1e-3
        return geometry.to_logical(self.rect, self.scale), 0 if exact else 1

    def do_snapshot(self, snapshot):
        (x, y, w, h), gap = self.logical()
        f = FRAME_WIDTH
        x, y, w, h = x - gap, y - gap, w + 2 * gap, h + 2 * gap
        color = self.get_color()
        for r in ((x - f, y - f, w + 2 * f, f), (x - f, y + h, w + 2 * f, f),
                  (x - f, y, f, h), (x + w, y, f, h)):
            snapshot.append_color(color, _rect(*r))


def label_position(rect, size, label, frame):
    """Where a label of size (w, h) goes around rect (x, y, w, h), all
    logical, on a surface of size: below, above, right or left of the frame
    (frame px outside rect), LABEL_GAP further out, whole pixels, inside the
    surface. None when there is no room anywhere."""
    x, y, w, h = rect
    lw, lh = label
    sw, sh = size
    out = frame + LABEL_GAP
    left = max(0, min(math.floor(x), sw - lw))
    top = max(0, min(math.floor(y), sh - lh))
    for lx, ly in ((left, math.ceil(y + h + out)), (left, math.floor(y - out - lh)),
                   (math.ceil(x + w + out), top), (math.floor(x - out - lw), top)):
        if 0 <= lx and lx + lw <= sw and 0 <= ly and ly + lh <= sh:
            return lx, ly
    return None


class Recording(Gtk.Application):
    """The indicator while recorder runs. SIGUSR1 or the MAX_SECONDS cap
    stop it and run work() in a thread with "Processing…" shown; SIGUSR2,
    SIGINT and SIGTERM cancel. outcome: "stopped" (result is work()'s),
    "cancelled", or "failed" (wf-recorder exited by itself)."""

    def __init__(self, output, rect, scale, recorder, max_seconds, work, on_started,
                 on_stopped):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.output = output
        self.rect = rect
        self.scale = scale
        self.recorder = recorder
        self.max_seconds = max_seconds
        self.work = work
        self.on_started = on_started
        self.on_stopped = on_stopped
        self.outcome = None
        self.result = None
        self.win = None
        self._state = "recording"
        self._t0 = None

    def do_activate(self):
        if self.win:
            return
        install_css(render_css(_CSS) + load_css(os.path.join(_DIR, "style.css")))
        monitors = Gdk.Display.get_default().get_monitors()
        monitor = None
        for i in range(monitors.get_n_items()):
            if monitors.get_item(i).get_connector() == self.output:
                monitor = monitors.get_item(i)
        if monitor is None and monitors.get_n_items() == 1:
            monitor = monitors.get_item(0)
        self.win = self._window(monitor)
        for signum, cancel in ((signal.SIGUSR1, False), (signal.SIGUSR2, True),
                               (signal.SIGINT, True), (signal.SIGTERM, True)):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signum, self._on_signal, cancel)
        self._t0 = time.monotonic()
        self._tick()
        GLib.timeout_add(200, self._tick)
        self.win.present()
        self.on_started()

    def _window(self, monitor):
        win = Gtk.ApplicationWindow(application=self, title=APP_ID)
        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_namespace(win, "capture-indicator")
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        if monitor is not None:
            Gtk4LayerShell.set_monitor(win, monitor)
        for edge in (Gtk4LayerShell.Edge.TOP, Gtk4LayerShell.Edge.BOTTOM,
                     Gtk4LayerShell.Edge.LEFT, Gtk4LayerShell.Edge.RIGHT):
            Gtk4LayerShell.set_anchor(win, edge, True)
        Gtk4LayerShell.set_exclusive_zone(win, -1)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)
        win.set_can_target(False)
        # Clicks go through to whatever is below
        win.connect("realize", lambda w: w.get_surface().set_input_region(cairo.Region()))

        self.frame = FrameView(self.rect, self.scale)
        self.label = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.START,
                               can_target=False)
        self.label.add_css_class("capture-badge")
        overlay = Gtk.Overlay(child=self.frame)
        overlay.add_overlay(self.label)
        win.set_child(overlay)
        geo = monitor.get_geometry() if monitor is not None else None
        self._size = (geo.width, geo.height) if geo else None
        return win

    def _set_label(self, text):
        if self.label.get_label() == text:
            return
        self.label.set_label(text)
        self.label.set_visible(True)
        size = self._size or (self.frame.get_width(), self.frame.get_height())
        # measure() counts the margins that place the label
        lw = self.label.measure(Gtk.Orientation.HORIZONTAL, -1)[1] - self.label.get_margin_start()
        lh = self.label.measure(Gtk.Orientation.VERTICAL, -1)[1] - self.label.get_margin_top()
        rect, gap = self.frame.logical()
        pos = label_position(rect, size, (lw, lh), FRAME_WIDTH + gap)
        if pos is None:
            self.label.set_visible(False)
        else:
            self.label.set_margin_start(pos[0])
            self.label.set_margin_top(pos[1])

    def _tick(self):
        if self._state != "recording":
            return False
        if self.recorder.exited():
            self.outcome = "failed"
            self._state = "failed"
            self.on_stopped()
            self.quit()
            return False
        elapsed = time.monotonic() - self._t0
        if elapsed >= self.max_seconds:
            self._stop(False)
            return False
        self._set_label(f"{_clock(elapsed)} / {_clock(self.max_seconds)}")
        return True

    def _on_signal(self, cancel):
        self._stop(cancel)
        return True  # keep catching: a second press must not kill us

    def _stop(self, cancel):
        if self._state != "recording":
            return
        self._state = "cancelled" if cancel else "processing"
        self.on_stopped()
        if cancel:
            self.win.set_visible(False)
        else:
            self.frame.add_css_class("processing")
            self._set_label("Processing…")
        threading.Thread(target=self._finish, args=(cancel,), daemon=True).start()

    def _finish(self, cancel):
        result = None
        try:
            self.recorder.stop()
            if not cancel:
                result = self.work()
        except Exception as e:  # the indicator must go away whatever happens
            result = e
        GLib.idle_add(self._done, "cancelled" if cancel else "stopped", result)

    def _done(self, outcome, result):
        self.outcome = outcome
        self.result = result
        self.quit()
        return False


def _clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def record(output, rect, scale, recorder, max_seconds, work, on_started, on_stopped):
    """Run the indicator (see Recording). Returns (outcome, work()'s result);
    the indicator is off the screen when it returns."""
    app = Recording(output, rect, scale, recorder, max_seconds, work, on_started, on_stopped)
    app.run([sys.argv[0]])
    if app.win is not None:
        app.win.set_visible(False)
    Gdk.Display.get_default().sync()
    return app.outcome, app.result
