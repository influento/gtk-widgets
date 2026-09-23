"""Shared base class for GTK4 layer-shell popup widgets."""

import json
import os
import re
import sys

# gtk4-layer-shell must be loaded before libwayland-client. A bare soname is
# resolved by the dynamic loader, so this works on any distro library layout.
if "LD_PRELOAD" not in os.environ:
    os.environ["LD_PRELOAD"] = "libgtk4-layer-shell.so.0"
    os.execvp(sys.executable, [sys.executable] + sys.argv)

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, Gtk, Gtk4LayerShell  # noqa: E402

_THEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "themes")
_CURRENT_THEME = os.path.join(_THEMES_DIR, "current.json")  # symlink set by install.sh
_FALLBACK_THEME = os.path.join(_THEMES_DIR, "catppuccin-mocha.json")

BASE_CSS = """
window {
  background-color: transparent;
}

/* Every popup container (added by WidgetPopup): the flush 1px border and
   radius required by the design rules, theme background/text colours, and
   the toolkit font, which all children inherit. */
.popup {
  background-color: @@BASE@@;
  color: @@TEXT@@;
  border: 1px solid @@SURFACE1@@;
  border-radius: 8px;
  font-family: "JetBrainsMono Nerd Font", monospace;
}

/* lib/copy_label.py flash; outranks a widget's single-class label colour */
.popup label.copy-label-copied {
  color: @@GREEN@@;
}

/* Overlay scrollbars keep their thin idle look: Adwaita widens them and
   paints a trough on hover/drag. Application priority beats the theme. */
scrollbar.overlay-indicator {
  background-color: transparent;
  border-color: transparent;
  transition: none;
}

scrollbar.overlay-indicator > range > trough > slider {
  margin: 0;
  min-width: 3px;
  min-height: 3px;
  border: 1px solid alpha(@@CRUST@@, 0.4);
  background-color: alpha(@@TEXT@@, 0.4);
  transition: none;
}

scrollbar.overlay-indicator.vertical > range > trough > slider {
  margin: 2px 0;
  min-height: 40px;
}

scrollbar.overlay-indicator.horizontal > range > trough > slider {
  margin: 0 2px;
  min-width: 40px;
}

/* Tooltips are separate surfaces outside .popup: theme them to match. */
tooltip {
  background-color: @@MANTLE@@;
  color: @@TEXT@@;
  border: 1px solid @@SURFACE1@@;
  border-radius: 6px;
  box-shadow: none;
  font-family: "JetBrainsMono Nerd Font", monospace;
  font-size: 13px;
}
"""


def _theme_path():
    """$GTK_WIDGETS_THEME, else the install.sh symlink, else the bundled default."""
    override = os.environ.get("GTK_WIDGETS_THEME")
    if override:
        return override
    if os.path.exists(_CURRENT_THEME):
        return _CURRENT_THEME
    return _FALLBACK_THEME


def _load_theme():
    """Load theme colors from JSON. Returns dict of {NAME: hex_value}."""
    with open(_theme_path()) as f:
        return json.load(f)["colors"]


def render_css(css):
    """Replace @@TOKEN@@ placeholders in a CSS string with theme colors."""
    colors = _load_theme()
    def replace_token(m):
        name = m.group(1)
        if name.endswith("_RAW"):
            return colors.get(name[:-4], m.group(0))
        return f"#{colors[name]}" if name in colors else m.group(0)
    return re.sub(r"@@([A-Z][A-Z0-9_]*)@@", replace_token, css)


def load_css(css_path):
    """Read a CSS file and replace @@TOKEN@@ placeholders with theme colors."""
    with open(css_path) as f:
        return render_css(f.read())


def install_css(css):
    """Apply rendered CSS to the default display at application priority."""
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def popup_window(app, on_dismiss, on_key):
    """Fullscreen transparent layer-shell overlay with exclusive keyboard.
    A click on the backdrop calls on_dismiss(); key presses go to on_key.
    Returns (window, overlay); add the popup container with show_popup()."""
    win = Gtk.ApplicationWindow(application=app, title=app.get_application_id())

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
    backdrop_click.connect("released", lambda *_: on_dismiss())
    backdrop.add_controller(backdrop_click)
    overlay.set_child(backdrop)

    controller = Gtk.EventControllerKey()
    controller.connect("key-pressed", on_key)
    win.add_controller(controller)
    return win, overlay


def show_popup(win, overlay, container, margin_top):
    """Place the .popup container top-centre on the overlay and present."""
    container.add_css_class("popup")
    container.set_halign(Gtk.Align.CENTER)
    container.set_valign(Gtk.Align.START)
    container.set_margin_top(margin_top)
    overlay.add_overlay(container)
    win.set_child(overlay)
    win.present()


class WidgetPopup(Gtk.Application):
    """Base GTK4 popup with layer-shell overlay, backdrop dismiss, and Esc/q close."""

    CSS = ""  # optional override; by default style.css beside the subclass module is used
    MARGIN_TOP = 40

    def __init__(self, application_id):
        super().__init__(application_id=application_id)

    def _widget_css(self):
        """Rendered CSS for this widget: CSS if set, else style.css beside the subclass's module."""
        if self.CSS:
            return self.CSS
        module = sys.modules.get(type(self).__module__)
        module_file = getattr(module, "__file__", None) or sys.argv[0]
        css_path = os.path.join(os.path.dirname(os.path.realpath(module_file)), "style.css")
        return load_css(css_path) if os.path.exists(css_path) else ""

    def do_activate(self):
        if self.get_windows():
            return  # re-activated by a second launch; the popup is already up
        install_css(render_css(BASE_CSS) + self._widget_css())
        win, overlay = popup_window(self, self.quit, self._on_key)
        show_popup(win, overlay, self.build_ui(), self.MARGIN_TOP)

    def build_ui(self):
        """Override to build widget content. Must return the container widget."""
        raise NotImplementedError

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False
