#!/usr/bin/env python3
"""Power menu popup — lock, sleep, reboot, shut down."""

import os, subprocess, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gtk, WidgetPopup, load_css

CSS = load_css(os.path.join(_DIR, "style.css"))

ACTIONS = [
    ("󰌾", "Lock",      "color-blue",  [os.path.expanduser("~/.local/bin/lock")]),
    ("󰤄", "Sleep",     "color-mauve", ["systemctl", "suspend"]),
    ("󰜉", "Reboot",    "color-peach", ["systemctl", "reboot"]),
    ("󰐥", "Shut Down", "color-red",   ["systemctl", "poweroff"]),
]


class PowerPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.power")

    def build_ui(self):
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        container.add_css_class("power-container")

        for icon, label, color_class, cmd in ACTIONS:
            btn = Gtk.Button()
            btn.add_css_class("power-button")
            btn.add_css_class(color_class)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_halign(Gtk.Align.CENTER)

            icon_label = Gtk.Label(label=icon)
            icon_label.add_css_class("power-icon")
            box.append(icon_label)

            text_label = Gtk.Label(label=label)
            text_label.add_css_class("power-label")
            box.append(text_label)

            btn.set_child(box)
            btn.connect("clicked", self._on_action, cmd)
            container.append(btn)

        return container

    def _on_action(self, button, cmd):
        self.quit()
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    PowerPopup.CSS = CSS
    PowerPopup().run()
