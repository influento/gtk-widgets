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
from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell  # noqa: E402

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

/* Scrollbars get a column of their own beside the content while a list
   overflows (popup_window turns overlay scrolling off), so rows never run
   under them: a thin slider, a gap on the content side, no trough. */
scrollbar {
  background-color: transparent;
  border: none;
  transition: none;
}

scrollbar.vertical {
  margin-left: 6px;
}

scrollbar.horizontal {
  margin-top: 6px;
}

scrollbar > range > trough {
  background-color: transparent;
  border: none;
}

scrollbar > range > trough > slider {
  margin: 0;
  min-width: 3px;
  min-height: 3px;
  border: 1px solid alpha(@@CRUST@@, 0.4);
  border-radius: 3px;
  background-clip: border-box;
  background-color: alpha(@@TEXT@@, 0.4);
  transition: none;
}

scrollbar > range > trough > slider:hover,
scrollbar > range > trough > slider:active {
  background-color: alpha(@@TEXT@@, 0.6);
}

scrollbar.vertical > range > trough > slider {
  min-height: 40px;
}

scrollbar.horizontal > range > trough > slider {
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


def pass_wheel(widget):
    """Leave the mouse wheel to the enclosing scrolled list: a slider or spin
    button in a list otherwise takes it wherever the pointer lands, and the
    list stops scrolling."""
    controllers = widget.observe_controllers()
    for i in range(controllers.get_n_items()):
        ctrl = controllers.get_item(i)
        if isinstance(ctrl, Gtk.EventControllerScroll):
            ctrl.set_propagation_phase(Gtk.PropagationPhase.NONE)


class VScroller(Gtk.ScrolledWindow):
    """Vertical-only scrolled list that grows with its content up to
    max_height. While the content overflows, its width includes the
    scrollbar's column: GTK 4.22 leaves a classic scrollbar out of the measured
    width, so a popup sized to its content lost its right edge to the
    scrollbar, and the rows ran under it."""

    def __init__(self, max_height, child=None):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER,
                         propagate_natural_height=True, max_content_height=max_height)
        if child is not None:
            self.set_child(child)

    def do_measure(self, orientation, for_size):
        mn, nat, _, _ = Gtk.ScrolledWindow.do_measure(self, orientation, for_size)
        child = self.get_child()
        if (orientation == Gtk.Orientation.HORIZONTAL and child is not None
                and child.measure(Gtk.Orientation.VERTICAL, -1)[1] > self.get_max_content_height()):
            bar = self.get_vscrollbar().measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            mn, nat = mn + bar, nat + bar
        return mn, nat, -1, -1


def popup_window(app, on_dismiss, on_key):
    """Fullscreen transparent layer-shell overlay with exclusive keyboard.
    A click on the backdrop calls on_dismiss(); key presses go to on_key.
    Returns (window, overlay); add the popup container with show_popup()."""
    # Classic scrollbars take their own space beside the content; overlay ones
    # are drawn over the right edge of every row (the gap is in BASE_CSS)
    Gtk.Settings.get_default().set_property("gtk-overlay-scrolling", False)
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
    # False: build_ui() data arrives asynchronously and the widget calls
    # show_ui() once it is in, so the popup opens at its final size
    SHOW_ON_BUILD = True
    SHOW_TIMEOUT_MS = 1000  # show anyway if show_ui() has not come by then

    def __init__(self, application_id):
        super().__init__(application_id=application_id)
        self._unshown = None

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
        self._unshown = (win, overlay, self.build_ui())
        if self.SHOW_ON_BUILD:
            self.show_ui()
        else:
            GLib.timeout_add(self.SHOW_TIMEOUT_MS, self.show_ui)

    def show_ui(self):
        """Present the popup built by build_ui(); later calls do nothing."""
        if self._unshown is not None:
            win, overlay, container = self._unshown
            self._unshown = None
            show_popup(win, overlay, container, self.MARGIN_TOP)
        return GLib.SOURCE_REMOVE

    def build_ui(self):
        """Override to build widget content. Must return the container widget."""
        raise NotImplementedError

    def _on_key(self, controller, keyval, keycode, state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False
