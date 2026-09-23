#!/usr/bin/env python3
"""Audio popup — GTK4 pavucontrol replacement backed by pulsectl (vendored in lib/).

Three pulse connections: an event connection whose blocking event_listen() runs
in a thread and only forwards events to the GTK main loop, a command connection
used on the main thread for every read and write, and a meter connection with
its own thread for the peak meter streams (meters.py). Rows are keyed by pulse
index and updated in place; the lists are never rebuilt.
"""

import json, math, os, signal, subprocess, sys, threading, time
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from lib.copy_label import CopyLabel
from lib.widget_base import Gdk, Gtk, WidgetPopup

from gi.repository import GLib, Pango

try:
    import lib.pulsectl as pulsectl
    from meters import APP_ID, METER_RATE, MIXER_APP_IDS, MeterThread
    from recorder import Recorder
except OSError:  # libpulse.so.0 missing
    pulsectl = None

PA_INVALID = 2**32 - 1
VOLUME_UI_MAX = 153            # PA_VOLUME_UI_MAX (+11 dB) in percent
SCROLL_STEP = 5                # percent per mouse-wheel notch
DRAG_GRACE = 0.2               # seconds volume events stay ignored after a drag
BACKOFF_START, BACKOFF_MAX = 0.5, 5  # reconnect delay doubles from 0.5 s, capped at 5 s
LATENCY_RANGE_MS = 2000
EVENT_ROLE = "sink-input-by-media-role:event"
METER_DECAY = 0.5              # meter fall per second, in bar lengths


def meter_position(peak):
    """Linear sample peak -> 0..1 on the volume sliders' cubic scale (loud
    speech ~60%). pavucontrol draws linear peaks, which barely move."""
    return min(max(peak, 0.0), 1.0) ** (1 / 3)


# level bar offsets (name, upper bound in dBFS): green, yellow, red near clipping
METER_BANDS = [(name, meter_position(10 ** (db / 20)))
               for name, db in (("low", -6), ("high", -1), ("full", 0))]

STATE_FILE = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "gtk-widgets", "audio.json")

ICON = {
    "speaker": "\U000F057E",      # nf-md-volume_high
    "speaker_mute": "\U000F0581",  # nf-md-volume_off
    "mic": "\U000F036C",          # nf-md-microphone
    "mic_mute": "\U000F036D",     # nf-md-microphone_off
    "lock": "\U000F033E",         # nf-md-lock
    "unlock": "\U000F033F",       # nf-md-lock_open
    "expand": "\U000F0142",       # nf-md-chevron_right
    "collapse": "\U000F0140",     # nf-md-chevron_down
    "default": "\U000F04CE",      # nf-md-star
    "not_default": "\U000F04D2",  # nf-md-star_outline
    "card": "\U000F04C3",         # nf-md-speaker
    "bell": "\U000F009A",         # nf-md-bell
    "offline": "\U000F0581",      # nf-md-volume_off
    "kill": "\U000F0156",         # nf-md-close
    "meters": "\U000F0128",       # nf-md-chart_bar
    "record": "\U000F044A",       # nf-md-record
    "stop": "\U000F04DB",         # nf-md-stop
}

# (key, label, list facility, empty-list message, filters, default filter)
TABS = [
    ("playback", "Playback", "sink_input",
     "No application is currently playing audio.",
     [("all", "All streams"), ("apps", "Applications"), ("virtual", "Virtual streams")], "apps"),
    ("recording", "Recording", "source_output",
     "No application is currently recording audio.",
     [("all", "All streams"), ("apps", "Applications"), ("virtual", "Virtual streams")], "apps"),
    ("outputs", "Output Devices", "sink",
     "No output devices available.",
     [("all", "All"), ("hardware", "Hardware"), ("virtual", "Virtual")], "all"),
    ("inputs", "Input Devices", "source",
     "No input devices available.",
     [("all", "All"), ("no-monitors", "All except monitors"), ("hardware", "Hardware"),
      ("virtual", "Virtual"), ("monitors", "Monitors")], "no-monitors"),
    ("config", "Configuration", "card", "No cards available.", None, None),
]
TAB_KEYS = [t[0] for t in TABS]

CHANNEL_NAMES = {"mono": "Mono", "lfe": "Subwoofer"}


def channel_label(name):
    """Pretty name for a pulse channel position ('front-left' -> 'Front Left')."""
    return CHANNEL_NAMES.get(name) or " ".join(w.capitalize() for w in name.split("-"))


def volume_db(v):
    """pa_sw_volume_to_dB: libpulse volumes are cubic, so dB = 60 * log10(v)."""
    return "-inf dB" if v <= 0 else f"{60 * math.log10(v):+.1f} dB".replace("+0.0", "0.0")


def scale_volume(values, new_max):
    """pa_cvolume_scale: scale all channels so the loudest equals new_max."""
    peak = max(values, default=0)
    if peak <= 0:
        return [new_max] * len(values)
    return [v * new_max / peak for v in values]


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def glyph_button(css_class, tooltip=None, toggle=False):
    btn = Gtk.ToggleButton() if toggle else Gtk.Button()
    btn.add_css_class("au-icon-btn")
    btn.add_css_class(css_class)
    btn.set_valign(Gtk.Align.CENTER)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    return btn


class Choice(Gtk.DropDown):
    """Dropdown of (key, label, enabled) items, updated in place.

    Disabled items are shown dimmed and cannot be picked. Programmatic updates
    never fire the pick callback.
    """

    def __init__(self, on_pick, max_chars=24):
        self._model = Gtk.StringList()
        super().__init__(model=self._model)
        self.add_css_class("au-choice")
        self._keys, self._labels, self._enabled, self._active = [], [], [], None
        self._on_pick = on_pick
        self.set_factory(self._make_factory(max_chars))
        self.set_list_factory(self._make_factory(None))
        self._handler = self.connect("notify::selected", self._on_selected)

    def _make_factory(self, max_chars):
        factory = Gtk.SignalListItemFactory()

        def setup(_f, item):
            label = Gtk.Label(xalign=0)
            if max_chars:
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_max_width_chars(max_chars)
            item.set_child(label)

        def bind(_f, item):
            pos = item.get_position()
            enabled = self._enabled[pos] if pos < len(self._enabled) else True
            label = item.get_child()
            label.set_text(item.get_item().get_string())
            label.set_sensitive(enabled)
            item.set_activatable(enabled)
            item.set_selectable(enabled)

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    def set_items(self, items, active):
        """items: [(key, label, enabled)]; active: key to show as selected."""
        keys = [k for k, _, _ in items]
        labels = [l for _, l, _ in items]
        enabled = [e for _, _, e in items]
        with self.handler_block(self._handler):
            if labels != self._labels or enabled != self._enabled:
                self._labels, self._enabled = labels, enabled
                self._model.splice(0, self._model.get_n_items(), labels)
            self._keys, self._active = keys, active
            pos = keys.index(active) if active in keys else Gtk.INVALID_LIST_POSITION
            if self.get_selected() != pos:
                self.set_selected(pos)

    def revert(self):
        """Show the last server-confirmed item again (after a failed pick)."""
        self.set_items(list(zip(self._keys, self._labels, self._enabled)), self._active)

    def _on_selected(self, *_):
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

    def __init__(self, on_volume, on_mute, mic=False, meter=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._on_volume, self._on_mute = on_volume, on_mute
        self._icons = ("mic", "mic_mute") if mic else ("speaker", "speaker_mute")
        self._values, self._channels = [], []
        self._pressed, self._busy_until, self._pending = False, 0.0, None
        self._resync_id = 0

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._mute = glyph_button("au-mute-btn", "Mute", toggle=True)
        self._mute_handler = self._mute.connect("toggled", self._on_mute_toggled)
        main.append(self._mute)

        self._base = 1.0
        self._scale, self._scale_handler = self._make_scale(self._on_main_changed, labeled=True)
        slider = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
        slider.append(self._scale)
        main.append(slider)

        self._meter, self._level = None, 0.0
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

        self._expand = glyph_button("au-expand-btn", "Channels", toggle=True)
        self._expand.set_label(ICON["expand"])
        self._expand.connect("toggled", self._on_expand_toggled)
        self._expand.set_valign(Gtk.Align.START)
        main.append(self._expand)
        self.append(main)

        self._revealer = Gtk.Revealer()
        chan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        chan_box.add_css_class("au-channels")
        lock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lock_label = Gtk.Label(label="Lock channels", xalign=0, hexpand=True)
        lock_label.add_css_class("au-channel-name")
        lock_row.append(lock_label)
        self._lock = glyph_button("au-lock-btn", "Lock channels together", toggle=True)
        self._lock.connect("toggled", self._on_lock_toggled)
        self._lock.set_active(True)
        self._on_lock_toggled(self._lock)
        lock_row.append(self._lock)
        chan_box.append(lock_row)
        self._chan_grid = Gtk.Grid(column_spacing=6, row_spacing=0)
        chan_box.append(self._chan_grid)
        self._revealer.set_child(chan_box)
        self.append(self._revealer)
        self._chan_scales = []

    # --- construction helpers ---

    @staticmethod
    def _level_labels():
        pct = Gtk.Label(xalign=1)
        pct.set_width_chars(4)
        pct.add_css_class("au-pct")
        db = Gtk.Label(xalign=1)
        db.set_width_chars(8)
        db.add_css_class("au-db")
        return pct, db

    def _add_marks(self, scale, labeled):
        """Silence and 100% marks, plus the device's hardware base volume if it has one."""
        scale.clear_marks()
        scale.add_mark(0, Gtk.PositionType.BOTTOM, "Silence" if labeled else None)
        scale.add_mark(100, Gtk.PositionType.BOTTOM, "100% (0 dB)" if labeled else None)
        if 0 < self._base < 1:
            scale.add_mark(self._base * 100, Gtk.PositionType.BOTTOM, "Base" if labeled else None)

    def _make_scale(self, callback, *args, labeled=False):
        adj = Gtk.Adjustment(lower=0, upper=VOLUME_UI_MAX, step_increment=1, page_increment=SCROLL_STEP)
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_round_digits(0)
        if labeled:
            scale.add_css_class("au-labeled")
        self._add_marks(scale, labeled)
        handler = scale.connect("value-changed", callback, *args)

        press = Gtk.EventControllerLegacy()
        press.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        press.connect("event", self._on_scale_event)
        scale.add_controller(press)

        scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.DISCRETE)
        scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        scroll.connect("scroll", self._on_scale_scroll, scale)
        scale.add_controller(scroll)
        return scale, handler

    def _rebuild_channels(self, names):
        """Channel map changed (rare): recreate only this control's channel sliders."""
        while child := self._chan_grid.get_first_child():
            self._chan_grid.remove(child)
        self._chan_scales = []
        for i, name in enumerate(names):
            label = Gtk.Label(label=channel_label(name), xalign=0)
            label.set_width_chars(12)
            label.add_css_class("au-channel-name")
            scale, handler = self._make_scale(self._on_channel_changed, i)
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

    def set_base(self, base):
        """Hardware base volume of a device (1.0 = none); marked on every slider."""
        if base == self._base:
            return
        self._base = base
        self._add_marks(self._scale, labeled=True)
        for scale, *_ in self._chan_scales:
            self._add_marks(scale, labeled=False)

    def update(self, values, channels, mute):
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

    def _show(self, values, source=None):
        """Set sliders and labels. `source` (the slider being moved) is left alone:
        setting a scale from inside its own value-changed makes GTK re-emit."""
        peak = max(values, default=0)
        if source is not self._scale:
            with self._scale.handler_block(self._scale_handler):
                self._scale.set_value(peak * 100)
        self._pct.set_text(f"{round(peak * 100)}%")
        self._db.set_text(volume_db(peak))
        for (scale, handler, pct, db), v in zip(self._chan_scales, values):
            if scale is not source:
                with scale.handler_block(handler):
                    scale.set_value(v * 100)
            pct.set_text(f"{round(v * 100)}%")
            db.set_text(volume_db(v))

    # --- peak meter ---

    def show_meter(self, visible):
        if self._meter is not None:
            self._meter.set_visible(visible)
            self.meter_step(0.0, None)

    def meter_step(self, peak, dt):
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

    def _busy(self):
        return self._pressed or time.monotonic() < self._busy_until

    def _touch(self):
        """Extend the grace window and schedule a one-shot resync at its end."""
        self._busy_until = time.monotonic() + DRAG_GRACE
        if self._resync_id:
            GLib.source_remove(self._resync_id)
        self._resync_id = GLib.timeout_add(int(DRAG_GRACE * 1000) + 10, self._resync)

    def _resync(self):
        self._resync_id = 0
        if self._busy():
            self._resync_id = GLib.timeout_add(int(DRAG_GRACE * 1000), self._resync)
            return GLib.SOURCE_REMOVE
        if self._pending is not None:
            self._values, self._pending = self._pending, None
            self._show(self._values)
        return GLib.SOURCE_REMOVE

    def _on_scale_event(self, ctrl, _event):
        # PyGObject passes None for the GdkEvent argument; ask the controller.
        event = ctrl.get_current_event()
        if event is None:
            return False
        kind = event.get_event_type()
        if kind in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.TOUCH_BEGIN):
            self._pressed = True
        elif kind in (Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.TOUCH_END,
                      Gdk.EventType.TOUCH_CANCEL):
            self._pressed = False
            self._touch()
        return False

    def _on_scale_scroll(self, _ctrl, _dx, dy, scale):
        if dy:
            self._touch()
            scale.set_value(round(scale.get_value()) - dy * SCROLL_STEP)
        return True  # stop the list from scrolling while over a slider

    # --- UI -> server ---

    def _commit(self, values, source):
        self._touch()
        self._values = values
        self._show(values, source)
        self._on_volume(values)

    def _on_main_changed(self, scale):
        self._commit(scale_volume(self._values, scale.get_value() / 100), scale)

    def _on_channel_changed(self, scale, index):
        v = scale.get_value() / 100
        if self._lock.get_active():
            self._commit(scale_volume(self._values, v), scale)
        else:
            values = list(self._values)
            values[index] = v
            self._commit(values, scale)

    def _on_mute_toggled(self, btn):
        self._on_mute(btn.get_active())

    def _on_expand_toggled(self, btn):
        self._revealer.set_reveal_child(btn.get_active())
        btn.set_label(ICON["collapse"] if btn.get_active() else ICON["expand"])

    def _on_lock_toggled(self, btn):
        btn.set_label(ICON["lock"] if btn.get_active() else ICON["unlock"])


def title_label(text, css_class="au-row-title"):
    label = Gtk.Label(label=text, xalign=0, hexpand=True)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    label.add_css_class(css_class)
    return label


class DeviceRow(Gtk.Box):
    """Sink or source: volume, set-as-default, port choice, latency offset."""

    def __init__(self, app, kind, index):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self._app, self._kind, self.index = app, kind, index
        self.info = None
        self._card = self._card_port = None

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._title = CopyLabel("au-row-title")
        header.append(self._title)
        if kind == "source":
            self._rec_time = Gtk.Label()
            self._rec_time.add_css_class("au-rec-time")
            self._rec_time.set_visible(False)
            header.append(self._rec_time)
            self._record = glyph_button("au-record-btn", "Record")
            self._record.set_label(ICON["record"])
            self._record.connect("clicked", lambda _: app.toggle_record(self))
            header.append(self._record)
        self._default = glyph_button("au-default-btn")
        self._default.connect("clicked", lambda _: app.set_default(kind, self.info.name))
        header.append(self._default)
        self.append(header)

        self.volume = VolumeControl(
            lambda values: app.set_volume(kind, index, values),
            lambda mute: app.set_mute(kind, index, mute),
            mic=(kind == "source"), meter=app.show_meters)
        self.append(self.volume)

        self._port_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label="Port", xalign=0, hexpand=True)
        label.add_css_class("au-field-label")
        self._port_row.append(label)
        self._ports = Choice(lambda port: app.set_port(kind, index, port, self._ports), 30)
        self._port_row.append(self._ports)
        self.append(self._port_row)

        self._latency_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        label = Gtk.Label(label="Latency offset", xalign=0, hexpand=True)
        label.add_css_class("au-field-label")
        self._latency_row.append(label)
        adj = Gtk.Adjustment(lower=-LATENCY_RANGE_MS, upper=LATENCY_RANGE_MS,
                             step_increment=1, page_increment=10)
        self._latency = Gtk.SpinButton(adjustment=adj, numeric=True)
        self._latency.set_width_chars(5)
        self._latency.add_css_class("au-spin")
        self._latency_handler = self._latency.connect("value-changed", self._on_latency)
        self._latency_row.append(self._latency)
        unit = Gtk.Label(label="ms")
        unit.add_css_class("au-field-label")
        self._latency_row.append(unit)
        self.append(self._latency_row)

    def update(self, info, is_default, card):
        self.info = info
        self._title.set_content(info.description, f"{info.description} ({info.name})",
                                f"{info.description}\n{info.name}")
        self.volume.set_base(info.base_volume)
        self.volume.update(info.volume.values, info.channel_list, bool(info.mute))

        items = [(p.name, p.description + (" (unplugged)" if p.available == "no" else ""),
                  p.available != "no") for p in info.port_list]
        show_ports = len(items) >= 2
        self._port_row.set_visible(show_ports)
        if show_ports:
            self._ports.set_items(items, info.port_active.name if info.port_active else None)
        self.update_context(is_default, card)

    def update_context(self, is_default, card):
        """Parts owned by other objects: the server default and the card's port latency."""
        self._default.set_label(ICON["default" if is_default else "not_default"])
        self._default.set_tooltip_text("Default device" if is_default else "Set as default")
        if is_default:
            self._default.add_css_class("au-default-on")
        else:
            self._default.remove_css_class("au-default-on")

        active = self.info.port_active.name if self.info.port_active else None
        card_port = None
        if card is not None and active:
            card_port = next((p for p in card.port_list if p.name == active), None)
        self._card, self._card_port = card, card_port
        self._latency_row.set_visible(card_port is not None)
        # don't overwrite a value the user is typing
        if card_port is not None and self._latency.get_focus_child() is None:
            with self._latency.handler_block(self._latency_handler):
                self._latency.set_value(card_port.latency_offset / 1000)

    def show_record(self, state, seconds, enabled):
        """Test recording controls (sources only): state idle | recording | playing."""
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

    def _on_latency(self, spin):
        if self._card_port is not None:
            self._app.set_latency(self._card.name, self._card_port.name,
                                  int(spin.get_value()) * 1000)

    def matches(self, flt):
        monitor = self._kind == "source" and self.info.monitor_of_sink != PA_INVALID
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

    def __init__(self, app, kind, index):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self._kind, self.index = kind, index
        self.info = None

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
        self._device = Choice(lambda dev: app.move_stream(kind, index, dev, self._device), 18)
        self._device.set_valign(Gtk.Align.CENTER)
        header.append(self._device)
        kill = glyph_button("au-kill-btn", "Terminate playback" if kind == "sink_input"
                            else "Terminate recording")
        kill.set_label(ICON["kill"])
        kill.connect("clicked", lambda _: app.kill_stream(kind, index))
        header.append(kill)
        self.append(header)

        self.volume = VolumeControl(
            lambda values: app.set_volume(kind, index, values),
            lambda mute: app.set_mute(kind, index, mute),
            mic=(kind == "source_output"), meter=app.show_meters)
        self.append(self.volume)

    def update(self, info, devices):
        self.info = info
        props = info.proplist
        self._icon.set_from_icon_name(props.get("application.icon_name") or "audio-card")
        self._app_name.set_text(props.get("application.name") or info.name or "Unknown")
        media = props.get("media.name") or info.name or ""
        self._media.set_text(media)
        self._media.set_tooltip_text(media)
        self.volume.update(info.volume.values, info.channel_list, bool(info.mute))
        self.update_devices(devices)

    def update_devices(self, devices):
        """devices: [(index, description)] of sinks (playback) or sources (recording)."""
        if self.info is None:
            return
        current = self.info.sink if self._kind == "sink_input" else self.info.source
        self._device.set_items([(i, d, True) for i, d in devices], current)

    def matches(self, flt):
        virtual = self.info.client == PA_INVALID
        return {"all": True, "apps": not virtual, "virtual": virtual}[flt]


class EventSoundsRow(Gtk.Box):
    """stream-restore entry for event sounds (system sounds volume and mute)."""

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self.info = None
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label=ICON["bell"])
        icon.add_css_class("au-glyph-icon")
        header.append(icon)
        header.append(title_label("System Sounds"))
        self.append(header)
        self.volume = VolumeControl(app.set_event_volume, app.set_event_mute)
        self.append(self.volume)

    def update(self, info):
        self.info = info
        self.volume.update(info.volume.values, info.channel_list, bool(info.mute))

    def matches(self, flt):
        return flt in ("all", "apps")


class CardRow(Gtk.Box):
    """Card description and profile choice."""

    def __init__(self, app, index):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("au-row")
        self.index, self.info = index, None
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
        self._profiles = Choice(lambda p: app.set_profile(index, p, self._profiles), 40)
        self._profiles.set_hexpand(True)
        profile_row.append(self._profiles)
        self.append(profile_row)

    def update(self, info):
        self.info = info
        desc = info.proplist.get("device.description") or info.name
        self._title.set_content(desc, f"{desc} ({info.name})", f"{desc}\n{info.name}")
        profiles = sorted(info.profile_list, key=lambda p: -p.priority)
        items = [(p.name, p.description + ("" if p.available else " (unavailable)"),
                  bool(p.available)) for p in profiles]
        self._profiles.set_items(items, info.profile_active.name)

    def matches(self, _flt):
        return True


class Tab:
    """One stack page: scrolling row list, empty message and optional filter."""

    def __init__(self, empty_text, filters, default_filter, on_filter):
        self.rows = {}
        self.extra_rows = []  # rows not keyed by pulse index (event sounds)
        self.filter = default_filter
        self.page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.empty = Gtk.Label(label=empty_text)
        self.empty.add_css_class("au-empty")
        self.list.append(self.empty)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(460)
        scroll.set_child(self.list)
        scroll.set_vexpand(True)
        self.page.append(scroll)

        if filters:
            bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            bar.add_css_class("au-filter-bar")
            label = Gtk.Label(label="Show", xalign=0)
            label.add_css_class("au-field-label")
            bar.append(label)
            choice = Choice(lambda f: on_filter(self, f))
            choice.set_items([(k, l, True) for k, l in filters], default_filter)
            bar.append(choice)
            self.page.append(bar)

    def add(self, index, row):
        self.rows[index] = row
        self.list.append(row)

    def remove(self, index):
        row = self.rows.pop(index, None)
        if row is not None:
            self.list.remove(row)

    def refilter(self):
        shown = False
        for row in list(self.rows.values()) + self.extra_rows:
            visible = row.info is not None and row.matches(self.filter)
            row.set_visible(visible)
            shown = shown or visible
        self.empty.set_visible(not shown)


class EventThread(threading.Thread):
    """Runs the event connection's blocking listen loop; forwards events only."""

    def __init__(self, pulse, on_event, on_disconnect):
        super().__init__(daemon=True)
        self._pulse, self._on_event, self._on_disconnect = pulse, on_event, on_disconnect
        self._stopping = self._closed = False
        self._lock = threading.Lock()

    def run(self):
        # Never call pulsectl from the callback: just hand the event to GTK.
        self._pulse.event_callback_set(lambda ev: GLib.idle_add(
            self._on_event, ev.facility._value, ev.t._value, ev.index))
        try:
            while not self._stopping:
                self._pulse.event_listen()
        except Exception:
            pass
        finally:
            with self._lock:
                self._closed = True
                self._pulse.close()
            if not self._stopping:
                GLib.idle_add(self._on_disconnect)

    def stop(self):
        """Thread-safe: wakes the listen loop unless the thread already closed it."""
        with self._lock:
            self._stopping = True
            if not self._closed:
                self._pulse.event_listen_stop()


class AudioPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.audio")
        self._cmd = None
        self._events = None
        self._connected = False
        self._backoff = 0
        self._reconnect_id = 0
        self._pending = {}
        self._flush_id = 0
        self._defaults = {"sink": None, "source": None}
        self._infos = {"sink": {}, "source": {}, "card": {}}
        self._state = load_state()
        self.show_meters = self._state.get("meters", True)
        self._meters = None
        self._meter_targets = {}   # (facility, index) -> stream spec sent to the thread
        self._meter_sync_id = self._tick_id = 0
        self._frame_time = 0.0
        self._recorder = Recorder(self._on_record_change) if pulsectl else None
        self._record_tick_id = 0

    # --- UI ---

    def build_ui(self):
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._container.add_css_class("au-container")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label="Audio", xalign=0, hexpand=True)
        title.add_css_class("au-title")
        header.append(title)
        self._container.append(header)

        if pulsectl is None:
            self._container.append(self._error_box(
                "libpulse not found", "Install libpulse (pulled in by pipewire-pulse)"))
            return self._container

        meters = glyph_button("au-meters-btn", "Show volume meters", toggle=True)
        meters.set_label(ICON["meters"])
        meters.set_active(self.show_meters)
        meters.connect("toggled", self._on_meters_toggled)
        header.append(meters)

        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tab_bar.add_css_class("au-tab-bar")
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self._stack.set_vhomogeneous(False)
        self._stack.set_hhomogeneous(True)
        self._tabs, self._tab_buttons = {}, {}
        for n, (key, label, _fac, empty, filters, default) in enumerate(TABS, 1):
            btn = Gtk.Button(label=label)
            btn.add_css_class("au-tab-btn")
            btn.set_tooltip_text(f"{label} ({n})")
            btn.connect("clicked", lambda _, k=key: self._switch_tab(k))
            tab_bar.append(btn)
            self._tab_buttons[key] = btn
            tab = Tab(empty, filters, default, self._on_filter)
            self._tabs[key] = tab
            self._stack.add_named(tab.page, key)
        self._container.append(tab_bar)

        self._offline = self._error_box("Not connected", "Waiting for the sound server…")
        self._offline.set_visible(False)
        self._container.append(self._offline)
        self._container.append(self._stack)

        self._event_row = EventSoundsRow(self)
        self._event_row.set_visible(False)
        playback = self._tabs["playback"]
        playback.extra_rows.append(self._event_row)
        playback.list.insert_child_after(self._event_row, playback.empty)

        tab = self._state.get("tab")
        self._switch_tab(tab if tab in self._tabs else "playback", save=False)
        # widget-toggle closes the popup with SIGTERM: quit cleanly so do_shutdown
        # stops a test recording's parec/pacat
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        self._connect()
        return self._container

    def _error_box(self, message, hint):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)
        icon = Gtk.Label(label=ICON["offline"])
        icon.add_css_class("au-error-icon")
        box.append(icon)
        msg = Gtk.Label(label=message)
        msg.add_css_class("au-error-msg")
        box.append(msg)
        hint_label = Gtk.Label(label=hint)
        hint_label.add_css_class("au-error-hint")
        box.append(hint_label)
        return box

    def _switch_tab(self, key, save=True):
        if key != self._stack.get_visible_child_name():
            self._recorder.cancel()
        self._stack.set_visible_child_name(key)
        self._queue_meters()
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.add_css_class("au-tab-active")
            else:
                btn.remove_css_class("au-tab-active")
        if save and self._state.get("tab") != key:
            self._state["tab"] = key
            save_state(self._state)

    def _on_filter(self, tab, flt):
        tab.filter = flt
        self._recorder.cancel()
        tab.refilter()
        self._queue_meters()

    def _on_meters_toggled(self, btn):
        self.show_meters = btn.get_active()
        for tab in self._tabs.values():
            for row in tab.rows.values():
                if isinstance(row, (DeviceRow, StreamRow)):
                    row.volume.show_meter(self.show_meters)
        self._state["meters"] = self.show_meters
        save_state(self._state)
        self._queue_meters()

    def _on_key(self, controller, keyval, keycode, state):
        win = self.get_active_window()
        focus = win.get_focus() if win else None
        editing = isinstance(focus, Gtk.Text)
        if keyval == Gdk.KEY_q and editing:
            return False
        if not editing and Gdk.KEY_1 <= keyval <= Gdk.KEY_5 and pulsectl is not None:
            self._switch_tab(TAB_KEYS[keyval - Gdk.KEY_1])
            return True
        return super()._on_key(controller, keyval, keycode, state)

    # --- connection lifecycle ---

    def _connect(self):
        """Open both connections, start the event thread, sync every list."""
        cmd = events = None
        try:
            # No connect(timeout=...): pulsectl then always waits the full timeout.
            # A missing server fails immediately anyway.
            cmd = pulsectl.Pulse("gtk-widgets-audio")
            events = pulsectl.Pulse("gtk-widgets-audio-events")
            events.event_mask_set("all")
        except Exception:
            for p in (cmd, events):
                if p is not None:
                    p.close()
            self._set_online(False)
            self._schedule_reconnect()
            return
        self._cmd = cmd
        self._events = EventThread(events, self._apply_event, self._on_disconnected)
        self._events.start()
        # connects on its own thread; picks up the targets _sync_all() queues
        self._meters = MeterThread(self._on_peaks)
        self._meters.start()
        self._connected, self._backoff = True, 0
        self._set_online(True)
        self._sync_all()

    def _schedule_reconnect(self):
        delay = min(BACKOFF_START * 2 ** self._backoff, BACKOFF_MAX)
        self._backoff += 1
        self._reconnect_id = GLib.timeout_add(int(delay * 1000), self._reconnect)

    def _reconnect(self):
        self._reconnect_id = 0
        self._connect()
        return GLib.SOURCE_REMOVE

    def _on_disconnected(self):
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
        self._set_online(False)
        self._schedule_reconnect()
        return GLib.SOURCE_REMOVE

    def _set_online(self, online):
        self._offline.set_visible(not online)
        self._stack.set_visible(online)

    def _call(self, fn, *args, **kwargs):
        """Run a command-connection call; None on failure (disconnect handled)."""
        if not self._connected:
            return None
        try:
            return fn(*args, **kwargs)
        except pulsectl.PulseError:
            if not self._cmd.connected:
                self._on_disconnected()
            return None

    # --- sync ---

    def _sync_all(self):
        """Full read after (re)connect; rows are diffed by index, not rebuilt."""
        c = self._cmd
        server = self._call(c.server_info)
        lists = {fac: self._call(getattr(c, f"{fac}_list"))
                 for fac in ("card", "sink", "source", "sink_input", "source_output")}
        if server is None or any(v is None for v in lists.values()):
            return
        self._defaults = {"sink": server.default_sink_name, "source": server.default_source_name}
        for fac in ("card", "sink", "source", "sink_input", "source_output"):
            seen = set()
            for info in lists[fac]:
                seen.add(info.index)
                self._upsert(fac, info)
            for index in list(self._rows(fac)):
                if index not in seen:
                    self._remove(fac, index)
        self._sync_event_sounds()
        self._refresh_after("sink")
        self._refresh_after("source")
        for tab in self._tabs.values():
            tab.refilter()
        self._queue_meters()

    def _sync_event_sounds(self):
        entries = self._call(self._cmd.stream_restore_list) or []
        entry = next((e for e in entries if e.name == EVENT_ROLE), None)
        if entry is not None:
            self._event_row.update(entry)
        self._event_row.info = entry
        self._tabs["playback"].refilter()

    def _apply_event(self, facility, kind, index):
        """Main-thread side of the event thread. Coalesces bursts per object."""
        if not self._connected:
            return GLib.SOURCE_REMOVE
        if facility == "server":
            self._pending[("server", 0)] = kind
        elif facility in ("sink", "source", "sink_input", "source_output", "card"):
            self._pending[(facility, index)] = kind  # last event wins; a fetch re-reads
        else:
            return GLib.SOURCE_REMOVE
        if not self._flush_id:
            self._flush_id = GLib.idle_add(self._flush)
        return GLib.SOURCE_REMOVE

    def _flush(self):
        self._flush_id = 0
        pending, self._pending = self._pending, {}
        touched = set()
        for (facility, index), kind in pending.items():
            if not self._connected:
                break
            if facility == "server":
                server = self._call(self._cmd.server_info)
                if server is not None:
                    self._defaults = {"sink": server.default_sink_name,
                                      "source": server.default_source_name}
                    touched.update(("sink", "source"))
                continue
            touched.add(facility)
            if kind == "remove":
                self._remove(facility, index)
                continue
            info = self._fetch(facility, index)
            if info is None:
                if self._connected:
                    self._remove(facility, index)
            else:
                self._upsert(facility, info)
        for facility in touched:
            self._refresh_after(facility)
        self._queue_meters()
        return GLib.SOURCE_REMOVE

    def _fetch(self, facility, index):
        getter = getattr(self._cmd, f"{facility}_info")
        try:
            return getter(index)
        except pulsectl.PulseIndexError:
            return None
        except pulsectl.PulseError:
            if not self._cmd.connected:
                self._on_disconnected()
            return None

    # --- rows ---

    def _tab_for(self, facility):
        return self._tabs[next(t[0] for t in TABS if t[2] == facility)]

    def _rows(self, facility):
        return self._tab_for(facility).rows

    def _devices(self, facility):
        return [(i, info.description) for i, info in sorted(self._infos[facility].items())]

    def _upsert(self, facility, info):
        app_id = info.proplist.get("application.id")
        if facility == "source_output" and app_id in MIXER_APP_IDS:
            return  # a meter stream (ours or another mixer's) or our test recording
        if facility == "sink_input" and app_id == APP_ID:
            return  # our test recording's playback
        tab = self._tab_for(facility)
        row = tab.rows.get(info.index)
        if facility in ("sink", "source", "card"):
            self._infos[facility][info.index] = info
        if row is None:
            row = {
                "sink": lambda: DeviceRow(self, "sink", info.index),
                "source": lambda: DeviceRow(self, "source", info.index),
                "sink_input": lambda: StreamRow(self, "sink_input", info.index),
                "source_output": lambda: StreamRow(self, "source_output", info.index),
                "card": lambda: CardRow(self, info.index),
            }[facility]()
            tab.add(info.index, row)
        if facility in ("sink", "source"):
            card = self._infos["card"].get(info.card)
            row.update(info, info.name == self._defaults[facility], card)
            if facility == "source" and self._recorder.state != "idle":
                self._show_record()  # a new row is disabled while a recording runs
        elif facility == "sink_input":
            if info.proplist.get("module-stream-restore.id") == EVENT_ROLE:
                row.info = None  # shown by the System Sounds row instead
            else:
                row.update(info, self._devices("sink"))
        elif facility == "source_output":
            row.update(info, self._devices("source"))
        else:
            row.update(info)

    def _remove(self, facility, index):
        if facility == "source" and index == self._recorder.source:
            self._recorder.cancel()
        if facility in self._infos:
            self._infos[facility].pop(index, None)
        self._tab_for(facility).remove(index)

    def _refresh_after(self, facility):
        """Propagate a change to rows that depend on it, then refilter."""
        if facility in ("sink", "source"):
            self._refresh_device_context(facility)
            streams = "sink_input" if facility == "sink" else "source_output"
            devices = self._devices(facility)
            for row in self._rows(streams).values():
                row.update_devices(devices)
            self._tab_for(streams).refilter()
        elif facility == "card":
            # latency offsets live on card ports
            self._refresh_device_context("sink")
            self._refresh_device_context("source")
        self._tab_for(facility).refilter()

    def _refresh_device_context(self, facility):
        default = self._defaults[facility]
        for row in self._rows(facility).values():
            if row.info is not None:
                row.update_context(row.info.name == default,
                                   self._infos["card"].get(row.info.card))

    # --- peak meters ---

    def _queue_meters(self):
        """Resync meter streams once the current burst of changes is applied."""
        if not self._meter_sync_id:
            self._meter_sync_id = GLib.idle_add(self._sync_meters)

    def _wanted_meters(self):
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
        facility = next(t[2] for t in TABS if t[0] == key)
        targets = {}
        for index, row in self._tabs[key].rows.items():
            info = row.info
            if info is None or not row.get_visible():
                continue
            if facility == "sink":
                device, source, stream = info, info.monitor_source, None
            elif facility == "source":
                device, source, stream = info, info.index, None
            elif facility == "sink_input":
                device = self._infos["sink"].get(info.sink)
                source, stream = (device.monitor_source if device else PA_INVALID), info.index
            elif facility == "source_output":
                device, source, stream = self._infos["source"].get(info.source), info.source, None
            else:
                continue  # cards have no volume
            if device is None or source == PA_INVALID:
                continue
            # the source of a sink's meter is its monitor; a source's is itself
            passive = facility in ("sink", "sink_input") or device.monitor_of_sink != PA_INVALID
            if passive and device.state == "suspended":
                continue
            targets[(facility, index)] = (source, stream, passive)
        return targets

    def _sync_meters(self):
        self._meter_sync_id = 0
        targets = self._wanted_meters()
        if targets != self._meter_targets:
            self._reset_meters(self._meter_targets.keys() - targets.keys())
            self._meter_targets = targets
            if self._meters is not None:
                self._meters.set_targets(targets)
        return GLib.SOURCE_REMOVE

    def _reset_meters(self, keys):
        for facility, index in keys:
            row = self._rows(facility).get(index)
            if row is not None:
                row.volume.meter_step(0.0, None)

    def _stop_meters(self):
        if self._meters is not None:
            self._meters.stop()
            self._meters = None
        self._reset_meters(self._meter_targets)
        self._meter_targets = {}

    def _on_peaks(self):
        """Meter thread has new peaks: apply them on the next frame."""
        if not self._tick_id and self._meters is not None:
            self._tick_id = self._container.add_tick_callback(self._meter_tick)
        return GLib.SOURCE_REMOVE

    def _meter_tick(self, _widget, clock):
        """Meter updates at METER_RATE on frame boundaries, until every meter is at zero."""
        now = clock.get_frame_time() / 1e6
        if self._frame_time and now - self._frame_time < 0.9 / METER_RATE:
            return GLib.SOURCE_CONTINUE  # between updates: nothing changes, nothing redraws
        dt = now - self._frame_time if self._frame_time else 0.0
        self._frame_time = now
        peaks = self._meters.take_peaks() if self._meters is not None else {}
        active = False
        for key in self._meter_targets:
            row = self._rows(key[0]).get(key[1])
            if row is not None and row.volume.meter_step(peaks.get(key, 0.0), dt) > 0:
                active = True
        if active:
            return GLib.SOURCE_CONTINUE
        self._tick_id, self._frame_time = 0, 0.0
        return GLib.SOURCE_REMOVE

    # --- test recording ---

    def toggle_record(self, row):
        if self._recorder.state == "idle":
            self._recorder.record(row.info.name, row.index)
        else:
            self._recorder.stop()

    def _on_record_change(self):
        busy = self._recorder.state != "idle"
        if busy and not self._record_tick_id:
            self._record_tick_id = GLib.timeout_add(250, self._record_tick)
        self._show_record()

    def _show_record(self):
        rec = self._recorder
        for index, row in self._rows("source").items():
            mine = index == rec.source
            row.show_record(rec.state if mine else "idle", rec.seconds(),
                            rec.state == "idle" or mine)

    def _record_tick(self):
        if self._recorder.state == "idle":
            self._record_tick_id = 0
            return GLib.SOURCE_REMOVE
        row = self._rows("source").get(self._recorder.source)
        if row is not None:
            row.show_record(self._recorder.state, self._recorder.seconds(), True)
        return GLib.SOURCE_CONTINUE

    # --- writes (command connection, main thread) ---

    def _act(self, method, *args, choice=None, **kwargs):
        """Run a command-connection write; a failed dropdown pick is reverted."""
        if self._connected:
            try:
                getattr(self._cmd, method)(*args, **kwargs)
                return
            except pulsectl.PulseError:
                if not self._cmd.connected:
                    self._on_disconnected()
        if choice is not None:
            choice.revert()

    def set_volume(self, facility, index, values):
        self._act(f"{facility}_volume_set", index, pulsectl.PulseVolumeInfo(list(values)))

    def set_mute(self, facility, index, mute):
        self._act(f"{facility}_mute", index, mute)

    def set_default(self, facility, name):
        self._act(f"{facility}_default_set", name)

    def set_port(self, facility, index, port, choice):
        self._act(f"{facility}_port_set", index, port, choice=choice)

    def move_stream(self, facility, index, device, choice):
        self._act(f"{facility}_move", index, device, choice=choice)

    def kill_stream(self, facility, index):
        self._act(f"{facility}_kill", index)

    def set_profile(self, index, profile, choice):
        self._act("card_profile_set_by_index", index, profile, choice=choice)

    def set_latency(self, card_name, port_name, offset_us):
        # pulsectl has no call for this; pactl is the documented fallback.
        subprocess.Popen(["pactl", "set-port-latency-offset", card_name, port_name,
                          str(offset_us)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _write_event_sounds(self, volume=None, mute=None):
        entry = self._event_row.info
        if entry is None:
            return
        if volume is not None:
            entry.volume = pulsectl.PulseVolumeInfo(list(volume))
        if mute is not None:
            entry.mute = int(mute)
        self._act("stream_restore_write",
                  pulsectl.PulseExtStreamRestoreInfo(
                      entry.name, entry.volume, entry.channel_list,
                      bool(entry.mute), entry.device or None),
                  mode="replace", apply_immediately=True)
        # stream-restore writes emit no subscription events; show the new state now
        self._event_row.volume.update(entry.volume.values, entry.channel_list, bool(entry.mute))

    def set_event_volume(self, values):
        self._write_event_sounds(volume=values)

    def set_event_mute(self, mute):
        self._write_event_sounds(mute=mute)

    def do_shutdown(self):
        if self._reconnect_id:
            GLib.source_remove(self._reconnect_id)
        if self._events:
            self._events.stop()
        if self._meters:
            self._meters.stop()
        if self._recorder:
            self._recorder.cancel()
        if self._cmd:
            self._cmd.close()
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    AudioPopup().run()
