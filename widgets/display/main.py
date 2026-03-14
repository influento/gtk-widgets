#!/usr/bin/env python3
"""Display settings popup — scale, brightness, night light temperature."""

import json, os, subprocess, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gtk, WidgetPopup, load_css

from gi.repository import GLib

CSS = load_css(os.path.join(_DIR, "style.css"))

TEMP_FILE = os.path.expanduser("~/.config/wlsunset/temperature")


def get_current_scale():
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs"], capture_output=True, text=True
        )
        outputs = json.loads(result.stdout)
        for output in outputs:
            if output.get("active"):
                return output.get("scale", 1.0)
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


def detect_brightness_backend():
    """Return 'backlight', 'ddc', or None."""
    try:
        result = subprocess.run(
            ["brightnessctl", "-c", "backlight", "info"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "backlight"
    except FileNotFoundError:
        pass
    try:
        result = subprocess.run(
            ["ddcutil", "getvcp", "10"], capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "ddc"
    except FileNotFoundError:
        pass
    return None


def get_brightness(backend):
    if backend == "backlight":
        try:
            cur = int(subprocess.run(
                ["brightnessctl", "-c", "backlight", "get"],
                capture_output=True, text=True,
            ).stdout.strip())
            mx = int(subprocess.run(
                ["brightnessctl", "-c", "backlight", "max"],
                capture_output=True, text=True,
            ).stdout.strip())
            return round(cur * 100 / mx)
        except Exception:
            return 100
    else:
        try:
            result = subprocess.run(
                ["ddcutil", "getvcp", "10"], capture_output=True, text=True,
            )
            for part in result.stdout.split(","):
                if "current value" in part:
                    return int(part.split("=")[1].strip())
        except Exception:
            pass
        return 100


def apply_brightness(backend, pct):
    pct = int(pct)
    if backend == "backlight":
        subprocess.run(
            ["brightnessctl", "-c", "backlight", "set", f"{pct}%"],
            capture_output=True,
        )
    else:
        subprocess.run(
            ["ddcutil", "setvcp", "10", str(pct)],
            capture_output=True,
        )


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


class DisplayPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.display")
        self._timeouts = {"scale": 0, "brightness": 0, "temperature": 0}

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        container.add_css_class("display-container")

        title = Gtk.Label(label="Display")
        title.add_css_class("display-title")
        container.append(title)

        # --- Scale ---
        self._build_slider(
            container, "SCALE", get_current_scale(), lambda v: f"{int(v * 100)}%",
            1.0, 2.0, 0.1,
            marks=[(1.0, "100%"), (1.5, "150%"), (2.0, "200%")],
            ticks=[1.0 + i * 0.1 for i in range(11)],
            snap=lambda v: round(v * 10) / 10,
            key="scale", delay=500, apply_fn=apply_scale,
        )

        # --- Brightness (backlight or DDC/CI) ---
        brightness_backend = detect_brightness_backend()
        if brightness_backend:
            delay = 100 if brightness_backend == "backlight" else 500
            container.append(Gtk.Separator())
            self._build_slider(
                container, "BRIGHTNESS",
                get_brightness(brightness_backend) / 100,
                lambda v: f"{int(v * 100)}%",
                0.0, 1.0, 0.05,
                marks=[(0.0, "0%"), (0.5, "50%"), (1.0, "100%")],
                ticks=[i * 0.1 for i in range(11)],
                snap=lambda v: round(v * 20) / 20,
                key="brightness", delay=delay,
                apply_fn=lambda v: apply_brightness(brightness_backend, v * 100),
            )

        # --- Night Light ---
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
        self._timeouts[key] = GLib.timeout_add(
            delay, self._apply, key, apply_fn, snapped
        )

    def _apply(self, key, apply_fn, value):
        self._timeouts[key] = 0
        apply_fn(value)
        return GLib.SOURCE_REMOVE


if __name__ == "__main__":
    DisplayPopup.CSS = CSS
    DisplayPopup().run()
