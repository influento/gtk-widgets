#!/usr/bin/env python3
"""Audio popup: the mixer (popup.py), or an error popup when libpulse is missing."""

from typing import override

from gtk_widgets.lib.ui.widget_base import Gtk, WidgetPopup
from gtk_widgets.widgets.audio.parts import APP_ID, error_box, popup_frame

try:
    from gtk_widgets.widgets.audio import popup
except OSError:  # libpulse.so.0 missing
    popup = None


class NoPulsePopup(WidgetPopup):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    @override
    def build_ui(self) -> Gtk.Widget:
        container, _ = popup_frame()
        container.append(
            error_box(
                "libpulse not found", "Install libpulse (pulled in by pipewire-pulse)"
            )
        )
        return container


def main() -> int:
    return (NoPulsePopup() if popup is None else popup.AudioPopup()).run()
