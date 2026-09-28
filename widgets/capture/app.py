"""Region picker over the frozen frames: one overlay per output; and the
indicator shown while capture gif records.

Each output gets a layer-shell surface on the OVERLAY layer, covering the
whole output (bars too) and taking the keyboard, that shows the frame
grabbed before anything of ours mapped, dimmed outside the selection. A drag
selects and releasing commits; Esc or a right click cancels. The selection
stays on the output the drag started on (outputs can differ in scale).
Before a drag the window under the pointer (sway's tree, fetched with the
frames) gets the selection frame, or the whole output where there is none
(the bar, the wallpaper), and the shade stays over everything: only a drag
cuts it away. A click (a press that moves less than CLICK_SLOP) takes it. The
Z key (the key, whatever the layout) turns a magnifier on and off: a loupe
beside the pointer with the physical pixels around it, the one under the
pointer outlined, and its position and colour below. It starts off.

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
LABEL_GAP = 6  # logical px between the indicator's frame (or the loupe) and its label
LOUPE_PIXELS = 13  # physical px across the loupe (odd: one in the middle)
LOUPE_CELL = 11  # logical px per physical px in the loupe, rounded to device px
LOUPE_GAP = 24  # logical px between the pointer and the loupe
LOUPE_RADIUS = 8
CLICK_SLOP = 3  # logical px a press may move and still be a click
_CSS = """
window {
  background-color: transparent;
}
"""


class Canvas(Gtk.Widget):
    """The frozen frame, the shade, the selection frame and the loupe, in one
    snapshot. readout is the label under the loupe (a sibling overlay)."""

    def __init__(self, picture, scale, shade_probe, readout):
        super().__init__()
        self.picture = picture
        self._scale = scale
        self.rect = None  # the selection in physical pixels
        self.targets = []  # windows in physical pixels, topmost first
        self.hover = None  # the target under the pointer, before a drag
        self._shade_probe = shade_probe
        self.readout = readout
        self.magnify = False
        self.pointer = None  # logical (x, y) while over this output
        self._loupe = None  # (x, y) of the middle pixel, (x, y) logical of the loupe
        self._slice = (None, None)  # (source rect, texture): one crop per pixel moved to
        self.add_css_class("capture-canvas")
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair"))

    def set_pointer(self, pos):
        self.pointer = pos
        if self.magnify:
            self.update_loupe()

    def target_at(self, pos):
        """The window under logical pos, else the whole output (physical)."""
        x, y = geometry.pixel_at(pos[0], self.scale), geometry.pixel_at(pos[1], self.scale)
        for rect in self.targets:
            if rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]:
                return rect
        return (0, 0, self.picture.width, self.picture.height)

    def set_hover(self, rect):
        if rect != self.hover:
            self.hover = rect
            self.queue_draw()

    @property
    def shown(self):
        """The rectangle the loupe outlines: the drag's, else the hover."""
        return self.rect if self.rect is not None else self.hover

    def set_magnify(self, on):
        self.magnify = on
        self.update_loupe()

    def _cell(self):
        """Device px per physical px in the loupe: whole, so the grid is sharp."""
        return max(1, round(LOUPE_CELL * self.scale))

    def update_loupe(self):
        """Place the loupe and its readout for the pointer, or hide them."""
        if not self.magnify or self.pointer is None:
            self._loupe = None
            self.readout.set_visible(False)
            self.queue_draw()
            return
        s, pic = self.scale, self.picture
        x = min(max(geometry.pixel_at(self.pointer[0], s), 0), pic.width - 1)
        y = min(max(geometry.pixel_at(self.pointer[1], s), 0), pic.height - 1)
        self.readout.set_label("{}, {}  #{:02X}{:02X}{:02X}".format(x, y, *pic.pixel(x, y)))
        self.readout.set_visible(True)
        # measure() counts the margins that place the label
        lw = self.readout.measure(Gtk.Orientation.HORIZONTAL, -1)[1] - self.readout.get_margin_start()
        lh = self.readout.measure(Gtk.Orientation.VERTICAL, -1)[1] - self.readout.get_margin_top()
        size = LOUPE_PIXELS * self._cell() / s
        lx, ly = geometry.loupe_place(self.pointer, (max(size, lw), size + LABEL_GAP + lh),
                                      (self.get_width(), self.get_height()), LOUPE_GAP)
        lx, ly = math.floor(lx), math.floor(ly)
        self.readout.set_margin_start(lx)
        self.readout.set_margin_top(math.ceil(ly + size + LABEL_GAP))
        self._loupe = ((x, y), (lx, ly))
        self.queue_draw()

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
        f = FRAME_WIDTH
        outline = Gsk.RoundedRect()
        if self.rect is None:
            # The shade stays until a drag: a hovered window only gets the
            # frame, pulled inside where it would fall past the output's edge
            snapshot.append_color(shade, _rect(0, 0, w, h))
            if self.hover is not None:
                x, y, sw, sh = geometry.to_logical(self.hover, self.scale)
                x0, y0 = max(x - f, 0), max(y - f, 0)
                x1, y1 = min(x + sw + f, w), min(y + sh + f, h)
                outline.init_from_rect(_rect(x0, y0, x1 - x0, y1 - y0), 0)
                snapshot.append_border(outline, [f] * 4, [self.get_color()] * 4)
        else:
            x, y, sw, sh = geometry.to_logical(self.rect, self.scale)
            for r in ((0, 0, w, y), (0, y + sh, w, h - y - sh),
                      (0, y, x, sh), (x + sw, y, w - x - sw, sh)):
                if r[2] > 0 and r[3] > 0:
                    snapshot.append_color(shade, _rect(*r))
            outline.init_from_rect(_rect(x - f, y - f, sw + 2 * f, sh + 2 * f), 0)
            snapshot.append_border(outline, [f] * 4, [self.get_color()] * 4)
        if self._loupe is not None:
            self._snapshot_loupe(snapshot, shade)

    def _snapshot_loupe(self, snapshot, shade):
        """The loupe, in device pixels: LOUPE_PIXELS physical px each side
        drawn as whole cells (NEAREST, never smoothed), a grid between them,
        the middle one outlined in the text colour, the selection's (or the
        hovered window's) edges in the accent while there is one."""
        (mx, my), (lx, ly) = self._loupe
        s, pic, cell, n = self.scale, self.picture, self._cell(), LOUPE_PIXELS
        size = n * cell
        sx, sy = mx - n // 2, my - n // 2  # the physical px in the top-left cell
        snapshot.save()
        snapshot.scale(1 / s, 1 / s)
        ox, oy = round(lx * s), round(ly * s)
        box = Gsk.RoundedRect()
        box.init_from_rect(_rect(ox, oy, size, size), LOUPE_RADIUS * s)
        snapshot.push_rounded_clip(box)
        # Past an output edge there is nothing: opaque shade colour
        empty = shade.copy()
        empty.alpha = 1
        snapshot.append_color(empty, _rect(ox, oy, size, size))
        x0, y0 = max(sx, 0), max(sy, 0)
        x1, y1 = min(sx + n, pic.width), min(sy + n, pic.height)
        if x1 > x0 and y1 > y0:
            src = (x0, y0, x1 - x0, y1 - y0)
            if self._slice[0] != src:
                self._slice = (src, pic.crop(*src))
            snapshot.append_scaled_texture(
                self._slice[1], Gsk.ScalingFilter.NEAREST,
                _rect(ox + (x0 - sx) * cell, oy + (y0 - sy) * cell,
                      (x1 - x0) * cell, (y1 - y0) * cell))
        for k in range(1, n):
            snapshot.append_color(shade, _rect(ox + k * cell, oy, 1, size))
            snapshot.append_color(shade, _rect(ox, oy + k * cell, size, 1))
        line = max(1, round(s))
        if self.shown is not None:
            rx, ry, rw, rh = self.shown
            edges = Gsk.RoundedRect()
            edges.init_from_rect(_rect(ox + (rx - sx) * cell - line, oy + (ry - sy) * cell - line,
                                       rw * cell + 2 * line, rh * cell + 2 * line), 0)
            snapshot.append_border(edges, [line] * 4, [self.get_color()] * 4)
        middle = Gsk.RoundedRect()
        middle.init_from_rect(_rect(ox + (mx - sx) * cell, oy + (my - sy) * cell, cell, cell), 0)
        snapshot.append_border(middle, [line] * 4, [self.readout.get_color()] * 4)
        snapshot.pop()
        f = max(1, round(FRAME_WIDTH * s))
        ring = Gsk.RoundedRect()
        ring.init_from_rect(_rect(ox - f, oy - f, size + 2 * f, size + 2 * f), LOUPE_RADIUS * s + f)
        snapshot.append_border(ring, [f] * 4, [self.get_color()] * 4)
        snapshot.restore()


def _rect(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


class Picker(Gtk.Application):
    """Shows one overlay per frame; result is (Picture, (x, y, w, h)) or None.
    windows: swayipc.windows(), the click targets."""

    def __init__(self, frames, scales, t0=None, windows=None):
        # One at a time is main.py's lock; no D-Bus name to wait for
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.frames = frames
        self.scales = scales
        self.windows_by_output = windows or {}
        self.t0 = t0
        self.result = None
        self.windows = []
        self.canvases = []
        self._active = None  # the Canvas a drag started on
        self._start = None
        self._dragging = False  # the press has moved CLICK_SLOP: a region
        self._magnify = False
        self._z_keys = set()  # hardware keycodes of Z in any layout (us: z, ru: я)

    def do_activate(self):
        if self.windows:
            return
        install_css(render_css(_CSS) + load_css(os.path.join(_DIR, "style.css")))
        display = Gdk.Display.get_default()
        found, keys = display.map_keyval(Gdk.KEY_z)
        self._z_keys = {k.keycode for k in keys} if found else set()
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
        readout = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.START,
                            can_target=False, visible=False)
        readout.add_css_class("capture-badge")
        canvas = Canvas(picture, scale, shade_probe, readout)
        if scale:
            size = (picture.width, picture.height)
            placed = (geometry.placed(r, scale, size)
                      for r in self.windows_by_output.get(frame.output.name, []))
            canvas.targets = [r for r in placed if r is not None]
        overlay = Gtk.Overlay(child=canvas)
        overlay.add_overlay(shade_probe)
        overlay.add_overlay(readout)
        win.set_child(overlay)
        self.canvases.append(canvas)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda _c, x, y: self._motion(canvas, (x, y)))
        motion.connect("motion", lambda _c, x, y: self._motion(canvas, (x, y)))
        motion.connect("leave", lambda _c: self._motion(canvas, None))
        canvas.add_controller(motion)
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

    def _on_key(self, _ctrl, keyval, keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        if keycode in self._z_keys or keyval in (Gdk.KEY_z, Gdk.KEY_Z):
            self._magnify = not self._magnify
            for canvas in self.canvases:
                canvas.set_magnify(self._magnify)
            return True
        return False

    def _motion(self, canvas, pos):
        canvas.set_pointer(pos)
        if self._active is None:  # no press going: light the target
            canvas.set_hover(canvas.target_at(pos) if pos is not None else None)

    def _select(self, canvas, end):
        pic = canvas.picture
        canvas.rect = geometry.selection(self._start, end, canvas.scale,
                                         (canvas.get_width(), canvas.get_height()),
                                         (pic.width, pic.height))
        canvas.set_pointer(end)
        canvas.queue_draw()

    def _drag_begin(self, _gesture, x, y, canvas):
        if self._active is not None and self._active is not canvas:
            return
        self._active = canvas
        self._start = (x, y)
        self._dragging = False

    def _drag_update(self, _gesture, dx, dy, canvas):
        if self._active is not canvas:
            return
        if not self._dragging:
            if max(abs(dx), abs(dy)) < CLICK_SLOP:
                return
            self._dragging = True
            canvas.hover = None
        self._select(canvas, (self._start[0] + dx, self._start[1] + dy))

    def _drag_end(self, _gesture, dx, dy, canvas):
        if self._active is not canvas:
            return
        if self._dragging:
            self._select(canvas, (self._start[0] + dx, self._start[1] + dy))
            rect = canvas.rect
        else:  # a click: the window (or output) under the press
            rect = canvas.target_at(self._start)
        self.result = (canvas.picture, rect)
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


def pick_region(frames, scales, t0=None, windows=None):
    """Run the picker. Returns (Picture, (x, y, w, h)) or None if cancelled.
    windows (swayipc.windows()) are what a click takes."""
    app = Picker(frames, scales, t0, windows)
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
    stop it; SIGUSR2, SIGINT and SIGTERM cancel. Either way the indicator
    goes at once, and the recorder is stopped in a thread. outcome:
    "stopped", "cancelled", or "failed" (wf-recorder exited by itself)."""

    def __init__(self, output, rect, scale, recorder, max_seconds, on_started, on_stopped):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.output = output
        self.rect = rect
        self.scale = scale
        self.recorder = recorder
        self.max_seconds = max_seconds
        self.on_started = on_started
        self.on_stopped = on_stopped
        self.outcome = None
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
        self._state = "cancelled" if cancel else "stopped"
        self.on_stopped()
        self.win.set_visible(False)
        threading.Thread(target=self._finish, daemon=True).start()

    def _finish(self):
        try:
            self.recorder.stop()
        finally:  # the app must end whatever happens
            GLib.idle_add(self._done)

    def _done(self):
        self.outcome = self._state
        self.quit()
        return False


def _clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def record(output, rect, scale, recorder, max_seconds, on_started, on_stopped):
    """Run the indicator (see Recording) until the recorder has stopped.
    Returns the outcome; the indicator is off the screen when it returns."""
    app = Recording(output, rect, scale, recorder, max_seconds, on_started, on_stopped)
    app.run([sys.argv[0]])
    if app.win is not None:
        app.win.set_visible(False)
    Gdk.Display.get_default().sync()
    return app.outcome
