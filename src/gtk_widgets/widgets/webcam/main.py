"""Webcam popup: live preview, every camera control, presets, LED, and the
background effects engine's switch and choices."""

import signal
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import override

from gi.repository import GLib, GObject

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.theme import colors
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import CopyLabel, copyable
from gtk_widgets.lib.ui.widget_base import Gtk, VScroller, WidgetPopup, pass_wheel
from gtk_widgets.widgets.webcam import engine, links, settings, v4l2
from gtk_widgets.widgets.webcam.apply import LED_MODES
from gtk_widgets.widgets.webcam.gallery import Gallery
from gtk_widgets.widgets.webcam.parse import Effect, Led, Settings
from gtk_widgets.widgets.webcam.preview import HEIGHT, WIDTH, Preview

BACKGROUNDS_DIR = Path.home() / "pictures/webcam"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
ANIMATED_SUFFIXES = {".gif", ".mp4", ".webm", ".mkv", ".mov", links.LINK_SUFFIX}
PREVIEW_SCALE = 0.6  # of the preview's frame size
CONTROLS_HEIGHT = 560
SET_DELAY_MS = 40  # a slider drag writes at most this often
SAVE_DELAY_MS = 400
RETRY_MS = 2000  # preview restart after ffmpeg stops
ENGINE_POLL_MS = 300
ENGINE_START_POLLS = 40  # 12 s: the first start downloads the model
ENGINE_WATCH_MS = 1000  # a running engine that dies turns the switch off
SWATCHES = ("BASE", "CRUST", "SURFACE1", "OVERLAY0", "BLUE", "GREEN", "MAUVE", "PEACH")

# Sections in this order; a control the camera has that is not here goes last
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("FRAMING", ("zoom_absolute", "pan_absolute", "tilt_absolute")),
    ("FOCUS", ("focus_automatic_continuous", "focus_absolute")),
    (
        "EXPOSURE",
        (
            "auto_exposure",
            "exposure_time_absolute",
            "exposure_dynamic_framerate",
            "gain",
            "backlight_compensation",
        ),
    ),
    ("WHITE BALANCE", ("white_balance_automatic", "white_balance_temperature")),
    ("IMAGE", ("brightness", "contrast", "saturation", "sharpness")),
    ("OTHER", ("power_line_frequency",)),
)
LABELS = {
    "zoom_absolute": "Zoom",
    "pan_absolute": "Pan",
    "tilt_absolute": "Tilt",
    "focus_automatic_continuous": "Autofocus",
    "focus_absolute": "Focus",
    "auto_exposure": "Exposure",
    "exposure_time_absolute": "Exposure time",
    "exposure_dynamic_framerate": "Lower frame rate in low light",
    "gain": "Gain",
    "backlight_compensation": "Backlight compensation",
    "white_balance_automatic": "Automatic",
    "white_balance_temperature": "Temperature",
    "brightness": "Brightness",
    "contrast": "Contrast",
    "saturation": "Saturation",
    "sharpness": "Sharpness",
    "power_line_frequency": "Anti-flicker",
}
MENU_LABELS = {
    "Manual Mode": "Manual",
    "Aperture Priority Mode": "Auto",
    "Disabled": "Off",
}
ZOOM = "zoom_absolute"
NO_ZOOM = 100  # zoom_absolute's value for the whole picture
PAN_TILT = ("pan_absolute", "tilt_absolute")
ARCSEC_PER_DEGREE = 3600


def _fmt(key: str, value: int) -> str:
    match key:
        case "zoom_absolute":
            return f"{value / NO_ZOOM:.1f}x"
        case "pan_absolute" | "tilt_absolute":
            return f"{value // ARCSEC_PER_DEGREE:+d}°"
        case "white_balance_temperature":
            return f"{value} K"
        case _:
            return str(value)


@dataclass(slots=True)
class Row:
    """One control's widgets: `box` holds them, `show` puts a value in them."""

    box: Gtk.Widget
    show: Callable[[v4l2.Control], None]


def _labelled(text: str, widget: Gtk.Widget) -> Gtk.Box:
    row = Gtk.Box(spacing=8)
    label = Gtk.Label(label=text, xalign=0, hexpand=True)
    label.add_css_class("row-label")
    row.append(label)
    row.append(widget)
    return row


def _is_switch(control: v4l2.Control) -> bool:
    return control.kind is v4l2.Kind.BOOLEAN or (
        control.kind is v4l2.Kind.INTEGER
        and (control.minimum, control.maximum) == (0, 1)
    )


class WebcamPopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.webcam")
        self._device: Path | None = None
        self._controls: dict[str, v4l2.Control] = {}
        self._rows: dict[str, Row] = {}
        self._syncing = False  # True while show() puts device values in widgets
        self._pending: dict[str, int] = {}
        self._set_source = 0
        self._save_source = 0
        self._retry_source = 0
        self._closing = False
        self._preview: Preview | None = None
        # The engine this popup started: polled so it is reaped when it ends
        self._engine_proc: subprocess.Popen[bytes] | None = None
        self._watch_source = 0
        match settings.load():
            case ParseError() as e:
                self._settings = Settings()
                self._load_error: str | None = str(e)
            case loaded:
                self._settings = loaded
                self._load_error = None

    # --- layout ---

    @override
    def build_ui(self) -> Gtk.Widget:
        container = Gtk.Box(spacing=20)
        container.add_css_class("webcam-container")
        self._device = v4l2.find_camera()

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        container.append(left)
        title = Gtk.Label(
            label=v4l2.card_name(self._device) if self._device else "Webcam", xalign=0
        )
        title.add_css_class("webcam-title")
        left.append(title)

        self._error = CopyLabel("webcam-error")
        self._error.set_wrap(True)
        self._error.set_xalign(0)
        self._error.set_max_width_chars(48)
        self._error.set_visible(False)
        left.append(self._error)

        if self._device is None:
            self._show_error("No camera found")
            return container

        self._build_preview(left)
        self._build_effects(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right.add_css_class("webcam-controls")
        container.append(VScroller(CONTROLS_HEIGHT, right))
        self._build_controls(right)

        if self._load_error:
            self._show_error(f"settings not read: {self._load_error}")
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_sigterm)
        self._start_preview()
        return container

    def _section(self, box: Gtk.Box, text: str) -> None:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("section-label")
        box.append(label)

    def _show_error(self, text: str) -> bool:
        self._error.set_content(text)
        self._error.set_visible(bool(text))
        return GLib.SOURCE_REMOVE

    # --- preview ---

    def _build_preview(self, box: Gtk.Box) -> None:
        overlay = Gtk.Overlay()
        overlay.add_css_class("preview")
        self._picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True)
        self._picture.set_size_request(
            int(WIDTH * PREVIEW_SCALE), int(HEIGHT * PREVIEW_SCALE)
        )
        overlay.set_child(self._picture)
        self._preview_note = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self._preview_note.add_css_class("preview-note")
        self._preview_note.set_valign(Gtk.Align.CENTER)
        self._preview_note.set_halign(Gtk.Align.CENTER)
        overlay.add_overlay(self._preview_note)
        box.append(overlay)
        self._preview = Preview(self._picture, self._on_preview_end, self._show_error)

    def _start_preview(self) -> bool:
        self._retry_source = 0
        if self._closing or self._device is None or self._preview is None:
            return GLib.SOURCE_REMOVE
        if engine.running_pid() is not None:
            loop = v4l2.find_loopback()
            if loop is None:
                self._preview_note.set_text("Effects on, no loopback device")
                return GLib.SOURCE_REMOVE
            self._preview_note.set_text("")
            self._preview.start(loop, camera=False)
        else:
            self._preview_note.set_text("")
            self._preview.start(self._device, camera=True)
        return GLib.SOURCE_REMOVE

    def _on_preview_end(self, message: str) -> None:
        busy = "busy" in message.lower()
        self._picture.set_paintable(None)
        self._preview_note.set_text(
            "Camera in use by another app\ncontrols still work" if busy else message
        )
        if not self._closing and not self._retry_source:
            self._retry_source = GLib.timeout_add(RETRY_MS, self._start_preview)

    # --- effects ---

    def _build_effects(self, box: Gtk.Box) -> None:
        self._section(box, "BACKGROUND")
        self._engine_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self._engine_switch.set_active(engine.running_pid() is not None)
        self._engine_switch.connect("state-set", self._on_engine_switch)
        if self._engine_switch.get_active():
            self._watch_engine()
        box.append(_labelled("Virtual camera", self._engine_switch))
        self._engine_note = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        self._engine_note.add_css_class("note")
        box.append(self._engine_note)
        self._show_engine_note()

        modes = Gtk.Box(spacing=0, homogeneous=True)
        modes.add_css_class("linked")
        first: Gtk.ToggleButton | None = None
        for effect, text in (
            (Effect.OFF, "None"),
            (Effect.BLUR, "Blur"),
            (Effect.IMAGE, "Image"),
            (Effect.ANIMATED, "Animated"),
            (Effect.COLOUR, "Colour"),
        ):
            button = Gtk.ToggleButton(label=text)
            button.add_css_class("mode")
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.set_active(self._settings.effect is effect)
            button.connect("toggled", self._on_effect, effect)
            modes.append(button)
        box.append(modes)

        self._blur_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        adj = Gtk.Adjustment(
            value=self._settings.blur, lower=0.1, upper=1.0, step_increment=0.05
        )
        blur = Gtk.Scale(adjustment=adj, draw_value=False)
        strength = Gtk.Label(label=f"{round(self._settings.blur * 100)}%")
        strength.add_css_class("row-value")
        adj.connect("value-changed", self._on_blur, strength)
        self._blur_box.append(_labelled("Strength", strength))
        self._blur_box.append(blur)
        box.append(self._blur_box)

        self._images = Gallery(
            BACKGROUNDS_DIR,
            suffixes=IMAGE_SUFFIXES,
            kind="images",
            chosen=lambda: self._settings.image,
            choose=self._on_image,
            show_error=self._show_error,
        )
        self._image_box = self._images.box
        box.append(self._image_box)
        box.append(self._build_animations())

        self._colour_box = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=len(SWATCHES)
        )
        palette = colors()
        for name in SWATCHES:
            if name not in palette:
                continue
            swatch = Gtk.Button(tooltip_text=name.lower())
            swatch.add_css_class("swatch")
            swatch.add_css_class(f"swatch-{name.lower()}")
            swatch.connect("clicked", self._on_colour, palette[name])
            self._colour_box.append(swatch)
        box.append(self._colour_box)
        self._show_effect_options()

    def _build_animations(self) -> Gtk.Box:
        """The GIFs, videos and links, and the box a link is pasted in."""
        self._animation_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._animations = Gallery(
            BACKGROUNDS_DIR,
            suffixes=ANIMATED_SUFFIXES,
            kind="GIFs or videos (or paste a video link below)",
            chosen=lambda: self._settings.animation,
            choose=self._on_animation,
            show_error=self._show_error,
        )
        self._animation_box.append(self._animations.box)
        self._animation_box.append(self._build_link_row())
        self._link_note = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        self._link_note.add_css_class("note")
        self._animation_box.append(self._link_note)
        return self._animation_box

    def _build_link_row(self) -> Gtk.Box:
        self._link_entry = Gtk.Entry(
            placeholder_text="Paste a YouTube or other video link", hexpand=True
        )
        self._link_add = Gtk.Button(label="Add")
        self._link_add.connect("clicked", self._on_link_add)
        self._link_entry.connect("activate", self._on_link_add)
        row = Gtk.Box(spacing=6)
        row.append(self._link_entry)
        row.append(self._link_add)
        return row

    def _on_link_add(self, _widget: Gtk.Widget) -> None:
        text = self._link_entry.get_text().strip()
        if not text or not self._link_add.get_sensitive():
            return
        self._link_add.set_sensitive(False)
        self._link_note.set_text("Checking the link…")
        _ = copyable(self._link_note, on=False)

        def check() -> None:
            added = links.add_link(text, BACKGROUNDS_DIR)
            _ = GLib.idle_add(self._link_added, added)

        in_background(check, self._show_error)

    def _link_added(self, added: Path | links.LinkError) -> bool:
        self._link_add.set_sensitive(True)
        match added:
            case links.LinkError() as e:
                self._link_note.set_text(str(e))
                _ = copyable(self._link_note)
            case path:
                self._link_entry.set_text("")
                self._link_note.set_text(f"Saved as {path.name}")
                self._on_animation(str(path))
                self._animations.refresh()
        return GLib.SOURCE_REMOVE

    def _show_effect_options(self) -> None:
        effect = self._settings.effect
        self._blur_box.set_visible(effect is Effect.BLUR)
        self._image_box.set_visible(effect is Effect.IMAGE)
        self._animation_box.set_visible(effect is Effect.ANIMATED)
        self._colour_box.set_visible(effect is Effect.COLOUR)

    def _show_engine_note(self, error: str = "") -> None:
        if error:
            text = error
        elif engine.running_pid() is not None:
            loop = v4l2.find_loopback()
            name = v4l2.card_name(loop) if loop else "?"
            text = f"Apps pick “{name}” as their camera"
        else:
            text = "Off: apps get the camera as is"
        self._engine_note.set_text(text)

    def _on_effect(self, button: Gtk.ToggleButton, effect: Effect) -> None:
        if button.get_active():
            self._settings.effect = effect
            self._show_effect_options()
            self._save_now()

    def _on_blur(self, adj: Gtk.Adjustment, strength: Gtk.Label) -> None:
        self._settings.blur = round(adj.get_value(), 2)
        strength.set_text(f"{round(self._settings.blur * 100)}%")
        self._save_later()

    def _on_image(self, path: str | None) -> None:
        self._settings.image = path
        self._save_now()

    def _on_animation(self, path: str | None) -> None:
        self._settings.animation = path
        self._save_now()

    def _on_colour(self, _button: Gtk.Button, colour: str) -> None:
        self._settings.colour = colour
        self._save_now()

    def _on_engine_switch(self, switch: Gtk.Switch, state: int) -> bool:
        on = bool(state)  # a gboolean
        running = engine.running_pid() is not None
        if on and not running:
            # Insensitive until the engine holds its lock: a second toggle in
            # between would start a second engine or stop none
            switch.set_sensitive(False)
            self._stop_preview()  # the engine needs the camera to itself
            self._engine_proc = engine.start()
            self._engine_note.set_text("Starting…")
            GLib.timeout_add(ENGINE_POLL_MS, self._poll_engine_start, [0])
        elif not on and running:
            switch.set_sensitive(False)
            self._unwatch_engine()
            engine.stop()
            self._stop_preview()
            GLib.timeout_add(ENGINE_POLL_MS, self._poll_engine_stop)
        return False  # let the switch move

    def _poll_engine_start(self, polls: list[int]) -> bool:
        polls[0] += 1
        proc = self._engine_proc
        if engine.running_pid() is not None:
            self._engine_switch.set_sensitive(True)
            self._show_engine_note()
            self._start_preview()
            self._watch_engine()
            return GLib.SOURCE_REMOVE
        if (proc is not None and proc.poll() is not None) or polls[
            0
        ] > ENGINE_START_POLLS:
            self._engine_failed()
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _poll_engine_stop(self) -> bool:
        if engine.running_pid() is not None:
            return GLib.SOURCE_CONTINUE
        if self._engine_proc is not None:
            _ = self._engine_proc.poll()
        self._engine_switch.set_sensitive(True)
        self._show_engine_note()
        self._start_preview()
        return GLib.SOURCE_REMOVE

    def _watch_engine(self) -> None:
        self._unwatch_engine()
        self._watch_source = GLib.timeout_add(ENGINE_WATCH_MS, self._check_engine)

    def _unwatch_engine(self) -> None:
        if self._watch_source:
            GLib.source_remove(self._watch_source)
            self._watch_source = 0

    def _check_engine(self) -> bool:
        """The engine stopped by itself (camera unplugged, a crash)."""
        if engine.running_pid() is not None:
            return GLib.SOURCE_CONTINUE
        self._watch_source = 0
        self._stop_preview()  # it showed the engine's output
        self._engine_failed()
        return GLib.SOURCE_REMOVE

    def _engine_failed(self) -> None:
        if self._engine_proc is not None:
            _ = self._engine_proc.poll()
        self._engine_switch.set_sensitive(True)
        self._show_engine_note(engine.last_error() or "the engine stopped")
        self._engine_switch.set_active(False)
        self._start_preview()

    # --- controls ---

    def _build_controls(self, box: Gtk.Box) -> None:
        if (listed := self._list()) is None:
            return
        self._controls = {c.key: c for c in listed}
        led = v4l2.get_led(self._device) if self._device else None
        for title, keys in GROUPS:
            present = [k for k in keys if k in self._controls]
            if title == "OTHER":
                present += [
                    k for k in self._controls if not any(k in g for _, g in GROUPS)
                ]
            if not present and not (title == "OTHER" and led is not None):
                continue
            self._section(box, title)
            for key in present:
                row = self._build_row(self._controls[key])
                self._rows[key] = row
                box.append(row.box)
            if title == "OTHER" and led is not None:
                box.append(self._build_led(led))
        self._build_presets(box)
        self._sync()

    def _list(self) -> list[v4l2.Control] | None:
        if self._device is None:
            return None
        match v4l2.list_controls(self._device):
            case v4l2.CameraError() as e:
                self._show_error(f"{self._device}: {e.strerror}")
                return None
            case listed:
                return listed

    def _build_row(self, control: v4l2.Control) -> Row:
        key = control.key
        text = LABELS.get(key, control.label)
        if _is_switch(control):
            switch = Gtk.Switch(valign=Gtk.Align.CENTER)

            def on_switch(_s: Gtk.Switch, state: int) -> bool:
                return self._on_value(key, int(bool(state)), at_once=True)

            switch.connect("state-set", on_switch)

            def show_switch(c: v4l2.Control) -> None:
                switch.set_active(bool(c.value))

            return Row(_labelled(text, switch), show_switch)
        if control.kind is v4l2.Kind.MENU:
            values = [v for v, _ in control.menu]
            dropdown = Gtk.DropDown.new_from_strings(
                [MENU_LABELS.get(label, label) for _, label in control.menu]
            )

            def on_menu(d: Gtk.DropDown, _p: GObject.ParamSpec) -> None:
                _ = self._on_value(key, values[d.get_selected()], at_once=True)

            dropdown.connect("notify::selected", on_menu)

            def show_menu(c: v4l2.Control) -> None:
                if c.value in values:
                    dropdown.set_selected(values.index(c.value))

            return Row(_labelled(text, dropdown), show_menu)

        value = Gtk.Label(label=_fmt(key, control.value))
        value.add_css_class("row-value")
        adj = Gtk.Adjustment(
            value=control.value,
            lower=control.minimum,
            upper=control.maximum,
            step_increment=control.step,
            page_increment=control.step,
        )
        scale = Gtk.Scale(adjustment=adj, draw_value=False)
        pass_wheel(scale)
        if control.minimum < control.default < control.maximum:
            scale.add_mark(control.default, Gtk.PositionType.BOTTOM, None)
        step = control.step

        def on_slide(a: Gtk.Adjustment) -> None:
            snapped = (
                control.minimum + round((a.get_value() - control.minimum) / step) * step
            )
            value.set_text(_fmt(key, snapped))
            self._on_value(key, snapped, at_once=False)

        adj.connect("value-changed", on_slide)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(_labelled(text, value))
        box.append(scale)

        def show_scale(c: v4l2.Control) -> None:
            adj.set_value(c.value)
            value.set_text(_fmt(key, c.value))

        return Row(box, show_scale)

    def _build_led(self, led: v4l2.LedMode) -> Gtk.Widget:
        modes = [Led.OFF, Led.ON, Led.AUTO]
        dropdown = Gtk.DropDown.new_from_strings(["Off", "On", "While streaming"])
        current = next((m for m in modes if LED_MODES[m] is led), Led.AUTO)
        dropdown.set_selected(modes.index(current))

        def on_led(d: Gtk.DropDown, _p: GObject.ParamSpec) -> None:
            mode = modes[d.get_selected()]
            if self._device is not None and (
                e := v4l2.set_led(self._device, LED_MODES[mode])
            ):
                self._show_error(f"LED: {e.strerror}")
                return
            self._settings.led = mode
            self._save_now()

        dropdown.connect("notify::selected", on_led)
        return _labelled("LED", dropdown)

    def _build_presets(self, box: Gtk.Box) -> None:
        self._section(box, "PRESETS")
        self._preset_list = Gtk.StringList()
        self._presets = Gtk.DropDown(model=self._preset_list, hexpand=True)
        apply = Gtk.Button(label="Apply")
        apply.connect("clicked", self._on_preset_apply)
        delete = Gtk.Button(label="Delete")
        delete.connect("clicked", self._on_preset_delete)
        row = Gtk.Box(spacing=6)
        for widget in (self._presets, apply, delete):
            row.append(widget)
        box.append(row)

        self._preset_name = Gtk.Entry(placeholder_text="Preset name", hexpand=True)
        save = Gtk.Button(label="Save")
        save.connect("clicked", self._on_preset_save)
        self._preset_name.connect("activate", self._on_preset_save)
        row = Gtk.Box(spacing=6)
        row.append(self._preset_name)
        row.append(save)
        box.append(row)

        reset = Gtk.Button(label="Reset camera to defaults")
        reset.connect("clicked", self._on_reset)
        box.append(reset)
        self._show_presets()

    def _show_presets(self, select: str | None = None) -> None:
        names = sorted(self._settings.presets)
        self._preset_list.splice(0, self._preset_list.get_n_items(), names)
        if select in names:
            self._presets.set_selected(names.index(select))

    def _selected_preset(self) -> str | None:
        item = self._presets.get_selected_item()
        return item.get_string() if isinstance(item, Gtk.StringObject) else None

    def _on_preset_save(self, _widget: Gtk.Widget) -> None:
        name = self._preset_name.get_text().strip()
        if not name:
            return
        self._settings.presets[name] = {k: c.value for k, c in self._controls.items()}
        self._preset_name.set_text("")
        self._show_presets(name)
        self._save_now()

    def _on_preset_apply(self, _button: Gtk.Button) -> None:
        name = self._selected_preset()
        if name is not None:
            self._apply_values(self._settings.presets[name])

    def _on_preset_delete(self, _button: Gtk.Button) -> None:
        name = self._selected_preset()
        if name is not None:
            del self._settings.presets[name]
            self._show_presets()
            self._save_now()

    def _on_reset(self, _button: Gtk.Button) -> None:
        self._apply_values({k: c.default for k, c in self._controls.items()})

    def _apply_values(self, values: dict[str, int]) -> None:
        if self._device is None:
            return
        match v4l2.apply_values(self._device, values):
            case v4l2.CameraError() as e:
                self._show_error(f"{self._device}: {e.strerror}")
            case []:
                self._show_error("")
            case failed:
                self._show_error(f"not applied: {', '.join(failed)}")
        self._sync()
        self._save_later()

    def _on_value(self, key: str, value: int, *, at_once: bool) -> bool:
        if self._syncing:
            return False
        self._pending[key] = value
        if at_once:
            self._write()
        elif not self._set_source:
            self._set_source = GLib.timeout_add(SET_DELAY_MS, self._write)
        return False

    def _write(self) -> bool:
        if self._set_source:
            GLib.source_remove(self._set_source)
            self._set_source = 0
        pending, self._pending = self._pending, {}
        if self._device is None:
            return GLib.SOURCE_REMOVE
        for key, value in pending.items():
            if (
                e := v4l2.set_control(self._device, self._controls[key].id, value)
            ) is not None:
                self._show_error(f"{LABELS.get(key, key)}: {e.strerror}")
                break
        else:
            self._show_error("")
        self._sync(skip=set(pending))
        self._save_later()
        return GLib.SOURCE_REMOVE

    def _sync(self, skip: set[str] | None = None) -> None:
        """Read every control back: an automatic mode switched on or off
        changes which values are the user's, and what they are now."""
        if (listed := self._list()) is None:
            return
        self._controls = {c.key: c for c in listed}
        zoomed = (z := self._controls.get(ZOOM)) is None or z.value > NO_ZOOM
        self._syncing = True
        try:
            for key, row in self._rows.items():
                control = self._controls.get(key)
                if control is None:
                    continue
                if not skip or key not in skip:
                    row.show(control)
                row.box.set_sensitive(
                    not control.inactive and (key not in PAN_TILT or zoomed)
                )
                row.box.set_tooltip_text(
                    "Zoom in to move the picture"
                    if key in PAN_TILT and not zoomed
                    else "Set by its automatic mode"
                    if control.inactive
                    else None
                )
        finally:
            self._syncing = False

    # --- settings file ---

    def _save_later(self) -> None:
        if self._save_source:
            GLib.source_remove(self._save_source)
        self._save_source = GLib.timeout_add(SAVE_DELAY_MS, self._save_now)

    def _save_now(self) -> bool:
        if self._save_source:
            GLib.source_remove(self._save_source)
            self._save_source = 0
        if self._controls:
            self._settings.controls = {k: c.value for k, c in self._controls.items()}
        try:
            settings.save(self._settings)
        except OSError as e:
            self._show_error(f"settings not saved: {e.strerror}")
        return GLib.SOURCE_REMOVE

    # --- close ---

    def _on_sigterm(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    @override
    def do_shutdown(self) -> None:
        self._closing = True
        if self._pending:
            self._write()
        if self._save_source:
            self._save_now()
        self._stop_preview()
        Gtk.Application.do_shutdown(self)

    def _stop_preview(self) -> None:
        if self._preview is not None:
            self._preview.stop()


def main() -> int:
    return WebcamPopup().run()
