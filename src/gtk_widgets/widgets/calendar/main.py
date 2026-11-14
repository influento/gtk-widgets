#!/usr/bin/env python3
"""Calendar popup for waybar — native GTK4 calendar widget with Catppuccin Mocha theme."""

from typing import override

from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup


class CalendarPopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.calendar")

    @override
    def build_ui(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("calendar-container")
        box.append(Gtk.Calendar())
        return box


def main() -> int:
    return CalendarPopup().run()
