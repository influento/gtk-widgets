#!/usr/bin/env python3
"""Timer widget — timer + stopwatch with session-scoped state."""

import os, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from gi.repository import GLib  # noqa: E402

from lib.widget_base import Gtk, WidgetPopup, load_css  # noqa: E402
import state as ts  # noqa: E402

CSS = load_css(os.path.join(_DIR, "style.css"))

PRESETS = [
    ("1m", 60),
    ("5m", 5 * 60),
    ("10m", 10 * 60),
    ("25m", 25 * 60),
    ("1h", 60 * 60),
]


class TimerPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.timer")
        self.state = ts.load()
        self._tick_id = None

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        container.add_css_class("timer-container")

        # Mode switcher
        mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0,
                           homogeneous=True)
        mode_row.add_css_class("mode-switcher")
        self.mode_buttons = {}
        for mode, label in (("timer", "Timer"), ("stopwatch", "Stopwatch")):
            btn = Gtk.Button(label=label)
            btn.add_css_class("mode-button")
            btn.connect("clicked", self._on_mode_clicked, mode)
            self.mode_buttons[mode] = btn
            mode_row.append(btn)
        container.append(mode_row)

        # Display
        self.display = Gtk.Label(label="00:00:00")
        self.display.add_css_class("timer-display")
        container.append(self.display)

        # Timer-only: spinners + presets
        self.config_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        spin_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        spin_row.set_halign(Gtk.Align.CENTER)
        self.spin_h = self._make_spin(0, 23)
        self.spin_m = self._make_spin(0, 59)
        self.spin_s = self._make_spin(0, 59)
        for spin, suffix in ((self.spin_h, "h"), (self.spin_m, "m"), (self.spin_s, "s")):
            cell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            cell.append(spin)
            lbl = Gtk.Label(label=suffix)
            lbl.add_css_class("spin-suffix")
            cell.append(lbl)
            spin_row.append(cell)
        self.config_box.append(spin_row)

        preset_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        preset_row.set_halign(Gtk.Align.CENTER)
        for label, seconds in PRESETS:
            btn = Gtk.Button(label=label)
            btn.add_css_class("preset-button")
            btn.connect("clicked", self._on_preset_clicked, seconds)
            preset_row.append(btn)
        self.config_box.append(preset_row)

        container.append(self.config_box)

        # Action row: start/pause + reset
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                             homogeneous=True)
        self.start_button = Gtk.Button(label="Start")
        self.start_button.add_css_class("action-button")
        self.start_button.add_css_class("primary")
        self.start_button.connect("clicked", self._on_start_pause)
        action_row.append(self.start_button)

        self.reset_button = Gtk.Button(label="Reset")
        self.reset_button.add_css_class("action-button")
        self.reset_button.connect("clicked", self._on_reset)
        action_row.append(self.reset_button)
        container.append(action_row)

        self._refresh_ui()
        self._start_tick()
        return container

    def _make_spin(self, lo, hi):
        adj = Gtk.Adjustment(lower=lo, upper=hi, step_increment=1, page_increment=5)
        spin = Gtk.SpinButton(adjustment=adj, numeric=True)
        spin.set_orientation(Gtk.Orientation.VERTICAL)
        spin.add_css_class("time-spin")
        spin.connect("value-changed", self._on_spinner_changed)
        return spin

    # ----- Event handlers -----

    def _on_mode_clicked(self, _btn, mode):
        ts.set_mode(self.state, mode)
        ts.save(self.state)
        self._refresh_ui()

    def _on_preset_clicked(self, _btn, seconds):
        ts.set_duration(self.state, seconds)
        ts.save(self.state)
        self._sync_spinners_from_state()
        self._refresh_ui()

    def _on_spinner_changed(self, _spin):
        if self._suppress_spin:
            return
        seconds = (int(self.spin_h.get_value()) * 3600
                   + int(self.spin_m.get_value()) * 60
                   + int(self.spin_s.get_value()))
        ts.set_duration(self.state, seconds)
        ts.save(self.state)
        self._refresh_ui()

    def _on_start_pause(self, _btn):
        if self.state["mode"] == "timer" and self.state["duration"] == 0.0:
            return
        if self.state["running"]:
            ts.pause(self.state)
        else:
            if self.state["mode"] == "timer" and ts.remaining(self.state) == 0.0:
                # Restart a finished timer with the same duration
                self.state["accumulated"] = 0.0
                self.state["fired"] = False
            ts.start(self.state)
        ts.save(self.state)
        self._refresh_ui()

    def _on_reset(self, _btn):
        ts.reset(self.state)
        ts.save(self.state)
        self._sync_spinners_from_state()
        self._refresh_ui()

    # ----- UI refresh / ticking -----

    _suppress_spin = False

    def _sync_spinners_from_state(self):
        self._suppress_spin = True
        try:
            total = int(self.state["duration"])
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            self.spin_h.set_value(h)
            self.spin_m.set_value(m)
            self.spin_s.set_value(s)
        finally:
            self._suppress_spin = False

    def _refresh_ui(self):
        # Reload state in case the status script has updated `fired`
        on_disk = ts.load()
        # Preserve mode/running/duration from in-memory (UI is the writer);
        # but pull the `fired` flag in case status script set it.
        self.state["fired"] = on_disk.get("fired", self.state["fired"])

        self.display.set_label(ts.format_hms(ts.display_seconds(self.state)))

        for mode, btn in self.mode_buttons.items():
            if mode == self.state["mode"]:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        is_timer = self.state["mode"] == "timer"
        self.config_box.set_visible(is_timer)
        if is_timer:
            self._sync_spinners_from_state()

        if self.state["running"]:
            self.start_button.set_label("Pause")
        elif is_timer and ts.remaining(self.state) == 0.0 and self.state["duration"] > 0:
            self.start_button.set_label("Restart")
        else:
            self.start_button.set_label("Start" if self.state["accumulated"] == 0
                                        else "Resume")

        # Disable start when timer has no duration set
        self.start_button.set_sensitive(
            not (is_timer and self.state["duration"] == 0.0)
        )

    def _start_tick(self):
        if self._tick_id is None:
            self._tick_id = GLib.timeout_add(250, self._on_tick)

    def _on_tick(self):
        if self.state["running"]:
            self.display.set_label(ts.format_hms(ts.display_seconds(self.state)))
            # Auto-pause timer when it hits zero (popup can do this; status
            # script also handles the case where popup is closed)
            if self.state["mode"] == "timer" and ts.remaining(self.state) == 0.0:
                ts.pause(self.state)
                ts.save(self.state)
                self._refresh_ui()
        return True


if __name__ == "__main__":
    TimerPopup.CSS = CSS
    TimerPopup().run()
