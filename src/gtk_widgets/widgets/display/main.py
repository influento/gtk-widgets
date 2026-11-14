#!/usr/bin/env python3
"""Display settings popup — scale, brightness, night light temperature."""

import contextlib
import json
import os
import signal
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, override

from gi.repository import GLib

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup
from gtk_widgets.widgets.display import brightness
from gtk_widgets.widgets.display.parse import parse_active_scale

# Runtime state, outside any config checkout: sway includes scale.conf and
# dotfiles' wlsunset.sh reads temperature at sway startup
STATE_DIR = Path.home() / ".local/state/dotfiles"
SCALE_FILE = STATE_DIR / "scale.conf"
TEMP_FILE = STATE_DIR / "temperature"
FLUSH_S = 5  # longest wait on close for the last brightness write (a rescan is ~3 s)
DEFAULT_SCALE = 1.0
DEFAULT_TEMPERATURE = 4500

type SliderKey = Literal["scale", "brightness", "temperature"]


def get_current_scale() -> float:
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs"],
            capture_output=True,
            text=True,
            check=False,
        )
        data: object = json.loads(result.stdout)
    except OSError, ValueError:
        return DEFAULT_SCALE
    match parse_active_scale(data):
        case None | ParseError():
            return DEFAULT_SCALE
        case scale:
            # sway stores scale as a float32: 1.3 reads back 1.2999999523,
            # which the label truncates to 129%
            return round(scale, 1)


def write_state(path: Path, text: str) -> None:
    """Write a state file whole: a reader sees the old text or the new, never
    an empty or partial file."""
    path.parent.mkdir(exist_ok=True, parents=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}")
    try:
        tmp.write_text(text)
        tmp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def apply_scale(scale: float) -> None:
    subprocess.run(
        ["swaymsg", "output", "*", "scale", f"{scale:.1f}"],
        capture_output=True,
        check=False,
    )
    write_state(SCALE_FILE, f"output * scale {scale:.1f}\n")
    subprocess.Popen(
        ["pkill", "-RTMIN+11", "waybar"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_temperature() -> int:
    try:
        return int(TEMP_FILE.read_text().strip())
    except OSError, ValueError:
        return DEFAULT_TEMPERATURE


def apply_temperature(temp: float) -> None:
    kelvin = int(temp)
    write_state(TEMP_FILE, f"{kelvin}\n")
    subprocess.run(["pkill", "wlsunset"], capture_output=True, check=False)
    subprocess.Popen(
        ["wlsunset", "-T", str(kelvin + 1), "-t", str(kelvin)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


class LatestWriter:
    """Runs fn(value) on one worker thread, newest value wins.

    set() returns at once; a value set while a write runs replaces any not yet
    written, so a drag becomes a few writes and the popup never waits on them.
    """

    def __init__(
        self, fn: Callable[[float], object], on_bug: Callable[[str], bool | None]
    ) -> None:
        self._fn = fn
        self._cond = threading.Condition()
        self._want: float | None = None
        self._busy = False
        in_background(self._loop, on_bug)

    def set(self, value: float) -> None:
        with self._cond:
            self._want = value
            self._cond.notify_all()

    def flush(self, timeout: float) -> None:
        """Wait (at most timeout s) until the newest value is written."""
        with self._cond:
            self._cond.wait_for(lambda: self._want is None and not self._busy, timeout)

    def _loop(self) -> None:
        while True:
            with self._cond:
                self._cond.wait_for(lambda: self._want is not None)
                value, self._want = self._want, None
                self._busy = True
            try:
                if value is not None:
                    self._fn(value)
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()


@dataclass(frozen=True, slots=True)
class Slider:
    """One labelled slider: its range, marks, and the debounced apply."""

    label: str
    fmt: Callable[[float], str]
    lower: float
    upper: float
    step: float
    marks: list[tuple[float, str]]
    ticks: list[float]
    snap: Callable[[float], float]
    key: SliderKey
    delay: int  # ms of quiet before apply_fn runs
    apply_fn: Callable[[float], None]


def tenths(v: float) -> float:
    return round(v * 10) / 10


def percent(v: float) -> str:
    return f"{int(v * 100)}%"


class DisplayPopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.display")
        self._timeouts: dict[SliderKey, int] = {
            "scale": 0,
            "brightness": 0,
            "temperature": 0,
        }
        # key -> (apply_fn, value) while its debounce runs
        self._pending: dict[SliderKey, tuple[Callable[[float], None], float]] = {}
        self._brightness_writer: LatestWriter | None = None

    @override
    def build_ui(self) -> Gtk.Widget:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        container.add_css_class("display-container")

        title = Gtk.Label(label="Display")
        title.add_css_class("display-title")
        container.append(title)

        # --- Scale (swaymsg is fast, keep sync) ---
        self._build_slider(
            container,
            Slider(
                "SCALE",
                percent,
                1.0,
                2.0,
                0.1,
                marks=[(1.0, "100%"), (1.5, "150%"), (2.0, "200%")],
                ticks=[1.0 + i * 0.1 for i in range(11)],
                snap=tenths,
                key="scale",
                delay=500,
                apply_fn=apply_scale,
            ),
            get_current_scale(),
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
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_sigterm)

        # --- Night Light (file read is fast, keep sync) ---
        container.append(Gtk.Separator())
        self._build_slider(
            container,
            Slider(
                "NIGHT LIGHT",
                lambda v: f"{int(v * 1000)}K",
                2.5,
                6.5,
                0.1,
                marks=[(2.5, "2500K"), (4.5, "4500K"), (6.5, "6500K")],
                ticks=[2.5 + i * 0.5 for i in range(9)],
                snap=tenths,
                key="temperature",
                delay=500,
                apply_fn=lambda v: apply_temperature(v * 1000),
            ),
            get_temperature() / 1000,
        )

        return container

    def _on_sigterm(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def _load_brightness_async(self) -> None:
        """Probe the backend off the main thread, then build the slider on it."""

        def worker() -> None:
            found = brightness.probe()
            if found is not None:
                GLib.idle_add(self._build_brightness, *found)

        in_background(worker, self._show_bug)

    def _show_bug(self, msg: str) -> bool:
        """A worker's bug, shown in the brightness section it would fill."""
        label = copyable(Gtk.Label(label=msg))
        label.add_css_class("display-error")
        label.set_wrap(True)
        self._brightness_box.append(label)
        self._brightness_sep.set_visible(True)
        self._brightness_box.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _build_brightness(self, backend: brightness.Backend, pct: int) -> bool:
        # DDC writes take 0.1-3 s: they run on a worker, never on the main thread
        self._brightness_writer = LatestWriter(
            lambda v: brightness.set_pct(backend, v * 100), self._show_bug
        )
        self._build_slider(
            self._brightness_box,
            Slider(
                "BRIGHTNESS",
                percent,
                0.0,
                1.0,
                0.05,
                marks=[(0.0, "0%"), (0.5, "50%"), (1.0, "100%")],
                ticks=[i * 0.1 for i in range(11)],
                snap=lambda v: round(v * 20) / 20,
                key="brightness",
                delay=100,
                apply_fn=self._brightness_writer.set,
            ),
            pct / 100,
        )
        self._brightness_sep.set_visible(True)
        self._brightness_box.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _build_slider(self, container: Gtk.Box, slider: Slider, current: float) -> None:
        label = Gtk.Label(label=slider.label)
        label.add_css_class("section-label")
        label.set_halign(Gtk.Align.START)
        container.append(label)

        value_label = Gtk.Label(label=slider.fmt(current))
        value_label.add_css_class("section-value")
        container.append(value_label)

        adj = Gtk.Adjustment(
            value=current,
            lower=slider.lower,
            upper=slider.upper,
            step_increment=slider.step,
            page_increment=slider.step,
        )
        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        scale.set_draw_value(False)
        scale.set_digits(2)
        for t in slider.ticks:
            scale.add_mark(t, Gtk.PositionType.BOTTOM, None)
        for val, text in slider.marks:
            scale.add_mark(val, Gtk.PositionType.TOP, text)
        adj.connect("value-changed", self._on_slider_changed, value_label, slider)
        container.append(scale)

    def _on_slider_changed(
        self, adj: Gtk.Adjustment, value_label: Gtk.Label, slider: Slider
    ) -> None:
        snapped = slider.snap(adj.get_value())
        value_label.set_text(slider.fmt(snapped))
        key = slider.key
        if self._timeouts[key]:
            GLib.source_remove(self._timeouts[key])
        self._pending[key] = (slider.apply_fn, snapped)
        self._timeouts[key] = GLib.timeout_add(slider.delay, self._apply, key)

    def _apply(self, key: SliderKey) -> bool:
        self._timeouts[key] = 0
        apply_fn, value = self._pending.pop(key)
        apply_fn(value)
        return GLib.SOURCE_REMOVE

    @override
    def do_shutdown(self) -> None:
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


def main() -> int:
    return DisplayPopup().run()
