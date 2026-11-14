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
import signal
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal, override

import cairo
from gi.repository import Gio, GLib, Graphene, Gsk

from gtk_widgets.lib.theme import render_css
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.widget_base import (
    Gdk,
    Gtk,
    Gtk4LayerShell,
    install_css,
    load_css,
)
from gtk_widgets.widgets.capture import geometry, screencopy
from gtk_widgets.widgets.capture import record as rec
from gtk_widgets.widgets.capture.geometry import Rect
from gtk_widgets.widgets.capture.ui import image

_STYLE = Path(__file__).resolve().parent / "style.css"

APP_ID = "dev.dotfiles.capture"
FRAME_WIDTH = 2  # logical px, drawn outside the selected pixels
LABEL_GAP = 6  # logical px between the indicator's frame (or the loupe) and its label
LOUPE_PIXELS = 13  # physical px across the loupe (odd: one in the middle)
LOUPE_CELL = 11  # logical px per physical px in the loupe, rounded to device px
LOUPE_GAP = 24  # logical px between the pointer and the loupe
LOUPE_RADIUS = 8
CLICK_SLOP = 3  # logical px a press may move and still be a click
TICK_MS = 200  # the indicator's clock
SCALE_MATCH = 1e-3  # a surface scale this close to the output's draws 1:1

type Point = tuple[float, float]
type Outcome = Literal["stopped", "cancelled", "failed"]
_CSS = """
window {
  background-color: transparent;
}
"""


class Canvas(Gtk.Widget):
    """The frozen frame, the shade, the selection frame and the loupe, in one
    snapshot. readout is the label under the loupe (a sibling overlay)."""

    def __init__(
        self,
        picture: image.Picture,
        scale: float | None,
        shade_probe: Gtk.Widget,
        readout: Gtk.Label,
    ) -> None:
        super().__init__()
        self.picture = picture
        self._scale = scale
        self.rect: Rect | None = None  # the selection in physical pixels
        self.targets: list[Rect] = []  # windows in physical pixels, topmost first
        self.hover: Rect | None = None  # the target under the pointer, before a drag
        self._shade_probe = shade_probe
        self.readout = readout
        self.magnify = False
        self.pointer: Point | None = None  # logical (x, y) while over this output
        # (x, y) of the middle pixel, (x, y) logical of the loupe
        self._loupe: tuple[tuple[int, int], tuple[int, int]] | None = None
        # (source rect, texture): one crop per pixel moved to
        self._slice: tuple[Rect, Gdk.Texture] | None = None
        self.add_css_class("capture-canvas")
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair"))

    def set_pointer(self, pos: Point | None) -> None:
        self.pointer = pos
        if self.magnify:
            self.update_loupe()

    def target_at(self, pos: Point) -> Rect:
        """The window under logical pos, else the whole output (physical)."""
        x, y = (
            geometry.pixel_at(pos[0], self.scale),
            geometry.pixel_at(pos[1], self.scale),
        )
        for rect in self.targets:
            if rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]:
                return rect
        return (0, 0, self.picture.width, self.picture.height)

    def set_hover(self, rect: Rect | None) -> None:
        if rect != self.hover:
            self.hover = rect
            self.queue_draw()

    @property
    def shown(self) -> Rect | None:
        """The rectangle the loupe outlines: the drag's, else the hover."""
        return self.rect if self.rect is not None else self.hover

    def set_magnify(self, *, on: bool) -> None:
        self.magnify = on
        self.update_loupe()

    def _cell(self) -> int:
        """Device px per physical px in the loupe: whole, so the grid is sharp."""
        return max(1, round(LOUPE_CELL * self.scale))

    def update_loupe(self) -> None:
        """Place the loupe and its readout for the pointer, or hide them."""
        pointer = self.pointer
        if not self.magnify or pointer is None:
            self._loupe = None
            self.readout.set_visible(False)
            self.queue_draw()
            return
        s, pic = self.scale, self.picture
        x = min(max(geometry.pixel_at(pointer[0], s), 0), pic.width - 1)
        y = min(max(geometry.pixel_at(pointer[1], s), 0), pic.height - 1)
        r, g, b = pic.pixel(x, y)
        self.readout.set_label(f"{x}, {y}  #{r:02X}{g:02X}{b:02X}")
        self.readout.set_visible(True)
        # measure() counts the margins that place the label
        lw = (
            self.readout.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            - self.readout.get_margin_start()
        )
        lh = (
            self.readout.measure(Gtk.Orientation.VERTICAL, -1)[1]
            - self.readout.get_margin_top()
        )
        size = LOUPE_PIXELS * self._cell() / s
        fx, fy = geometry.loupe_place(
            pointer,
            (max(size, lw), size + LABEL_GAP + lh),
            (self.get_width(), self.get_height()),
            LOUPE_GAP,
        )
        lx, ly = math.floor(fx), math.floor(fy)
        self.readout.set_margin_start(lx)
        self.readout.set_margin_top(math.ceil(ly + size + LABEL_GAP))
        self._loupe = ((x, y), (lx, ly))
        self.queue_draw()

    @property
    def scale(self) -> float:
        """The output's scale: sway's, else the surface's wp_fractional_scale
        (exact in 1/120 steps; Gdk.Monitor.get_scale() is a ratio of rounded
        sizes, see swayipc.py)."""
        if self._scale:
            return self._scale
        surface = _surface(self)
        return surface.get_scale() if surface else 1

    @override
    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        w, h = self.get_width(), self.get_height()
        pic = self.picture
        # Texture pixel k lands on device pixel k when GTK renders at the
        # output's scale (checked by screencopy at 1.25, 1.3, 1.5), provided
        # the texture is drawn at its own size under a 1/scale transform: into
        # a rectangle of the logical size GTK 4.22 resamples it. Otherwise the
        # preview is soft; the saved image never comes from it.
        surface = _surface(self)
        filt = (
            Gsk.ScalingFilter.NEAREST
            if surface and abs(surface.get_scale() - self.scale) < SCALE_MATCH
            else Gsk.ScalingFilter.LINEAR
        )
        snapshot.save()
        snapshot.scale(1 / self.scale, 1 / self.scale)
        snapshot.append_scaled_texture(
            pic.texture, filt, _rect(0, 0, pic.width, pic.height)
        )
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
            for r in (
                (0, 0, w, y),
                (0, y + sh, w, h - y - sh),
                (0, y, x, sh),
                (x + sw, y, w - x - sw, sh),
            ):
                if r[2] > 0 and r[3] > 0:
                    snapshot.append_color(shade, _rect(*r))
            outline.init_from_rect(_rect(x - f, y - f, sw + 2 * f, sh + 2 * f), 0)
            snapshot.append_border(outline, [f] * 4, [self.get_color()] * 4)
        if self._loupe is not None:
            self._snapshot_loupe(snapshot, shade, self._loupe)

    def _snapshot_loupe(
        self,
        snapshot: Gtk.Snapshot,
        shade: Gdk.RGBA,
        loupe: tuple[tuple[int, int], tuple[int, int]],
    ) -> None:
        """The loupe, in device pixels: LOUPE_PIXELS physical px each side
        drawn as whole cells (NEAREST, never smoothed), a grid between them,
        the middle one outlined in the text colour, the selection's (or the
        hovered window's) edges in the accent while there is one."""
        (mx, my), (lx, ly) = loupe
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
            if self._slice is None or self._slice[0] != src:
                self._slice = (src, pic.crop(*src))
            snapshot.append_scaled_texture(
                self._slice[1],
                Gsk.ScalingFilter.NEAREST,
                _rect(
                    ox + (x0 - sx) * cell,
                    oy + (y0 - sy) * cell,
                    (x1 - x0) * cell,
                    (y1 - y0) * cell,
                ),
            )
        for k in range(1, n):
            snapshot.append_color(shade, _rect(ox + k * cell, oy, 1, size))
            snapshot.append_color(shade, _rect(ox, oy + k * cell, size, 1))
        line = max(1, round(s))
        if self.shown is not None:
            rx, ry, rw, rh = self.shown
            edges = Gsk.RoundedRect()
            edges.init_from_rect(
                _rect(
                    ox + (rx - sx) * cell - line,
                    oy + (ry - sy) * cell - line,
                    rw * cell + 2 * line,
                    rh * cell + 2 * line,
                ),
                0,
            )
            snapshot.append_border(edges, [line] * 4, [self.get_color()] * 4)
        middle = Gsk.RoundedRect()
        middle.init_from_rect(
            _rect(ox + (mx - sx) * cell, oy + (my - sy) * cell, cell, cell), 0
        )
        snapshot.append_border(middle, [line] * 4, [self.readout.get_color()] * 4)
        snapshot.pop()
        f = max(1, round(FRAME_WIDTH * s))
        ring = Gsk.RoundedRect()
        ring.init_from_rect(
            _rect(ox - f, oy - f, size + 2 * f, size + 2 * f), LOUPE_RADIUS * s + f
        )
        snapshot.append_border(ring, [f] * 4, [self.get_color()] * 4)
        snapshot.restore()


def _rect(x: float, y: float, w: float, h: float) -> Graphene.Rect:
    return Graphene.Rect().init(x, y, w, h)


def _surface(widget: Gtk.Widget) -> Gdk.Surface | None:
    native = widget.get_native()
    return native.get_surface() if native is not None else None


def _display() -> Gdk.Display:
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("no display: GTK could not connect to Wayland")
    return display


def _monitors() -> list[Gdk.Monitor]:
    monitors = _display().get_monitors()
    found: list[Gdk.Monitor] = []
    for i in range(monitors.get_n_items()):
        monitor = monitors.get_item(i)
        if monitor is not None:
            found.append(monitor)
    return found


class Picker(Gtk.Application):
    """Shows one overlay per frame; result is (Picture, (x, y, w, h)) or None.
    windows: swayipc.windows(), the click targets."""

    def __init__(
        self,
        frames: list[screencopy.Frame],
        scales: dict[str, float],
        t0: int | None = None,
        windows: dict[str, list[Rect]] | None = None,
    ) -> None:
        # One at a time is main.py's lock; no D-Bus name to wait for
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.frames = frames
        self.scales = scales
        self.windows_by_output = windows or {}
        self.t0 = t0
        self.result: tuple[image.Picture, Rect] | None = None
        self.windows: list[Gtk.ApplicationWindow] = []
        self.canvases: list[Canvas] = []
        self._active: Canvas | None = None  # the Canvas a drag started on
        self._start: Point = (0.0, 0.0)
        self._dragging = False  # the press has moved CLICK_SLOP: a region
        self._magnify = False
        # hardware keycodes of Z in any layout (us: z, ru: я)
        self._z_keys: set[int] = set()

    @override
    def do_activate(self) -> None:
        if self.windows:
            return
        install_css(render_css(_CSS) + load_css(_STYLE))
        found, keys = _display().map_keyval(Gdk.KEY_z)
        self._z_keys = {k.keycode for k in keys} if found else set()
        by_name = {m.get_connector(): m for m in _monitors()}
        for frame in self.frames:
            monitor = by_name.get(frame.output.name)
            if monitor is None and len(self.frames) == 1 and len(by_name) == 1:
                monitor = next(iter(by_name.values()))
            if monitor is None:
                print(
                    f"capture: no monitor for output {frame.output.name!r}",
                    file=sys.stderr,
                )
                continue
            self.windows.append(self._window(frame, monitor))
        if not self.windows:
            self.quit()
            return
        if self.t0:
            self._trace(self.windows[0], self.t0)
        for win in self.windows:
            win.present()

    def _window(
        self, frame: screencopy.Frame, monitor: Gdk.Monitor
    ) -> Gtk.ApplicationWindow:
        picture = image.upright(frame)
        scale = self.scales.get(frame.output.name)

        win = Gtk.ApplicationWindow(application=self, title=APP_ID)
        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_namespace(win, "capture")
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_monitor(win, monitor)
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(win, edge, anchor_to_edge=True)
        # over the bar, at the output's origin
        Gtk4LayerShell.set_exclusive_zone(win, -1)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)

        # A widget that is never drawn, for the shade colour from style.css
        shade_probe = Gtk.Box(
            can_target=False, halign=Gtk.Align.START, valign=Gtk.Align.START
        )
        shade_probe.add_css_class("capture-shade")
        readout = Gtk.Label(
            halign=Gtk.Align.START,
            valign=Gtk.Align.START,
            can_target=False,
            visible=False,
        )
        readout.add_css_class("capture-badge")
        canvas = Canvas(picture, scale, shade_probe, readout)
        if scale:
            size = (picture.width, picture.height)
            placed = (
                geometry.placed(r, scale, size)
                for r in self.windows_by_output.get(frame.output.name, [])
            )
            canvas.targets = [r for r in placed if r is not None]
        overlay = Gtk.Overlay(child=canvas)
        overlay.add_overlay(shade_probe)
        overlay.add_overlay(readout)
        win.set_child(overlay)
        self.canvases.append(canvas)

        def moved(_c: Gtk.EventControllerMotion, x: float, y: float) -> None:
            self._motion(canvas, (x, y))

        def left(_c: Gtk.EventControllerMotion) -> None:
            self._motion(canvas, None)

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", moved)
        motion.connect("motion", moved)
        motion.connect("leave", left)
        canvas.add_controller(motion)
        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", self._drag_begin, canvas)
        drag.connect("drag-update", self._drag_update, canvas)
        drag.connect("drag-end", self._drag_end, canvas)
        canvas.add_controller(drag)
        cancel = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        cancel.connect("pressed", self._on_cancel_click)
        canvas.add_controller(cancel)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        win.add_controller(keys)
        return win

    def _on_cancel_click(
        self, _gesture: Gtk.GestureClick, _n: int, _x: float, _y: float
    ) -> None:
        self.quit()

    def _on_key(
        self,
        _ctrl: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        if keycode in self._z_keys or keyval in {Gdk.KEY_z, Gdk.KEY_Z}:
            self._magnify = not self._magnify
            for canvas in self.canvases:
                canvas.set_magnify(on=self._magnify)
            return True
        return False

    def _motion(self, canvas: Canvas, pos: Point | None) -> None:
        canvas.set_pointer(pos)
        if self._active is None:  # no press going: light the target
            canvas.set_hover(canvas.target_at(pos) if pos is not None else None)

    def _select(self, canvas: Canvas, end: Point) -> Rect:
        pic = canvas.picture
        canvas.rect = rect = geometry.selection(
            self._start,
            end,
            canvas.scale,
            (canvas.get_width(), canvas.get_height()),
            (pic.width, pic.height),
        )
        canvas.set_pointer(end)
        canvas.queue_draw()
        return rect

    def _drag_begin(
        self, _gesture: Gtk.GestureDrag, x: float, y: float, canvas: Canvas
    ) -> None:
        if self._active is not None and self._active is not canvas:
            return
        self._active = canvas
        self._start = (x, y)
        self._dragging = False

    def _drag_update(
        self, _gesture: Gtk.GestureDrag, dx: float, dy: float, canvas: Canvas
    ) -> None:
        if self._active is not canvas:
            return
        if not self._dragging:
            if max(abs(dx), abs(dy)) < CLICK_SLOP:
                return
            self._dragging = True
            canvas.hover = None
        self._select(canvas, (self._start[0] + dx, self._start[1] + dy))

    def _drag_end(
        self, _gesture: Gtk.GestureDrag, dx: float, dy: float, canvas: Canvas
    ) -> None:
        if self._active is not canvas:
            return
        if self._dragging:
            rect = self._select(canvas, (self._start[0] + dx, self._start[1] + dy))
        else:  # a click: the window (or output) under the press
            rect = canvas.target_at(self._start)
        self.result = (canvas.picture, rect)
        # Off the screen now: the PNG is written after the overlays are gone
        for win in self.windows:
            win.set_visible(False)
        self.quit()

    def _trace(self, win: Gtk.ApplicationWindow, t0: int) -> None:
        """Print the time from t0 (ns since the epoch) to the first frame."""
        handler = 0

        def painted(clock: Gdk.FrameClock) -> None:
            clock.disconnect(handler)
            print(
                f"capture: frozen frame painted {(time.time_ns() - t0) / 1e6:.1f} ms"
                " after launch",
                file=sys.stderr,
                flush=True,
            )

        def realized(w: Gtk.ApplicationWindow) -> None:
            nonlocal handler
            clock = w.get_frame_clock()
            if clock is not None:
                handler = clock.connect("after-paint", painted)

        win.connect("realize", realized)


def pick_region(
    frames: list[screencopy.Frame],
    scales: dict[str, float],
    t0: int | None = None,
    windows: dict[str, list[Rect]] | None = None,
) -> tuple[image.Picture, Rect] | None:
    """Run the picker. Returns (Picture, (x, y, w, h)) or None if cancelled.
    windows (swayipc.windows()) are what a click takes."""
    app = Picker(frames, scales, t0, windows)
    app.run([sys.argv[0]])
    _display().flush()  # the unmap goes out before the save
    return app.result


def wait_unmapped() -> None:
    """Block until the compositor has handled the picker's unmap (a
    roundtrip); the next frame it renders is without it."""
    _display().sync()


class FrameView(Gtk.Widget):
    """The recording frame, FRAME_WIDTH wide, just outside rect (physical
    pixels): its inner edges fall on the pixel edges around the selection. A
    side past the output's edge is clipped away with the surface."""

    def __init__(self, rect: Rect, scale: float) -> None:
        super().__init__(can_target=False)
        self.rect = rect
        self.scale = scale
        self.add_css_class("capture-frame")

    def logical(self) -> tuple[tuple[float, float, float, float], int]:
        """rect in the surface's coordinates, and how far out the frame starts.
        The surface draws at the output's scale when the compositor sends it
        (wp_fractional_scale); otherwise it is resampled, so the frame keeps a
        logical pixel away from the recorded ones."""
        surface = _surface(self)
        exact = surface is None or abs(surface.get_scale() - self.scale) < SCALE_MATCH
        return geometry.to_logical(self.rect, self.scale), 0 if exact else 1

    @override
    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        (x, y, w, h), gap = self.logical()
        f = FRAME_WIDTH
        x, y, w, h = x - gap, y - gap, w + 2 * gap, h + 2 * gap
        color = self.get_color()
        for r in (
            (x - f, y - f, w + 2 * f, f),
            (x - f, y + h, w + 2 * f, f),
            (x - f, y, f, h),
            (x + w, y, f, h),
        ):
            snapshot.append_color(color, _rect(*r))


def label_position(
    rect: tuple[float, float, float, float],
    size: tuple[int, int],
    label: tuple[int, int],
    frame: int,
) -> tuple[int, int] | None:
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
    for lx, ly in (
        (left, math.ceil(y + h + out)),
        (left, math.floor(y - out - lh)),
        (math.ceil(x + w + out), top),
        (math.floor(x - out - lw), top),
    ):
        if lx >= 0 and lx + lw <= sw and ly >= 0 and ly + lh <= sh:
            return lx, ly
    return None


class Recording(Gtk.Application):
    """The indicator while recorder runs. SIGUSR1 or the MAX_SECONDS cap
    stop it; SIGUSR2, SIGINT and SIGTERM cancel. Either way the indicator
    goes at once, and the recorder is stopped in a thread. outcome:
    "stopped", "cancelled", or "failed" (wf-recorder exited by itself)."""

    def __init__(
        self,
        output: str,
        rect: Rect,
        scale: float,
        recorder: rec.Recorder,
        *,
        max_seconds: float,
        on_started: Callable[[], None],
        on_stopped: Callable[[], None],
    ) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.output = output
        self.rect = rect
        self.scale = scale
        self.recorder = recorder
        self.max_seconds = max_seconds
        self.on_started = on_started
        self.on_stopped = on_stopped
        self.outcome: Outcome | None = None
        self.win: Gtk.ApplicationWindow | None = None
        self._state: Outcome | Literal["recording"] = "recording"
        self._t0 = 0.0
        self.frame = FrameView(rect, scale)
        self.label = Gtk.Label(
            halign=Gtk.Align.START, valign=Gtk.Align.START, can_target=False
        )
        self._size: tuple[int, int] | None = None

    @override
    def do_activate(self) -> None:
        if self.win:
            return
        install_css(render_css(_CSS) + load_css(_STYLE))
        monitors = _monitors()
        monitor = None
        for m in monitors:
            if m.get_connector() == self.output:
                monitor = m
        if monitor is None and len(monitors) == 1:
            monitor = monitors[0]
        self.win = win = self._window(monitor)
        for signum, cancel in (
            (signal.SIGUSR1, False),
            (signal.SIGUSR2, True),
            (signal.SIGINT, True),
            (signal.SIGTERM, True),
        ):
            GLib.unix_signal_add(
                GLib.PRIORITY_HIGH, signum, self._on_signal(cancel=cancel)
            )
        self._t0 = time.monotonic()
        self._tick()
        GLib.timeout_add(TICK_MS, self._tick)
        win.present()
        self.on_started()

    def _window(self, monitor: Gdk.Monitor | None) -> Gtk.ApplicationWindow:
        win = Gtk.ApplicationWindow(application=self, title=APP_ID)
        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_namespace(win, "capture-indicator")
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        if monitor is not None:
            Gtk4LayerShell.set_monitor(win, monitor)
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(win, edge, anchor_to_edge=True)
        Gtk4LayerShell.set_exclusive_zone(win, -1)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)
        win.set_can_target(False)

        def realized(w: Gtk.ApplicationWindow) -> None:
            # Clicks go through to whatever is below
            surface = w.get_surface()
            if surface is not None:
                surface.set_input_region(cairo.Region())

        win.connect("realize", realized)
        self.label.add_css_class("capture-badge")
        overlay = Gtk.Overlay(child=self.frame)
        overlay.add_overlay(self.label)
        win.set_child(overlay)
        geo = monitor.get_geometry() if monitor is not None else None
        self._size = (geo.width, geo.height) if geo else None
        return win

    def _set_label(self, text: str) -> None:
        if self.label.get_label() == text:
            return
        self.label.set_label(text)
        self.label.set_visible(True)
        size = self._size or (self.frame.get_width(), self.frame.get_height())
        # measure() counts the margins that place the label
        lw = (
            self.label.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            - self.label.get_margin_start()
        )
        lh = (
            self.label.measure(Gtk.Orientation.VERTICAL, -1)[1]
            - self.label.get_margin_top()
        )
        rect, gap = self.frame.logical()
        pos = label_position(rect, size, (lw, lh), FRAME_WIDTH + gap)
        if pos is None:
            self.label.set_visible(False)
        else:
            self.label.set_margin_start(pos[0])
            self.label.set_margin_top(pos[1])

    def _tick(self) -> bool:
        if self._state != "recording":
            return GLib.SOURCE_REMOVE
        if self.recorder.exited():
            self.outcome = "failed"
            self._state = "failed"
            self.on_stopped()
            self.quit()
            return GLib.SOURCE_REMOVE
        elapsed = time.monotonic() - self._t0
        if elapsed >= self.max_seconds:
            self._stop(cancel=False)
            return GLib.SOURCE_REMOVE
        self._set_label(f"{_clock(elapsed)} / {_clock(self.max_seconds)}")
        return GLib.SOURCE_CONTINUE

    def _on_signal(self, *, cancel: bool) -> Callable[[], bool]:
        def handler() -> bool:
            self._stop(cancel=cancel)
            return (
                GLib.SOURCE_CONTINUE
            )  # keep catching: a second press must not kill us

        return handler

    def _stop(self, *, cancel: bool) -> None:
        if self._state != "recording":
            return
        self._state = "cancelled" if cancel else "stopped"
        self.on_stopped()
        if self.win is not None:
            self.win.set_visible(False)
        in_background(self._finish, self._on_bug)

    def _finish(self) -> None:
        try:
            self.recorder.stop()
        finally:  # the app must end whatever happens
            GLib.idle_add(self._done)

    @staticmethod
    def _on_bug(message: str) -> None:
        """The indicator is gone by now: a bug in stopping goes to stderr."""
        print(f"capture: {message}", file=sys.stderr)

    def _done(self) -> bool:
        if self._state != "recording":
            self.outcome = self._state
        self.quit()
        return GLib.SOURCE_REMOVE


def _clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def record(
    output: str,
    rect: Rect,
    scale: float,
    recorder: rec.Recorder,
    *,
    max_seconds: float,
    on_started: Callable[[], None],
    on_stopped: Callable[[], None],
) -> Outcome | None:
    """Run the indicator (see Recording) until the recorder has stopped.
    Returns the outcome; the indicator is off the screen when it returns."""
    app = Recording(
        output,
        rect,
        scale,
        recorder,
        max_seconds=max_seconds,
        on_started=on_started,
        on_stopped=on_stopped,
    )
    app.run([sys.argv[0]])
    if app.win is not None:
        app.win.set_visible(False)
    _display().sync()
    return app.outcome
