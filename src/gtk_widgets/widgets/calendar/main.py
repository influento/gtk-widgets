#!/usr/bin/env python3
"""Calendar popup for waybar — native GTK4 calendar widget with Catppuccin Mocha theme."""

from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup


class CalendarPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.calendar")

    def build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("calendar-container")
        box.append(Gtk.Calendar())
        return box


def main() -> int:
    return CalendarPopup().run()
