"""Audio popup — GTK4 pavucontrol replacement backed by pulsectl (vendored in lib/).

Three pulse connections: an event connection whose blocking event_listen() runs
in a thread and only forwards events to the GTK main loop, a command connection
used on the main thread for every read and write, and a meter connection with
its own thread for the peak meter streams (meters.py). Rows are keyed by pulse
index and updated in place; the lists are never rebuilt.
"""

import contextlib
import json
import math
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Literal, override

from gi.repository import GLib, GObject, Pango

from gtk_widgets.lib import pulsectl
from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.pulsectl import (
    Pulse,
    PulseCardInfo,
    PulseCardPortInfo,
    PulseEventInfo,
    PulseExtStreamRestoreInfo,
    PulseSinkInfo,
    PulseSinkInputInfo,
    PulseSourceInfo,
    PulseSourceOutputInfo,
    PulseVolumeInfo,
)
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import CopyLabel, copyable
from gtk_widgets.lib.ui.widget_base import Gdk, Gtk, VScroller, WidgetPopup, pass_wheel
from gtk_widgets.widgets.audio.meters import (
    METER_RATE,
    MIXER_APP_IDS,
    Meters,
    MeterSpec,
)
from gtk_widgets.widgets.audio.parse import State, parse_state
from gtk_widgets.widgets.audio.parts import APP_ID, ICON, error_box, popup_frame
from gtk_widgets.widgets.audio.recorder import Recorder, RecordState

PA_INVALID = 2**32 - 1
VOLUME_UI_MAX = 153  # PA_VOLUME_UI_MAX (+11 dB) in percent
SCROLL_STEP = 5  # percent per Page Up/Down on a slider
DRAG_GRACE = 0.2  # seconds volume events stay ignored after a drag
BACKOFF_START, BACKOFF_MAX = 0.5, 5  # reconnect delay doubles from 0.5 s, capped at 5 s
LATENCY_RANGE_MS = 2000
EVENT_ROLE = "sink-input-by-media-role:event"
METER_DECAY = 0.5  # meter fall per second, in bar lengths
RECORD_TICK_MS = 250

type DeviceKind = Literal["sink", "source"]
type StreamKind = Literal["sink_input", "source_output"]
type Facility = DeviceKind | StreamKind | Literal["card"]
type TabKey = Literal["playback", "recording", "outputs", "inputs", "config"]
type Info = (
    PulseSinkInfo
    | PulseSourceInfo
    | PulseSinkInputInfo
    | PulseSourceOutputInfo
    | PulseCardInfo
)
type MeterKey = tuple[Facility, int]

EVENT_FACILITIES: tuple[Facility | Literal["server"], ...] = (
    "card",
    "sink",
    "source",
    "sink_input",
    "source_output",
    "server",
)

INFO: dict[Facility, Callable[[Pulse, int], Info]] = {
    "card": Pulse.card_info,
    "sink": Pulse.sink_info,
    "source": Pulse.source_info,
    "sink_input": Pulse.sink_input_info,
    "source_output": Pulse.source_output_info,
}
VOLUME_SET: dict[
    DeviceKind | StreamKind, Callable[[Pulse, int, PulseVolumeInfo], None]
] = {
    "sink": Pulse.sink_volume_set,
    "source": Pulse.source_volume_set,
    "sink_input": Pulse.sink_input_volume_set,
    "source_output": Pulse.source_output_volume_set,
}
MUTE: dict[DeviceKind | StreamKind, Callable[[Pulse, int, bool], None]] = {
    "sink": Pulse.sink_mute,
    "source": Pulse.source_mute,
    "sink_input": Pulse.sink_input_mute,
    "source_output": Pulse.source_output_mute,
}
DEFAULT_SET: dict[DeviceKind, Callable[[Pulse, str], None]] = {
    "sink": Pulse.sink_default_set,
    "source": Pulse.source_default_set,
}
PORT_SET: dict[DeviceKind, Callable[[Pulse, int, str], None]] = {
    "sink": Pulse.sink_port_set,
    "source": Pulse.source_port_set,
}
MOVE: dict[StreamKind, Callable[[Pulse, int, int], None]] = {
    "sink_input": Pulse.sink_input_move,
    "source_output": Pulse.source_output_move,
}
KILL: dict[StreamKind, Callable[[Pulse, int], None]] = {
    "sink_input": Pulse.sink_input_kill,
    "source_output": Pulse.source_output_kill,
}


def meter_position(peak: float) -> float:
    """Linear sample peak -> 0..1 on the volume sliders' cubic scale (loud
    speech ~60%). pavucontrol draws linear peaks, which barely move."""
    return min(max(peak, 0.0), 1.0) ** (1 / 3)


# level bar offsets (name, upper bound in dBFS): green, yellow, red near clipping
METER_BANDS = [
    (name, meter_position(10 ** (db / 20)))
    for name, db in (("low", -6), ("high", -1), ("full", 0))
]

STATE_FILE = (
    Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    / "gtk-widgets"
    / "audio.json"
)


@dataclass(frozen=True, slots=True)
class TabSpec:
    key: TabKey
    label: str
    facility: Facility
    empty: str  # shown when no row is
    filters: list[tuple[str, str]]  # (key, label); none: no filter bar
    default_filter: str


STREAM_FILTERS = [
    ("all", "All streams"),
    ("apps", "Applications"),
    ("virtual", "Virtual streams"),
]
TABS = [
    TabSpec(
        "playback",
        "Playback",
        "sink_input",
        "No application is currently playing audio.",
        STREAM_FILTERS,
        "apps",
    ),
    TabSpec(
        "recording",
        "Recording",
        "source_output",
        "No application is currently recording audio.",
        STREAM_FILTERS,
        "apps",
    ),
    TabSpec(
        "outputs",
        "Output Devices",
        "sink",
        "No output devices available.",
        [("all", "All"), ("hardware", "Hardware"), ("virtual", "Virtual")],
        "all",
    ),
    TabSpec(
        "inputs",
        "Input Devices",
        "source",
        "No input devices available.",
        [
            ("all", "All"),
            ("no-monitors", "All except monitors"),
            ("hardware", "Hardware"),
            ("virtual", "Virtual"),
            ("monitors", "Monitors"),
        ],
        "no-monitors",
    ),
    TabSpec("config", "Configuration", "card", "No cards available.", [], "all"),
]
TAB_KEYS: list[TabKey] = [t.key for t in TABS]
TAB_OF: dict[Facility, TabKey] = {t.facility: t.key for t in TABS}

CHANNEL_NAMES = {"mono": "Mono", "lfe": "Subwoofer"}


def channel_label(name: str) -> str:
    """Pretty name for a pulse channel position ('front-left' -> 'Front Left')."""
    return CHANNEL_NAMES.get(name) or " ".join(w.capitalize() for w in name.split("-"))


def volume_db(v: float) -> str:
    """pa_sw_volume_to_dB: libpulse volumes are cubic, so dB = 60 * log10(v)."""
    return (
        "-inf dB" if v <= 0 else f"{60 * math.log10(v):+.1f} dB".replace("+0.0", "0.0")
    )


def scale_volume(values: list[float], new_max: float) -> list[float]:
    """pa_cvolume_scale: scale all channels so the loudest equals new_max."""
    peak = max(values, default=0)
    if peak <= 0:
        return [new_max] * len(values)
    return [v * new_max / peak for v in values]


def load_state() -> State:
    try:
        data: object = json.loads(STATE_FILE.read_text())
    except OSError, ValueError:
        return State()
    match parse_state(data):
        case ParseError():
            return State()
        case state:
            return state


def save_state(state: State) -> None:
    with contextlib.suppress(OSError):
        STATE_FILE.parent.mkdir(exist_ok=True, parents=True)
        STATE_FILE.write_text(json.dumps(asdict(state)))


def glyph_button(css_class: str, tooltip: str | None = None) -> Gtk.Button:
    return _glyph(Gtk.Button(), css_class, tooltip)


def glyph_toggle(css_class: str, tooltip: str) -> Gtk.ToggleButton:
    return _glyph(Gtk.ToggleButton(), css_class, tooltip)


def _glyph[B: Gtk.Button](btn: B, css_class: str, tooltip: str | None) -> B:
    btn.add_css_class("au-icon-btn")
    btn.add_css_class(css_class)
    btn.set_valign(Gtk.Align.CENTER)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    return btn


class Choice[K](Gtk.DropDown):
    """Dropdown of (key, label, enabled) items, updated in place.

    Disabled items are shown dimmed and cannot be picked. Programmatic updates
    never fire the pick callback.
    """

    def __init__(
        self, on_pick: Callable[[K], None], max_chars: int | None = 24
    ) -> None:
        self._model = Gtk.StringList()
        super().__init__(model=self._model)
        self.add_css_class("au-choice")
        self._keys: list[K] = []
        self._labels: list[str] = []
        self._enabled: list[bool] = []
        self._active: K | None = None
        self._on_pick = on_pick
        self.set_factory(self._make_factory(max_chars))
        self.set_list_factory(self._make_factory(None))
        self._handler = self.connect("notify::selected", self._on_selected)

    def _make_factory(self, max_chars: int | None) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory()

        def setup(_f: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            label = Gtk.Label(xalign=0)
            if max_chars:
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_max_width_chars(max_chars)
            item.set_child(label)

        def bind(_f: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            pos = item.get_position()
            enabled = self._enabled[pos] if pos < len(self._enabled) else True
            label, text = item.get_child(), item.get_item()
            if isinstance(label, Gtk.Label) and isinstance(text, Gtk.StringObject):
                label.set_text(text.get_string())
                label.set_sensitive(enabled)
            item.set_activatable(enabled)
            item.set_selectable(enabled)

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    def set_items(self, items: list[tuple[K, str, bool]], active: K | None) -> None:
        """items: [(key, label, enabled)]; active: key to show as selected."""
        keys = [k for k, _, _ in items]
        labels = [label for _, label, _ in items]
        enabled = [e for _, _, e in items]
        with self.handler_block(self._handler):
            if labels != self._labels or enabled != self._enabled:
                self._labels, self._enabled = labels, enabled
                self._model.splice(0, self._model.get_n_items(), labels)
            self._keys, self._active = keys, active
            pos = keys.index(active) if active in keys else Gtk.INVALID_LIST_POSITION
            if self.get_selected() != pos:
                self.set_selected(pos)

    def revert(self) -> None:
        """Show the last server-confirmed item again (after a failed pick)."""
        self.set_items(
            list(zip(self._keys, self._labels, self._enabled, strict=True)),
            self._active,
        )

    def _on_selected(self, _dropdown: Gtk.DropDown, _pspec: GObject.ParamSpec) -> None:
        pos = self.get_selected()
        if pos >= len(self._keys) or not self._enabled[pos]:
            self.revert()
            return
        if self._keys[pos] != self._active:
            self._on_pick(self._keys[pos])


class VolumeControl(Gtk.Box):
    """Mute toggle, 0-153% slider, percent label and per-channel sliders.

    While the user drags (or scrolls) a slider, and DRAG_GRACE after, volume
    updates from the server are held back and applied once the grace ends, so
    the slider never jitters or snaps back.

    `meter` (None: no meter) adds a peak meter under the slider, shown if true.
    Meter levels never touch the sliders or their drag tracking.
    """

    def __init__(
        self,
        on_volume: Callable[[list[float]], None],
        on_mute: Callable[[bool], None],
        *,
        mic: bool = False,
        meter: bool | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._on_volume, self._on_mute = on_volume, on_mute
        self._icons = ("mic", "mic_mute") if mic else ("speaker", "speaker_mute")
        self._values: list[float] = []
        self._channels: list[str] = []
        self._pressed, self._busy_until = False, 0.0
        self._pending: list[float] | None = None
        self._resync_id = 0
        self._chan_scales: list[tuple[Gtk.Scale, int, Gtk.Label, Gtk.Label]] = []

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._mute = glyph_toggle("au-mute-btn", "Mute")
        self._mute_handler = self._mute.connect("toggled", self._on_mute_toggled)
        main.append(self._mute)

        self._base = 1.0
        self._scale, self._scale_handler = self._make_scale(
            self._on_main_changed, labeled=True
        )
        slider = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
        slider.append(self._scale)
        main.append(slider)

        self._meter: Gtk.LevelBar | None = None
        self._level = 0.0
        if meter is not None:
            self._meter = Gtk.LevelBar(min_value=0, max_value=1)
            for name, value in METER_BANDS:
                self._meter.add_offset_value(name, value)
            self._meter.add_css_class("au-meter")
            self._meter.set_visible(meter)
            slider.append(self._meter)

        self._pct, self._db = self._level_labels()
        main.append(self._pct)
        main.append(self._db)
        # mark labels make the scale taller; keep its neighbours level with the trough
        for w in (self._mute, self._pct, self._db):
            w.set_valign(Gtk.Align.START)

        self._expand = glyph_toggle("au-expand-btn", "Channels")
        self._expand.set_label(ICON["expand"])
        self._expand.connect("toggled", self._on_expand_toggled)
        self._expand.set_valign(Gtk.Align.START)
        main.append(self._expand)
        self.append(main)

        self._revealer = self._channel_panel()
        self.append(self._revealer)

    # --- construction helpers ---

    def _channel_panel(self) -> Gtk.Revealer:
        """Lock toggle and the per-channel sliders, hidden until expanded."""
        revealer = Gtk.Revealer()
        chan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        chan_box.add_css_class("au-channels")
        lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lock_label = Gtk.Label(label="Lock channels", xalign=0, hexpand=True)
        lock_label.add_css_class("au-channel-name")
        lock_row.append(lock_label)
        self._lock = glyph_toggle("au-lock-btn", "Lock channels together")
        self._lock.connect("toggled", self._on_lock_toggled)
        self._lock.set_active(True)
        self._on_lock_toggled(self._lock)
        lock_row.append(self._lock)
        chan_box.append(lock_row)
        self._chan_grid = Gtk.Grid(column_spacing=6, row_spacing=0)
        chan_box.append(self._chan_grid)
        revealer.set_child(chan_box)
        return revealer

    @staticmethod
    def _level_labels() -> tuple[Gtk.Label, Gtk.Label]:
        pct = Gtk.Label(xalign=1)
        pct.set_width_chars(4)
        pct.add_css_class("au-pct")
        db = Gtk.Label(xalign=1)
        db.set_width_chars(8)
        db.add_css_class("au-db")
        return pct, db

    def _add_marks(self, scale: Gtk.Scale, *, labeled: bool) -> None:
        """Silence and 100% marks, plus the device's hardware base volume if it has one."""
        scale.clear_marks()
        scale.add_mark(0, Gtk.PositionType.BOTTOM, "Silence" if labeled else None)
        scale.add_mark(100, Gtk.PositionType.BOTTOM, "100% (0 dB)" if labeled else None)
        if 0 < self._base < 1:
            scale.add_mark(
                self._base * 100, Gtk.PositionType.BOTTOM, "Base" if labeled else None
            )

    def _make_scale(
        self, on_change: Callable[[Gtk.Scale], None], *, labeled: bool = False
    ) -> tuple[Gtk.Scale, int]:
        adj = Gtk.Adjustment(
            lower=0, upper=VOLUME_UI_MAX, step_increment=1, page_increment=SCROLL_STEP
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_round_digits(0)
        if labeled:
            scale.add_css_class("au-labeled")
        self._add_marks(scale, labeled=labeled)
        handler = scale.connect("value-changed", on_change)

        press = Gtk.EventControllerLegacy()
        press.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        press.connect("event", self._on_scale_event)
        scale.add_controller(press)
        pass_wheel(scale)
        return scale, handler

    def _rebuild_channels(self, names: list[str]) -> None:
        """Channel map changed (rare): recreate only this control's channel sliders."""
        while child := self._chan_grid.get_first_child():
            self._chan_grid.remove(child)
        self._chan_scales = []
        for i, name in enumerate(names):
            label = Gtk.Label(label=channel_label(name), xalign=0)
            label.set_width_chars(12)
            label.add_css_class("au-channel-name")
            scale, handler = self._make_scale(
                partial(self._on_channel_changed, index=i)
            )
            scale.set_hexpand(True)
            pct, db = self._level_labels()
            self._chan_grid.attach(label, 0, i, 1, 1)
            self._chan_grid.attach(scale, 1, i, 1, 1)
            self._chan_grid.attach(pct, 2, i, 1, 1)
            self._chan_grid.attach(db, 3, i, 1, 1)
            self._chan_scales.append((scale, handler, pct, db))
        self._channels = list(names)
        multi = len(names) > 1
        self._expand.set_sensitive(multi)
        self._expand.set_opacity(1 if multi else 0)
        if not multi:
            self._expand.set_active(False)

    # --- server -> UI ---

    def set_base(self, base: float) -> None:
        """Hardware base volume of a device (1.0 = none); marked on every slider."""
        if base == self._base:
            return
        self._base = base
        self._add_marks(self._scale, labeled=True)
        for scale, *_ in self._chan_scales:
            self._add_marks(scale, labeled=False)

    def update(self, values: list[float], channels: list[str], *, mute: bool) -> None:
        """Apply server state. Volume is held back while the user interacts."""
        with self._mute.handler_block(self._mute_handler):
            self._mute.set_active(mute)
        self._mute.set_label(ICON[self._icons[1] if mute else self._icons[0]])
        self._mute.set_tooltip_text("Unmute" if mute else "Mute")
        if list(channels) != self._channels:
            self._rebuild_channels(channels)
            self._show(values)  # new sliders need values even mid-drag
            self._values = list(values)
            return
        if self._busy():
            self._pending = list(values)
            return
        self._values = list(values)
        self._show(values)

    def _show(self, values: list[float], source: Gtk.Scale | None = None) -> None:
        """Set sliders and labels. `source` (the slider being moved) is left alone:
        setting a scale from inside its own value-changed makes GTK re-emit."""
        peak = max(values, default=0)
        if source is not self._scale:
            with self._scale.handler_block(self._scale_handler):
                self._scale.set_value(peak * 100)
        self._pct.set_text(f"{round(peak * 100)}%")
        self._db.set_text(volume_db(peak))
        # a channel map shorter than its values (or longer) shows what pairs up
        for (scale, handler, pct, db), v in zip(
            self._chan_scales, values, strict=False
        ):
            if scale is not source:
                with scale.handler_block(handler):
                    scale.set_value(v * 100)
            pct.set_text(f"{round(v * 100)}%")
            db.set_text(volume_db(v))

    # --- peak meter ---

    def show_meter(self, *, visible: bool) -> None:
        if self._meter is not None:
            self._meter.set_visible(visible)
            self.meter_step(0.0, None)

    def meter_step(self, peak: float, dt: float | None) -> float:
        """One frame: jump up to linear sample `peak` (drawn cubic), else fall
        METER_DECAY per second. dt None resets to `peak`. Returns the position shown."""
        if self._meter is None:
            return 0.0
        peak = meter_position(peak)
        level = peak if dt is None else max(peak, self._level - METER_DECAY * dt, 0.0)
        if level != self._level:
            self._level = level
            self._meter.set_value(level)
        return level

    # --- interaction tracking ---

    def _busy(self) -> bool:
        return self._pressed or time.monotonic() < self._busy_until

    def _touch(self) -> None:
        """Extend the grace window and schedule a one-shot resync at its end."""
        self._busy_until = time.monotonic() + DRAG_GRACE
        if self._resync_id:
            GLib.source_remove(self._resync_id)
        self._resync_id = GLib.timeout_add(int(DRAG_GRACE * 1000) + 10, self._resync)

    def _resync(self) -> bool:
        self._resync_id = 0
        if self._busy():
            self._resync_id = GLib.timeout_add(int(DRAG_GRACE * 1000), self._resync)
            return GLib.SOURCE_REMOVE
        if self._pending is not None:
            self._values, self._pending = self._pending, None
            self._show(self._values)
        return GLib.SOURCE_REMOVE

    def _on_scale_event(
        self, ctrl: Gtk.EventControllerLegacy, _event: Gdk.Event | None
    ) -> bool:
        # PyGObject passes None for the GdkEvent argument; ask the controller.
        event = ctrl.get_current_event()
        if event is None:
            return False
        kind = event.get_event_type()
        if kind in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.TOUCH_BEGIN):
            self._pressed = True
        elif kind in (
            Gdk.EventType.BUTTON_RELEASE,
            Gdk.EventType.TOUCH_END,
            Gdk.EventType.TOUCH_CANCEL,
        ):
            self._pressed = False
            self._touch()
        return False

    # --- UI -> server ---

    def _commit(self, values: list[float], source: Gtk.Scale) -> None:
        self._touch()
        self._values = values
        self._show(values, source)
        self._on_volume(values)

    def _on_main_changed(self, scale: Gtk.Scale) -> None:
        self._commit(scale_volume(self._values, scale.get_value() / 100), scale)

    def _on_channel_changed(self, scale: Gtk.Scale, index: int) -> None:
        v = scale.get_value() / 100
        if self._lock.get_active():
            self._commit(scale_volume(self._values, v), scale)
        else:
            values = list(self._values)
            values[index] = v
            self._commit(values, scale)

    def _on_mute_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._on_mute(btn.get_active())

    def _on_expand_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._revealer.set_reveal_child(btn.get_active())
        btn.set_label(ICON["collapse"] if btn.get_active() else ICON["expand"])

    @staticmethod
    def _on_lock_toggled(btn: Gtk.ToggleButton) -> None:
        btn.set_label(ICON["lock"] if btn.get_active() else ICON["unlock"])


def title_label(text: str, css_class: str = "au-row-title") -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0, hexpand=True)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    label.add_css_class(css_class)
    return label


class DeviceRow(Gtk.Box):
    """Sink or source: volume, set-as-default, port choice, latency offset."""

    def __init__(self, app: AudioPopup, kind: DeviceKind, index: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self._app, self.index = app, index
        self._kind: DeviceKind = kind
        self.info: PulseSinkInfo | PulseSourceInfo | None = None
        self._card: PulseCardInfo | None = None
        self._card_port: PulseCardPortInfo | None = None

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._title = CopyLabel("au-row-title")
        header.append(self._title)
        self._rec_time = Gtk.Label()
        self._record = glyph_button("au-record-btn", "Record")
        if kind == "source":
            self._rec_time.add_css_class("au-rec-time")
            self._rec_time.set_visible(False)
            header.append(self._rec_time)
            self._record.set_label(ICON["record"])
            self._record.connect("clicked", self._on_record_clicked)
            header.append(self._record)
        self._default = glyph_button("au-default-btn")
        self._default.connect("clicked", self._on_default_clicked)
        header.append(self._default)
        self.append(header)

        self.volume = VolumeControl(
            partial(app.set_volume, kind, index),
            lambda mute: app.set_mute(kind, index, mute=mute),
            mic=(kind == "source"),
            meter=app.show_meters,
        )
        self.append(self.volume)

        self._port_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label="Port", xalign=0, hexpand=True)
        label.add_css_class("au-field-label")
        self._port_row.append(label)
        self._ports = Choice[str](self._on_port_picked, 30)
        self._port_row.append(self._ports)
        self.append(self._port_row)

        self._latency_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label="Latency offset", xalign=0, hexpand=True)
        label.add_css_class("au-field-label")
        self._latency_row.append(label)
        adj = Gtk.Adjustment(
            lower=-LATENCY_RANGE_MS,
            upper=LATENCY_RANGE_MS,
            step_increment=1,
            page_increment=10,
        )
        self._latency = Gtk.SpinButton(adjustment=adj, numeric=True)
        self._latency.set_width_chars(5)
        self._latency.add_css_class("au-spin")
        pass_wheel(self._latency)
        self._latency_handler = self._latency.connect("value-changed", self._on_latency)
        self._latency_row.append(self._latency)
        unit = Gtk.Label(label="ms")
        unit.add_css_class("au-field-label")
        self._latency_row.append(unit)
        self.append(self._latency_row)

    def update(
        self,
        info: PulseSinkInfo | PulseSourceInfo,
        card: PulseCardInfo | None,
        *,
        is_default: bool,
    ) -> None:
        self.info = info
        self._title.set_content(
            info.description,
            f"{info.description} ({info.name})",
            f"{info.description}\n{info.name}",
        )
        self.volume.set_base(info.base_volume)
        self.volume.update(info.volume.values, info.channel_list, mute=bool(info.mute))

        items = [
            (
                p.name,
                p.description + (" (unplugged)" if p.available == "no" else ""),
                p.available != "no",
            )
            for p in info.port_list
        ]
        show_ports = len(items) >= 2
        self._port_row.set_visible(show_ports)
        if show_ports:
            self._ports.set_items(
                items, info.port_active.name if info.port_active else None
            )
        self.update_context(card, is_default=is_default)

    def update_context(self, card: PulseCardInfo | None, *, is_default: bool) -> None:
        """Parts owned by other objects: the server default and the card's port latency."""
        self._default.set_label(ICON["default" if is_default else "not_default"])
        self._default.set_tooltip_text(
            "Default device" if is_default else "Set as default"
        )
        if is_default:
            self._default.add_css_class("au-default-on")
        else:
            self._default.remove_css_class("au-default-on")

        port = self.info.port_active if self.info else None
        active = port.name if port else None
        card_port = None
        if card is not None and active:
            card_port = next((p for p in card.port_list if p.name == active), None)
        self._card, self._card_port = card, card_port
        self._latency_row.set_visible(card_port is not None)
        # don't overwrite a value the user is typing
        if card_port is not None and self._latency.get_focus_child() is None:
            with self._latency.handler_block(self._latency_handler):
                self._latency.set_value(card_port.latency_offset / 1000)

    def show_record(self, state: RecordState, seconds: float, *, enabled: bool) -> None:
        """Test recording controls (sources only)."""
        busy = state != "idle"
        self._record.set_label(ICON["stop" if busy else "record"])
        self._record.set_tooltip_text("Stop" if busy else "Record")
        self._record.set_sensitive(enabled)
        for name in ("recording", "playing"):
            if state == name:
                self._record.add_css_class(f"au-rec-{name}")
                self._rec_time.add_css_class(f"au-rec-{name}")
            else:
                self._record.remove_css_class(f"au-rec-{name}")
                self._rec_time.remove_css_class(f"au-rec-{name}")
        self._rec_time.set_visible(busy)
        self._rec_time.set_text(f"{int(seconds) // 60}:{int(seconds) % 60:02}")

    def _on_record_clicked(self, _btn: Gtk.Button) -> None:
        self._app.toggle_record(self)

    def _on_default_clicked(self, _btn: Gtk.Button) -> None:
        if self.info is not None:
            self._app.set_default_device(self._kind, self.info.name)

    def _on_port_picked(self, port: str) -> None:
        self._app.set_port(self._kind, self.index, port, self._ports)

    def _on_latency(self, spin: Gtk.SpinButton) -> None:
        if self._card is not None and self._card_port is not None:
            self._app.set_latency(
                self._card.name, self._card_port.name, int(spin.get_value()) * 1000
            )

    def matches(self, flt: str) -> bool:
        if self.info is None:
            return False
        monitor = (
            isinstance(self.info, PulseSourceInfo)
            and self.info.monitor_of_sink != PA_INVALID
        )
        # pipewire-pulse sets PA_SINK_HARDWARE on every node, null sinks
        # included; a device API (alsa, bluez5, ...) marks real hardware.
        hardware = "device.api" in self.info.proplist and not monitor
        return {
            "all": True,
            "hardware": hardware,
            "virtual": not hardware,
            "no-monitors": not monitor,
            "monitors": monitor,
        }[flt]


class StreamRow(Gtk.Box):
    """Sink input or source output: app, media name, volume, device to move to."""

    def __init__(self, app: AudioPopup, kind: StreamKind, index: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self._app, self.index = app, index
        self._kind: StreamKind = kind
        self.info: PulseSinkInputInfo | PulseSourceOutputInfo | None = None

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._icon = Gtk.Image()
        self._icon.set_pixel_size(24)
        header.append(self._icon)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
        names.set_valign(Gtk.Align.CENTER)
        self._app_name = title_label("")
        self._media = title_label("", "au-row-subtitle")
        names.append(self._app_name)
        names.append(self._media)
        header.append(names)
        self._device = Choice[int](self._on_device_picked, 18)
        self._device.set_valign(Gtk.Align.CENTER)
        header.append(self._device)
        kill = glyph_button(
            "au-kill-btn",
            "Terminate playback" if kind == "sink_input" else "Terminate recording",
        )
        kill.set_label(ICON["kill"])
        kill.connect("clicked", self._on_kill_clicked)
        header.append(kill)
        self.append(header)

        self.volume = VolumeControl(
            partial(app.set_volume, kind, index),
            lambda mute: app.set_mute(kind, index, mute=mute),
            mic=(kind == "source_output"),
            meter=app.show_meters,
        )
        self.append(self.volume)

    def update(
        self,
        info: PulseSinkInputInfo | PulseSourceOutputInfo,
        devices: list[tuple[int, str]],
    ) -> None:
        self.info = info
        props = info.proplist
        self._icon.set_from_icon_name(
            props.get("application.icon_name") or "audio-card"
        )
        self._app_name.set_text(props.get("application.name") or info.name or "Unknown")
        media = props.get("media.name") or info.name or ""
        self._media.set_text(media)
        self._media.set_tooltip_text(media)
        self.volume.update(info.volume.values, info.channel_list, mute=bool(info.mute))
        self.update_devices(devices)

    def update_devices(self, devices: list[tuple[int, str]]) -> None:
        """devices: [(index, description)] of sinks (playback) or sources (recording)."""
        match self.info:
            case None:
                return
            case PulseSinkInputInfo() as info:
                current = info.sink
            case info:
                current = info.source
        self._device.set_items([(i, d, True) for i, d in devices], current)

    def _on_device_picked(self, device: int) -> None:
        self._app.move_stream(self._kind, self.index, device, self._device)

    def _on_kill_clicked(self, _btn: Gtk.Button) -> None:
        self._app.kill_stream(self._kind, self.index)

    def matches(self, flt: str) -> bool:
        if self.info is None:
            return False
        virtual = self.info.client == PA_INVALID
        return {"all": True, "apps": not virtual, "virtual": virtual}[flt]


class EventSoundsRow(Gtk.Box):
    """stream-restore entry for event sounds (system sounds volume and mute)."""

    def __init__(self, app: AudioPopup) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self.info: PulseExtStreamRestoreInfo | None = None
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label=ICON["bell"])
        icon.add_css_class("au-glyph-icon")
        header.append(icon)
        header.append(title_label("System Sounds"))
        self.append(header)
        self.volume = VolumeControl(
            app.set_event_volume, lambda mute: app.set_event_mute(mute=mute)
        )
        self.append(self.volume)

    def update(self, info: PulseExtStreamRestoreInfo) -> None:
        self.info = info
        self.volume.update(info.volume.values, info.channel_list, mute=bool(info.mute))

    def matches(self, flt: str) -> bool:
        return self.info is not None and flt in ("all", "apps")


class CardRow(Gtk.Box):
    """Card description and profile choice."""

    def __init__(self, app: AudioPopup, index: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self._app, self.index = app, index
        self.info: PulseCardInfo | None = None
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label=ICON["card"])
        icon.add_css_class("au-glyph-icon")
        header.append(icon)
        self._title = CopyLabel("au-row-title")
        header.append(self._title)
        self.append(header)
        profile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label="Profile", xalign=0)
        label.add_css_class("au-field-label")
        profile_row.append(label)
        self._profiles = Choice[str](self._on_profile_picked, 40)
        self._profiles.set_hexpand(True)
        profile_row.append(self._profiles)
        self.append(profile_row)

    def update(self, info: PulseCardInfo) -> None:
        self.info = info
        desc = info.proplist.get("device.description") or info.name
        self._title.set_content(desc, f"{desc} ({info.name})", f"{desc}\n{info.name}")
        profiles = sorted(info.profile_list, key=lambda p: -p.priority)
        items = [
            (
                p.name,
                p.description + ("" if p.available else " (unavailable)"),
                bool(p.available),
            )
            for p in profiles
        ]
        self._profiles.set_items(items, info.profile_active.name)

    def _on_profile_picked(self, profile: str) -> None:
        self._app.set_profile(self.index, profile, self._profiles)

    def matches(self, _flt: str) -> bool:
        return self.info is not None


type Row = DeviceRow | StreamRow | CardRow


class Tab:
    """One stack page: scrolling row list, empty message and optional filter."""

    def __init__(self, spec: TabSpec, on_filter: Callable[[Tab, str], None]) -> None:
        self.rows: dict[int, Row] = {}
        self.extra_rows: list[EventSoundsRow] = []  # not keyed by pulse index
        self.filter = spec.default_filter
        self.page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.empty = Gtk.Label(label=spec.empty)
        self.empty.add_css_class("au-empty")
        self.list.append(self.empty)

        scroll = VScroller(460, self.list)
        scroll.set_vexpand(True)
        self.page.append(scroll)

        if spec.filters:
            bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            bar.add_css_class("au-filter-bar")
            label = Gtk.Label(label="Show", xalign=0)
            label.add_css_class("au-field-label")
            bar.append(label)
            items = [(k, label, True) for k, label in spec.filters]

            def pick(flt: str) -> None:
                # a local setting: nothing confirms it later, so it is the
                # active item right away (else picking back the old one is ignored)
                choice.set_items(items, flt)
                on_filter(self, flt)

            choice = Choice[str](pick)
            choice.set_items(items, spec.default_filter)
            bar.append(choice)
            self.page.append(bar)

    def add(self, index: int, row: Row) -> None:
        self.rows[index] = row
        self.list.append(row)

    def remove(self, index: int) -> None:
        row = self.rows.pop(index, None)
        if row is not None:
            self.list.remove(row)

    def refilter(self) -> None:
        shown = False
        for row in [*self.rows.values(), *self.extra_rows]:
            visible = row.matches(self.filter)
            row.set_visible(visible)
            shown = shown or visible
        self.empty.set_visible(not shown)


@dataclass(frozen=True, slots=True)
class Event:
    """A pulse event the popup follows."""

    facility: Facility | Literal["server"]
    index: int  # 0 for the server
    removed: bool


class EventListener:
    """Runs the event connection's blocking listen loop; forwards events only."""

    def __init__(
        self,
        pulse: Pulse,
        on_event: Callable[[Event], bool],
        on_disconnect: Callable[[], bool],
    ) -> None:
        self._pulse, self._on_event, self._on_disconnect = (
            pulse,
            on_event,
            on_disconnect,
        )
        self._stopping = self._closed = False
        self._lock = threading.Lock()

    def start(self, on_bug: Callable[[str], bool | None]) -> None:
        in_background(self._run, on_bug)

    def _run(self) -> None:
        self._pulse.event_callback_set(self._forward)
        try:
            # the server went away: on_disconnect reconnects
            with contextlib.suppress(pulsectl.PulseError, pulsectl.PulseDisconnected):
                while not self._stopping:
                    self._pulse.event_listen()
        finally:
            with self._lock:
                self._closed = True
                self._pulse.close()
            if not self._stopping:
                GLib.idle_add(self._on_disconnect)

    def _forward(self, ev: PulseEventInfo) -> None:
        """Never call pulsectl from the callback: just hand the event to GTK."""
        # pulsectl's event fields are string enums that only compare equal to a str
        for facility in EVENT_FACILITIES:
            if ev.facility == facility:
                event = Event(facility, ev.index, removed=ev.t == "remove")
                GLib.idle_add(self._on_event, event)
                return

    def stop(self) -> None:
        """Thread-safe: wakes the listen loop unless the thread already closed it."""
        with self._lock:
            self._stopping = True
            if not self._closed:
                self._pulse.event_listen_stop()


class AudioPopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self._cmd: Pulse | None = None
        self._events: EventListener | None = None
        self._connected = False
        self._backoff = 0
        self._reconnect_id = 0
        # (facility, index) -> removed, coalesced until the next flush
        self._pending: dict[tuple[Facility | Literal["server"], int], bool] = {}
        self._flush_id = 0
        self._defaults: dict[DeviceKind, str | None] = {"sink": None, "source": None}
        self._sinks: dict[int, PulseSinkInfo] = {}
        self._sources: dict[int, PulseSourceInfo] = {}
        self._cards: dict[int, PulseCardInfo] = {}
        self._state = load_state()
        self.show_meters = self._state.meters
        self._meters: Meters[MeterKey] | None = None
        self._meter_targets: dict[MeterKey, MeterSpec] = {}  # sent to the meter thread
        self._meter_sync_id = self._tick_id = 0
        self._frame_time = 0.0
        self._recorder = Recorder(self._on_record_change, self._show_bug)
        self._record_tick_id = 0

    # --- UI ---

    @override
    def build_ui(self) -> Gtk.Widget:
        self._container, header = popup_frame()

        meters = glyph_toggle("au-meters-btn", "Show volume meters")
        meters.set_label(ICON["meters"])
        meters.set_active(self.show_meters)
        meters.connect("toggled", self._on_meters_toggled)
        header.append(meters)

        self._bug = copyable(Gtk.Label(wrap=True, xalign=0))
        self._bug.add_css_class("au-bug")
        self._bug.set_visible(False)
        self._container.append(self._bug)

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tab_bar.add_css_class("au-tab-bar")
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self._stack.set_vhomogeneous(False)
        self._stack.set_hhomogeneous(True)
        self._tabs: dict[TabKey, Tab] = {}
        self._tab_buttons: dict[TabKey, Gtk.Button] = {}
        for n, spec in enumerate(TABS, 1):
            btn = Gtk.Button(label=spec.label)
            btn.add_css_class("au-tab-btn")
            btn.set_tooltip_text(f"{spec.label} ({n})")
            btn.connect("clicked", self._on_tab_clicked, spec.key)
            tab_bar.append(btn)
            self._tab_buttons[spec.key] = btn
            tab = Tab(spec, self._on_filter)
            self._tabs[spec.key] = tab
            self._stack.add_named(tab.page, spec.key)
        self._container.append(tab_bar)

        self._offline = error_box("Not connected", "Waiting for the sound server…")
        self._offline.set_visible(False)
        self._container.append(self._offline)
        self._container.append(self._stack)

        self._event_row = EventSoundsRow(self)
        self._event_row.set_visible(False)
        playback = self._tabs["playback"]
        playback.extra_rows.append(self._event_row)
        playback.list.insert_child_after(self._event_row, playback.empty)

        last = self._state.tab
        self._switch_tab(last if last in TAB_KEYS else "playback", save=False)
        # widget-toggle closes the popup with SIGTERM: quit cleanly so do_shutdown
        # stops a test recording's parec/pacat
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_sigterm)
        self._connect()
        return self._container

    def _on_sigterm(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def _show_bug(self, msg: str) -> bool:
        """A worker thread's bug, on the line under the header."""
        self._bug.set_text(msg)
        self._bug.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _on_tab_clicked(self, _btn: Gtk.Button, key: TabKey) -> None:
        self._switch_tab(key)

    def _switch_tab(self, key: TabKey, *, save: bool = True) -> None:
        if key != self._stack.get_visible_child_name():
            self._recorder.cancel()
        self._stack.set_visible_child_name(key)
        self._queue_meters()
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.add_css_class("au-tab-active")
            else:
                btn.remove_css_class("au-tab-active")
        if save and self._state.tab != key:
            self._state.tab = key
            save_state(self._state)

    def _on_filter(self, tab: Tab, flt: str) -> None:
        tab.filter = flt
        self._recorder.cancel()
        tab.refilter()
        self._queue_meters()

    def _on_meters_toggled(self, btn: Gtk.ToggleButton) -> None:
        self.show_meters = btn.get_active()
        for tab in self._tabs.values():
            for row in tab.rows.values():
                if isinstance(row, (DeviceRow, StreamRow)):
                    row.volume.show_meter(visible=self.show_meters)
        self._state.meters = self.show_meters
        save_state(self._state)
        self._queue_meters()

    @override
    def _on_key(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        win = self.get_active_window()
        focus = win.get_focus() if win else None
        editing = isinstance(focus, Gtk.Text)
        if keyval == Gdk.KEY_q and editing:
            return False
        if not editing and Gdk.KEY_1 <= keyval <= Gdk.KEY_5:
            self._switch_tab(TAB_KEYS[keyval - Gdk.KEY_1])
            return True
        return super()._on_key(_controller, keyval, _keycode, _state)

    # --- connection lifecycle ---

    def _connect(self) -> None:
        """Open both connections, start the event thread, sync every list."""
        cmd = events = None
        try:
            # No connect(timeout=...): pulsectl then always waits the full timeout.
            # A missing server fails immediately anyway.
            cmd = Pulse("gtk-widgets-audio")
            events = Pulse("gtk-widgets-audio-events")
            events.event_mask_set("all")
        except pulsectl.PulseError:
            for p in (cmd, events):
                if p is not None:
                    p.close()
            self._set_online(online=False)
            self._schedule_reconnect()
            return
        self._cmd = cmd
        self._events = EventListener(events, self._apply_event, self._on_disconnected)
        self._events.start(self._show_bug)
        # connects on its own thread; picks up the targets _sync_all() queues
        self._meters = Meters[MeterKey](self._on_peaks)
        self._meters.start(self._show_bug)
        self._connected, self._backoff = True, 0
        self._set_online(online=True)
        self._sync_all()

    def _schedule_reconnect(self) -> None:
        delay = min(BACKOFF_START * 2**self._backoff, BACKOFF_MAX)
        self._backoff += 1
        self._reconnect_id = GLib.timeout_add(int(delay * 1000), self._reconnect)

    def _reconnect(self) -> bool:
        self._reconnect_id = 0
        self._connect()
        return GLib.SOURCE_REMOVE

    def _on_disconnected(self) -> bool:
        if not self._connected:
            return GLib.SOURCE_REMOVE
        self._connected = False
        if self._events:
            self._events.stop()
            self._events = None
        self._stop_meters()
        self._recorder.cancel()
        if self._cmd:
            self._cmd.close()
            self._cmd = None
        self._pending.clear()
        self._set_online(online=False)
        self._schedule_reconnect()
        return GLib.SOURCE_REMOVE

    def _set_online(self, *, online: bool) -> None:
        self._offline.set_visible(not online)
        self._stack.set_visible(online)

    def _call[T](self, fn: Callable[[Pulse], T]) -> T | None:
        """Run a command-connection call; None on failure (disconnect handled)."""
        cmd = self._cmd
        if not self._connected or cmd is None:
            return None
        try:
            return fn(cmd)
        except pulsectl.PulseError:
            if not cmd.connected:
                self._on_disconnected()
            return None

    # --- sync ---

    def _sync_all(self) -> None:
        """Full read after (re)connect; rows are diffed by index, not rebuilt."""
        server = self._call(Pulse.server_info)
        cards = self._call(Pulse.card_list)
        sinks = self._call(Pulse.sink_list)
        sources = self._call(Pulse.source_list)
        sink_inputs = self._call(Pulse.sink_input_list)
        source_outputs = self._call(Pulse.source_output_list)
        if (
            server is None
            or cards is None
            or sinks is None
            or sources is None
            or sink_inputs is None
            or source_outputs is None
        ):
            return
        self._defaults = {
            "sink": server.default_sink_name,
            "source": server.default_source_name,
        }
        lists: list[tuple[Facility, list[Info]]] = [
            ("card", [*cards]),
            ("sink", [*sinks]),
            ("source", [*sources]),
            ("sink_input", [*sink_inputs]),
            ("source_output", [*source_outputs]),
        ]
        for fac, infos in lists:
            seen: set[int] = set()
            for info in infos:
                seen.add(info.index)
                self._upsert(info)
            for index in list(self._rows(fac)):
                if index not in seen:
                    self._remove(fac, index)
        self._sync_event_sounds()
        self._refresh_after("sink")
        self._refresh_after("source")
        for tab in self._tabs.values():
            tab.refilter()
        self._queue_meters()

    def _sync_event_sounds(self) -> None:
        entries = self._call(Pulse.stream_restore_list) or []
        entry = next((e for e in entries if e.name == EVENT_ROLE), None)
        if entry is not None:
            self._event_row.update(entry)
        self._event_row.info = entry
        self._tabs["playback"].refilter()

    def _apply_event(self, event: Event) -> bool:
        """Main-thread side of the event thread. Coalesces bursts per object."""
        if not self._connected:
            return GLib.SOURCE_REMOVE
        index = 0 if event.facility == "server" else event.index
        # last event wins; a fetch re-reads
        self._pending[event.facility, index] = event.removed
        if not self._flush_id:
            self._flush_id = GLib.idle_add(self._flush)
        return GLib.SOURCE_REMOVE

    def _flush(self) -> bool:
        self._flush_id = 0
        pending, self._pending = self._pending, {}
        touched: set[Facility] = set()
        for (facility, index), removed in pending.items():
            if not self._connected:
                break
            if facility == "server":
                server = self._call(Pulse.server_info)
                if server is not None:
                    self._defaults = {
                        "sink": server.default_sink_name,
                        "source": server.default_source_name,
                    }
                    touched.update(("sink", "source"))
                continue
            touched.add(facility)
            if removed:
                self._remove(facility, index)
                continue
            info = self._fetch(facility, index)
            if info is None:
                if self._connected:
                    self._remove(facility, index)
            else:
                self._upsert(info)
        for facility in touched:
            self._refresh_after(facility)
        self._queue_meters()
        return GLib.SOURCE_REMOVE

    def _fetch(self, facility: Facility, index: int) -> Info | None:
        cmd = self._cmd
        if cmd is None:
            return None
        try:
            return INFO[facility](cmd, index)
        except pulsectl.PulseIndexError:
            return None
        except pulsectl.PulseError:
            if not cmd.connected:
                self._on_disconnected()
            return None

    # --- rows ---

    def _tab_for(self, facility: Facility) -> Tab:
        return self._tabs[TAB_OF[facility]]

    def _rows(self, facility: Facility) -> dict[int, Row]:
        return self._tab_for(facility).rows

    def _device_rows(self, kind: DeviceKind) -> dict[int, DeviceRow]:
        return {
            i: row for i, row in self._rows(kind).items() if isinstance(row, DeviceRow)
        }

    def _volume_of(self, key: MeterKey) -> VolumeControl | None:
        row = self._rows(key[0]).get(key[1])
        return row.volume if isinstance(row, (DeviceRow, StreamRow)) else None

    def _devices(self, kind: DeviceKind) -> list[tuple[int, str]]:
        infos = self._sinks if kind == "sink" else self._sources
        return [(i, info.description) for i, info in sorted(infos.items())]

    def _upsert(self, info: Info) -> None:
        app_id = info.proplist.get("application.id")
        match info:
            case PulseSinkInfo() | PulseSourceInfo():
                self._upsert_device(info)
            case PulseSinkInputInfo():
                if app_id == APP_ID:
                    return  # our test recording's playback
                row = self._stream_row("sink_input", info.index)
                if info.proplist.get("module-stream-restore.id") == EVENT_ROLE:
                    row.info = None  # shown by the System Sounds row instead
                else:
                    row.update(info, self._devices("sink"))
            case PulseSourceOutputInfo():
                if app_id in MIXER_APP_IDS:
                    return  # a meter stream (ours or another mixer's) or our test recording
                self._stream_row("source_output", info.index).update(
                    info, self._devices("source")
                )
            case PulseCardInfo():
                self._cards[info.index] = info
                row = self._rows("card").get(info.index)
                if not isinstance(row, CardRow):
                    row = CardRow(self, info.index)
                    self._tab_for("card").add(info.index, row)
                row.update(info)

    def _upsert_device(self, info: PulseSinkInfo | PulseSourceInfo) -> None:
        kind: DeviceKind
        if isinstance(info, PulseSinkInfo):
            kind = "sink"
            self._sinks[info.index] = info
        else:
            kind = "source"
            self._sources[info.index] = info
        row = self._rows(kind).get(info.index)
        if not isinstance(row, DeviceRow):
            row = DeviceRow(self, kind, info.index)
            self._tab_for(kind).add(info.index, row)
        row.update(
            info,
            self._cards.get(info.card),
            is_default=info.name == self._defaults[kind],
        )
        if kind == "source" and self._recorder.state != "idle":
            self._show_record()  # a new row is disabled while a recording runs

    def _stream_row(self, kind: StreamKind, index: int) -> StreamRow:
        row = self._rows(kind).get(index)
        if not isinstance(row, StreamRow):
            row = StreamRow(self, kind, index)
            self._tab_for(kind).add(index, row)
        return row

    def _remove(self, facility: Facility, index: int) -> None:
        if facility == "source" and index == self._recorder.source:
            self._recorder.cancel()
        match facility:
            case "sink":
                self._sinks.pop(index, None)
            case "source":
                self._sources.pop(index, None)
            case "card":
                self._cards.pop(index, None)
            case _:
                pass
        self._tab_for(facility).remove(index)

    def _refresh_after(self, facility: Facility) -> None:
        """Propagate a change to rows that depend on it, then refilter."""
        if facility in ("sink", "source"):
            kind: DeviceKind = "sink" if facility == "sink" else "source"
            self._refresh_device_context(kind)
            streams: StreamKind = "sink_input" if kind == "sink" else "source_output"
            devices = self._devices(kind)
            for row in self._rows(streams).values():
                if isinstance(row, StreamRow):
                    row.update_devices(devices)
            self._tab_for(streams).refilter()
        elif facility == "card":
            # latency offsets live on card ports
            self._refresh_device_context("sink")
            self._refresh_device_context("source")
        self._tab_for(facility).refilter()

    def _refresh_device_context(self, kind: DeviceKind) -> None:
        default = self._defaults[kind]
        for row in self._device_rows(kind).values():
            if row.info is not None:
                row.update_context(
                    self._cards.get(row.info.card), is_default=row.info.name == default
                )

    # --- peak meters ---

    def _queue_meters(self) -> None:
        """Resync meter streams once the current burst of changes is applied."""
        if not self._meter_sync_id:
            self._meter_sync_id = GLib.idle_add(self._sync_meters)

    def _wanted_meters(self) -> dict[MeterKey, MeterSpec]:
        """Streams for the rows shown on the visible tab: {(facility, index): spec}.

        Like pavucontrol, monitors (outputs, playback, monitor sources) are
        metered passively and microphones actively: opening the Input Devices
        tab wakes a suspended mic so its meter shows input. A suspended device
        behind a passive meter is skipped: it carries no audio, and
        pipewire-pulse keeps a passive stream on it in the creating state,
        where it can't be disconnected. Its state change event on resume
        brings the meter back.
        """
        if self._meters is None or not self.show_meters:
            return {}
        key = self._stack.get_visible_child_name()
        spec = next((t for t in TABS if t.key == key), None)
        if spec is None:
            return {}
        targets: dict[MeterKey, MeterSpec] = {}
        for index, row in self._tabs[spec.key].rows.items():
            if not row.get_visible():
                continue
            device: PulseSinkInfo | PulseSourceInfo | None
            match row.info:
                case PulseSinkInfo() as info:
                    device, source, stream = info, info.monitor_source, None
                case PulseSourceInfo() as info:
                    device, source, stream = info, info.index, None
                case PulseSinkInputInfo() as info:
                    device = self._sinks.get(info.sink)
                    source = device.monitor_source if device else PA_INVALID
                    stream = info.index
                case PulseSourceOutputInfo() as info:
                    device = self._sources.get(info.source)
                    source, stream = info.source, None
                case _:
                    continue  # not loaded yet; cards have no volume
            if device is None or source == PA_INVALID:
                continue
            # the source of a sink's meter is its monitor; a source's is itself
            passive = (
                isinstance(device, PulseSinkInfo)
                or device.monitor_of_sink != PA_INVALID
            )
            if passive and device.state == "suspended":
                continue
            targets[spec.facility, index] = (source, stream, passive)
        return targets

    def _sync_meters(self) -> bool:
        self._meter_sync_id = 0
        targets = self._wanted_meters()
        if targets != self._meter_targets:
            self._reset_meters(self._meter_targets.keys() - targets.keys())
            self._meter_targets = targets
            if self._meters is not None:
                self._meters.set_targets(targets)
        return GLib.SOURCE_REMOVE

    def _reset_meters(self, keys: set[MeterKey]) -> None:
        for key in keys:
            volume = self._volume_of(key)
            if volume is not None:
                volume.meter_step(0.0, None)

    def _stop_meters(self) -> None:
        if self._meters is not None:
            self._meters.stop()
            self._meters = None
        self._reset_meters(set(self._meter_targets))
        self._meter_targets = {}

    def _on_peaks(self) -> bool:
        """Meter thread has new peaks: apply them on the next frame."""
        if not self._tick_id and self._meters is not None:
            self._tick_id = self._container.add_tick_callback(self._meter_tick)
        return GLib.SOURCE_REMOVE

    def _meter_tick(self, _widget: Gtk.Widget, clock: Gdk.FrameClock) -> bool:
        """Meter updates at METER_RATE on frame boundaries, until every meter is at zero."""
        now = clock.get_frame_time() / 1e6
        if self._frame_time and now - self._frame_time < 0.9 / METER_RATE:
            # between updates: nothing changes, nothing redraws
            return GLib.SOURCE_CONTINUE
        dt = now - self._frame_time if self._frame_time else 0.0
        self._frame_time = now
        peaks = self._meters.take_peaks() if self._meters is not None else {}
        active = False
        for key in self._meter_targets:
            volume = self._volume_of(key)
            if volume is not None and volume.meter_step(peaks.get(key, 0.0), dt) > 0:
                active = True
        if active:
            return GLib.SOURCE_CONTINUE
        self._tick_id, self._frame_time = 0, 0.0
        return GLib.SOURCE_REMOVE

    # --- test recording ---

    def toggle_record(self, row: DeviceRow) -> None:
        if self._recorder.state == "idle":
            if row.info is not None:
                self._recorder.record(row.info.name, row.index)
        else:
            self._recorder.stop()

    def _on_record_change(self) -> None:
        busy = self._recorder.state != "idle"
        if busy and not self._record_tick_id:
            self._record_tick_id = GLib.timeout_add(RECORD_TICK_MS, self._record_tick)
        self._show_record()

    def _show_record(self) -> None:
        rec = self._recorder
        for index, row in self._device_rows("source").items():
            mine = index == rec.source
            row.show_record(
                rec.state if mine else "idle",
                rec.seconds(),
                enabled=rec.state == "idle" or mine,
            )

    def _record_tick(self) -> bool:
        if self._recorder.state == "idle":
            self._record_tick_id = 0
            return GLib.SOURCE_REMOVE
        source = self._recorder.source
        row = self._device_rows("source").get(source) if source is not None else None
        if row is not None:
            row.show_record(
                self._recorder.state, self._recorder.seconds(), enabled=True
            )
        return GLib.SOURCE_CONTINUE

    # --- writes (command connection, main thread) ---

    def _act(
        self,
        call: Callable[[Pulse], None],
        choice: Choice[str] | Choice[int] | None = None,
    ) -> None:
        """Run a command-connection write; a failed dropdown pick is reverted."""
        cmd = self._cmd
        if self._connected and cmd is not None:
            try:
                call(cmd)
            except pulsectl.PulseError:
                if not cmd.connected:
                    self._on_disconnected()
            else:
                return
        if choice is not None:
            choice.revert()

    def set_volume(
        self, facility: DeviceKind | StreamKind, index: int, values: list[float]
    ) -> None:
        vol = PulseVolumeInfo(list(values))
        self._act(lambda p: VOLUME_SET[facility](p, index, vol))

    def set_mute(
        self, facility: DeviceKind | StreamKind, index: int, *, mute: bool
    ) -> None:
        self._act(lambda p: MUTE[facility](p, index, mute))

    def set_default_device(self, kind: DeviceKind, name: str) -> None:
        self._act(lambda p: DEFAULT_SET[kind](p, name))

    def set_port(
        self, kind: DeviceKind, index: int, port: str, choice: Choice[str]
    ) -> None:
        self._act(lambda p: PORT_SET[kind](p, index, port), choice)

    def move_stream(
        self, kind: StreamKind, index: int, device: int, choice: Choice[int]
    ) -> None:
        self._act(lambda p: MOVE[kind](p, index, device), choice)

    def kill_stream(self, kind: StreamKind, index: int) -> None:
        self._act(lambda p: KILL[kind](p, index))

    def set_profile(self, index: int, profile: str, choice: Choice[str]) -> None:
        self._act(lambda p: p.card_profile_set_by_index(index, profile), choice)

    @staticmethod
    def set_latency(card_name: str, port_name: str, offset_us: int) -> None:
        # pulsectl has no call for this; pactl is the documented fallback.
        subprocess.Popen(
            ["pactl", "set-port-latency-offset", card_name, port_name, str(offset_us)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _write_event_sounds(
        self, *, volume: list[float] | None = None, mute: bool | None = None
    ) -> None:
        entry = self._event_row.info
        if entry is None:
            return
        if volume is not None:
            entry.volume = PulseVolumeInfo(list(volume))
        if mute is not None:
            entry.mute = int(mute)
        restore = PulseExtStreamRestoreInfo(
            entry.name,
            entry.volume,
            entry.channel_list,
            bool(entry.mute),
            entry.device or None,
        )
        self._act(
            lambda p: p.stream_restore_write(
                restore, mode="replace", apply_immediately=True
            )
        )
        # stream-restore writes emit no subscription events; show the new state now
        self._event_row.volume.update(
            entry.volume.values, entry.channel_list, mute=bool(entry.mute)
        )

    def set_event_volume(self, values: list[float]) -> None:
        self._write_event_sounds(volume=values)

    def set_event_mute(self, *, mute: bool) -> None:
        self._write_event_sounds(mute=mute)

    @override
    def do_shutdown(self) -> None:
        if self._reconnect_id:
            GLib.source_remove(self._reconnect_id)
        if self._events:
            self._events.stop()
        if self._meters:
            self._meters.stop()
        self._recorder.cancel()
        if self._cmd:
            self._cmd.close()
        Gtk.Application.do_shutdown(self)
