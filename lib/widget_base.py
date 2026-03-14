"""Shared base class for GTK4 layer-shell popup widgets."""

import json
import os
import re
import sys

# gtk4-layer-shell must be loaded before libwayland-client
if "LD_PRELOAD" not in os.environ:
    os.environ["LD_PRELOAD"] = "/usr/lib/libgtk4-layer-shell.so"
    os.execvp(sys.executable, [sys.executable] + sys.argv)

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gtk, Gtk4LayerShell  # noqa: E402

_LIB_DIR = os.path.dirname(__file__)
_DEFAULT_THEME = os.path.join(_LIB_DIR, "..", "themes", "current.json")

BASE_CSS = """
window {
  background-color: transparent;
}
"""


def _load_theme():
    """Load theme colors from JSON. Returns dict of {NAME: hex_value}."""
    theme_path = os.environ.get("GTK_WIDGETS_THEME", _DEFAULT_THEME)
    with open(theme_path) as f:
        return json.load(f)["colors"]


def load_css(css_path):
    """Read a CSS file and replace @@TOKEN@@ placeholders with theme colors."""
    colors = _load_theme()
    css = open(css_path).read()
    def replace_token(m):
        name = m.group(1)
        if name.endswith("_RAW"):
            return colors.get(name[:-4], m.group(0))
        return f"#{colors[name]}" if name in colors else m.group(0)
    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", replace_token, css)


class WidgetPopup(Gtk.Application):
    """Base GTK4 popup with layer-shell overlay, backdrop dismiss, and Esc/q close."""

    CSS = ""
    MARGIN_TOP = 40

    def __init__(self, application_id):
        super().__init__(application_id=application_id)

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(BASE_CSS + self.CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win = Gtk.ApplicationWindow(application=self, title=self.get_application_id())

        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.BOTTOM, True)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.RIGHT, True)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)

        overlay = Gtk.Overlay()
        backdrop = Gtk.DrawingArea()
        backdrop.set_hexpand(True)
        backdrop.set_vexpand(True)
        backdrop_click = Gtk.GestureClick()
        backdrop_click.connect("released", lambda *_: self.quit())
        backdrop.add_controller(backdrop_click)
        overlay.set_child(backdrop)

        container = self.build_ui()
        container.set_halign(Gtk.Align.CENTER)
        container.set_valign(Gtk.Align.START)
        container.set_margin_top(self.MARGIN_TOP)
        overlay.add_overlay(container)

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key)
        win.add_controller(controller)

        win.set_child(overlay)
        win.present()

    def build_ui(self):
        """Override to build widget content. Must return the container widget."""
        raise NotImplementedError

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False
