"""Clickable label that copies its text to the Wayland clipboard."""

import subprocess

from lib.widget_base import Gtk

from gi.repository import GLib, Pango

FLASH_MS = 1000  # how long a clicked label reads "Copied"


def copy_to_clipboard(text):
    """Copy via wl-copy, which keeps serving the text after the popup exits.
    Returns False if wl-clipboard is missing."""
    try:
        subprocess.Popen(["wl-copy", "--", text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True


class CopyLabel(Gtk.Label):
    """Ellipsized label; a click copies its copy text and flashes "Copied".

    Only the text itself is clickable (halign START). Content set during the
    flash is shown when it ends. The flash colour comes from the
    .copy-label-copied rule in the base CSS.
    """

    def __init__(self, css_class=None):
        super().__init__(xalign=0, hexpand=True, halign=Gtk.Align.START)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        if css_class:
            self.add_css_class(css_class)
        self.set_cursor_from_name("pointer")
        self._text = self._copy = ""
        self._flash_id = 0
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)

    def set_content(self, text, copy_text=None, tooltip=None):
        """Show `text`; a click copies `copy_text` (default: `text`).
        The tooltip (default: `text`) gets a "Click to copy" line."""
        self._text, self._copy = text, copy_text or text
        self.set_tooltip_text(f"{tooltip or text}\nClick to copy")
        if not self._flash_id:
            self.set_text(text)

    def _on_click(self, *_):
        if not self._copy or not copy_to_clipboard(self._copy):
            return
        self.set_text("Copied to clipboard")
        self.add_css_class("copy-label-copied")
        if self._flash_id:
            GLib.source_remove(self._flash_id)
        self._flash_id = GLib.timeout_add(FLASH_MS, self._end_flash)

    def _end_flash(self):
        self._flash_id = 0
        self.remove_css_class("copy-label-copied")
        self.set_text(self._text)
        return GLib.SOURCE_REMOVE
