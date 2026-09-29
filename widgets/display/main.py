#!/usr/bin/env python3
"""Display settings popup — scale, brightness, night light temperature."""

import json, os, signal, subprocess, sys, threading
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from lib.widget_base import Gtk, WidgetPopup

from gi.repository import GLib

import brightness  # noqa: E402

TEMP_FILE = os.path.expanduser("~/.config/wlsunset/temperature")
FLUSH_S = 5  # longest wait on close for the last brightness write (a rescan is ~3 s)


def get_current_scale():
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs"], capture_output=True, text=True
        )
        outputs = json.loads(result.stdout)
        for output in outputs:
            if output.get("active"):
                # sway stores scale as a float32: 1.3 reads back 1.2999999523,
                # which the label truncates to 129%
                return round(output.get("scale", 1.0), 1)
    except Exception:
        pass
    return 1.0


def apply_scale(scale):
    subprocess.run(
        ["swaymsg", "output", "*", "scale", f"{scale:.1f}"],
        capture_output=True,
    )
    conf = os.path.expanduser("~/.config/sway/scale.conf")
    with open(conf, "w") as f:
        f.write(f"output * scale {scale:.1f}\n")
    subprocess.Popen(["pkill", "-RTMIN+11", "waybar"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_temperature():
    try:
        with open(TEMP_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return 4500


def apply_temperature(temp):
    temp = int(temp)
    os.makedirs(os.path.dirname(TEMP_FILE), exist_ok=True)
    with open(TEMP_FILE, "w") as f:
        f.write(f"{temp}\n")
    subprocess.run(["pkill", "wlsunset"], capture_output=True)
    subprocess.Popen(
        ["wlsunset", "-T", str(temp + 1), "-t", str(temp)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


class LatestWriter:
    """Runs fn(value) on one worker thread, newest value wins.

    set() returns at once; a value set while a write runs replaces any not yet
    written, so a drag becomes a few writes and the popup never waits on them.
    """

    def __init__(self, fn):
        self._fn = fn
        self._cond = threading.Condition()
        self._want = None
        self._busy = False
        threading.Thread(target=self._loop, daemon=True).start()

    def set(self, value):
        with self._cond:
            self._want = value
            self._cond.notify_all()

    def flush(self, timeout):
        """Wait (at most timeout s) until the newest value is written."""
        with self._cond:
            self._cond.wait_for(
                lambda: self._want is None and not self._busy, timeout)

    def _loop(self):
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._want is not None)
                value, self._want = self._want, None
                self._busy = True
            try:
                self._fn(value)
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()


class DisplayPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.display")
        self._timeouts = {"scale": 0, "brightness": 0, "temperature": 0}
        self._pending = {}  # key -> (apply_fn, value) while its debounce runs
        self._brightness_writer = None

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        container.add_css_class("display-container")

        title = Gtk.Label(label="Display")
        title.add_css_class("display-title")
        container.append(title)

        # --- Scale (swaymsg is fast, keep sync) ---
        self._build_slider(
            container, "SCALE", get_current_scale(), lambda v: f"{int(v * 100)}%",
            1.0, 2.0, 0.1,
            marks=[(1.0, "100%"), (1.5, "150%"), (2.0, "200%")],
            ticks=[1.0 + i * 0.1 for i in range(11)],
            snap=lambda v: round(v * 10) / 10,
            key="scale", delay=500, apply_fn=apply_scale,
        )

        # --- Brightness (probed on a worker thread — DDC is slow) ---
        self._brightness_sep = Gtk.Separator()
        self._brightness_sep.set_visible(False)
        container.append(self._brightness_sep)

        self._brightness_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._brightness_box.set_visible(False)
        container.append(self._brightness_box)

        self._load_brightness_async()
        # widget-toggle closes the popup with SIGTERM: quit cleanly so do_shutdown
        # writes a brightness value still on its way
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)

        # --- Night Light (file read is fast, keep sync) ---
        container.append(Gtk.Separator())
        self._build_slider(
            container, "NIGHT LIGHT", get_temperature() / 1000,
            lambda v: f"{int(v * 1000)}K",
            2.5, 6.5, 0.1,
            marks=[(2.5, "2500K"), (4.5, "4500K"), (6.5, "6500K")],
            ticks=[2.5 + i * 0.5 for i in range(9)],
            snap=lambda v: round(v * 10) / 10,
            key="temperature", delay=500,
            apply_fn=lambda v: apply_temperature(v * 1000),
        )

        return container

    def _load_brightness_async(self):
        """Probe the backend off the main thread, then build the slider on it."""
        def worker():
            backend, pct = brightness.probe()
            if backend:
                GLib.idle_add(self._build_brightness, backend, pct)
        threading.Thread(target=worker, daemon=True).start()

    def _build_brightness(self, backend, pct):
        # DDC writes take 0.1-3 s: they run on a worker, never on the main thread
        self._brightness_writer = LatestWriter(
            lambda v: brightness.set_pct(backend, v * 100))
        self._build_slider(
            self._brightness_box, "BRIGHTNESS",
            pct / 100,
            lambda v: f"{int(v * 100)}%",
            0.0, 1.0, 0.05,
            marks=[(0.0, "0%"), (0.5, "50%"), (1.0, "100%")],
            ticks=[i * 0.1 for i in range(11)],
            snap=lambda v: round(v * 20) / 20,
            key="brightness", delay=100,
            apply_fn=self._brightness_writer.set,
        )
        self._brightness_sep.set_visible(True)
        self._brightness_box.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _build_slider(self, container, label_text, current, fmt_fn,
                      lower, upper, step, marks, ticks, snap,
                      key, delay, apply_fn):
        label = Gtk.Label(label=label_text)
        label.add_css_class("section-label")
        label.set_halign(Gtk.Align.START)
        container.append(label)

        value_label = Gtk.Label(label=fmt_fn(current))
        value_label.add_css_class("section-value")
        container.append(value_label)

        adj = Gtk.Adjustment(
            value=current, lower=lower, upper=upper,
            step_increment=step, page_increment=step,
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_digits(2)
        for t in ticks:
            scale.add_mark(t, Gtk.PositionType.BOTTOM, None)
        for val, text in marks:
            scale.add_mark(val, Gtk.PositionType.TOP, text)
        adj.connect("value-changed", self._on_slider_changed,
                    value_label, fmt_fn, snap, key, delay, apply_fn)
        container.append(scale)

    def _on_slider_changed(self, adj, value_label, fmt_fn, snap,
                           key, delay, apply_fn):
        snapped = snap(adj.get_value())
        value_label.set_text(fmt_fn(snapped))
        if self._timeouts[key]:
            GLib.source_remove(self._timeouts[key])
        self._pending[key] = (apply_fn, snapped)
        self._timeouts[key] = GLib.timeout_add(delay, self._apply, key)

    def _apply(self, key):
        self._timeouts[key] = 0
        apply_fn, value = self._pending.pop(key)
        apply_fn(value)
        return GLib.SOURCE_REMOVE

    def do_shutdown(self):
        # A change still in its debounce is applied, not dropped, on close
        for key, source in self._timeouts.items():
            if source:
                GLib.source_remove(source)
                self._apply(key)
        if self._brightness_writer:
            for win in self.get_windows():
                win.set_visible(False)
            self._brightness_writer.flush(FLUSH_S)
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    DisplayPopup().run()
