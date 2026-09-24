"""Click-to-copy labels: CopyLabel, and copyable() for error lines."""

import subprocess

from lib.widget_base import Gtk

from gi.repository import GLib, Pango

FLASH_MS = 1000  # how long a clicked label reads "Copied"
COPIED = "Copied to clipboard"


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
        self.set_text(COPIED)
        self.add_css_class("copy-label-copied")
        if self._flash_id:
            GLib.source_remove(self._flash_id)
        self._flash_id = GLib.timeout_add(FLASH_MS, self._end_flash)

    def _end_flash(self):
        self._flash_id = 0
        self.remove_css_class("copy-label-copied")
        self.set_text(self._text)
        return GLib.SOURCE_REMOVE


def copyable(label, on=True, copy_text=None):
    """Let a plain Gtk.Label (an error line) copy its text on click, or stop it.

    A click copies `copy_text` (default: the text shown) and flashes "Copied
    to clipboard" at the label's current size, so a wrapped error does not
    reflow the popup. Labels that show errors only some of the time call this
    again with on=False for other messages. Sets a "Click to copy" tooltip
    while on. Returns the label.
    """
    copier = getattr(label, "_copier", None)
    if copier is None:
        if not on:
            return label
        copier = label._copier = _Copier(label)
    copier.on, copier.copy_text = on, copy_text
    label.set_cursor_from_name("pointer" if on else None)
    label.set_tooltip_text("Click to copy" if on else None)
    return label


class _Copier:
    def __init__(self, label):
        self.label = label
        self.on, self.copy_text = False, None
        self.text, self.size, self.flash_id = "", (-1, -1), 0
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        label.add_controller(click)

    def _on_click(self, *_):
        shown = self.label.get_text()
        if self.flash_id and shown == COPIED:
            shown = self.text
        if not self.on or not shown or not copy_to_clipboard(self.copy_text or shown):
            return
        self.text = shown
        if self.flash_id:
            GLib.source_remove(self.flash_id)
        else:
            self.size = self.label.get_size_request()
            self.label.set_size_request(self.label.get_width(), self.label.get_height())
        self.label.set_text(COPIED)
        self.label.add_css_class("copy-label-copied")
        self.flash_id = GLib.timeout_add(FLASH_MS, self._end_flash)

    def _end_flash(self):
        self.flash_id = 0
        self.label.remove_css_class("copy-label-copied")
        self.label.set_size_request(*self.size)
        if self.label.get_text() == COPIED:  # else a new message replaced it meanwhile
            self.label.set_text(self.text)
        return GLib.SOURCE_REMOVE
