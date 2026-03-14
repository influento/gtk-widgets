#!/usr/bin/env python3
"""Calendar popup for waybar — native GTK4 calendar widget with Catppuccin Mocha theme."""

import os, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))

from lib.widget_base import Gtk, WidgetPopup, load_css

CSS = load_css(os.path.join(_DIR, "style.css"))


class CalendarPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.calendar")

    def build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("calendar-container")
        box.append(Gtk.Calendar())
        return box


if __name__ == "__main__":
    CalendarPopup.CSS = CSS
    CalendarPopup().run()
