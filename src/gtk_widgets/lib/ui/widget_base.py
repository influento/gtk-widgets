"""Shared base class for GTK4 layer-shell popup widgets."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal, override

from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell

from gtk_widgets.lib.theme import render_css

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


# What the Gtk stubs' vfuncs take for an orientation (their own alias is private)
type Orientation = (
    Gtk.Orientation
    | Literal[
        "GTK_ORIENTATION_HORIZONTAL",
        "GTK_ORIENTATION_VERTICAL",
        "horizontal",
        "vertical",
    ]
)

type KeyHandler = Callable[[Gtk.EventControllerKey, int, int, Gdk.ModifierType], bool]
"""A "key-pressed" handler: (controller, keyval, keycode, state) -> handled."""


def load_css(css_path: Path | str) -> str:
    """Read a CSS file and replace @@TOKEN@@ placeholders with theme colors."""
    return render_css(Path(css_path).read_text(encoding="utf-8"))


def install_css(css: str) -> None:
    """Apply rendered CSS to the default display at application priority."""
    display = Gdk.Display.get_default()
    if display is None:
        raise RuntimeError("no display: GTK could not connect to Wayland")
    provider = Gtk.CssProvider()
    provider.load_from_string(css)
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def pass_wheel(widget: Gtk.Widget) -> None:
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

    def __init__(self, max_height: int, child: Gtk.Widget | None = None) -> None:
        super().__init__(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_height=True,
            max_content_height=max_height,
        )
        if child is not None:
            self.set_child(child)

    @override
    def do_measure(
        self, orientation: Orientation, for_size: int
    ) -> tuple[int, int, int, int]:
        mn, nat, _, _ = Gtk.ScrolledWindow.do_measure(self, orientation, for_size)
        child = self.get_child()
        if (
            orientation == Gtk.Orientation.HORIZONTAL
            and child is not None
            and child.measure(Gtk.Orientation.VERTICAL, -1)[1]
            > self.get_max_content_height()
        ):
            bar = self.get_vscrollbar().measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            mn, nat = mn + bar, nat + bar
        return mn, nat, -1, -1


def popup_window(
    app: Gtk.Application, on_dismiss: Callable[[], None], on_key: KeyHandler
) -> tuple[Gtk.ApplicationWindow, Gtk.Overlay]:
    """Fullscreen transparent layer-shell overlay with exclusive keyboard.
    A click on the backdrop calls on_dismiss(); key presses go to on_key.
    Returns (window, overlay); add the popup container with show_popup()."""
    # Classic scrollbars take their own space beside the content; overlay ones
    # are drawn over the right edge of every row (the gap is in BASE_CSS)
    settings = Gtk.Settings.get_default()
    if settings is None:
        raise RuntimeError("no display: GTK could not connect to Wayland")
    settings.props.gtk_overlay_scrolling = False
    win = Gtk.ApplicationWindow(application=app, title=app.get_application_id())

    Gtk4LayerShell.init_for_window(win)
    Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
    for edge in (
        Gtk4LayerShell.Edge.TOP,
        Gtk4LayerShell.Edge.BOTTOM,
        Gtk4LayerShell.Edge.LEFT,
        Gtk4LayerShell.Edge.RIGHT,
    ):
        Gtk4LayerShell.set_anchor(win, edge, anchor_to_edge=True)
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


def place_popup(
    win: Gtk.Window, overlay: Gtk.Overlay, container: Gtk.Widget, margin_top: int
) -> None:
    """Place the .popup container top-centre on the overlay, not yet shown
    (a resident app builds its window once and presents it on demand)."""
    container.add_css_class("popup")
    container.set_halign(Gtk.Align.CENTER)
    container.set_valign(Gtk.Align.START)
    container.set_margin_top(margin_top)
    overlay.add_overlay(container)
    win.set_child(overlay)


def show_popup(
    win: Gtk.Window, overlay: Gtk.Overlay, container: Gtk.Widget, margin_top: int
) -> None:
    """Place the .popup container top-centre on the overlay and present."""
    place_popup(win, overlay, container, margin_top)
    win.present()


class WidgetPopup(Gtk.Application):
    """Base GTK4 popup with layer-shell overlay, backdrop dismiss, and Esc/q close."""

    CSS = (
        ""  # optional override; by default style.css beside the subclass module is used
    )
    MARGIN_TOP = 40
    # False: build_ui() data arrives asynchronously and the widget calls
    # show_ui() once it is in, so the popup opens at its final size
    SHOW_ON_BUILD = True
    SHOW_TIMEOUT_MS = 1000  # show anyway if show_ui() has not come by then

    def __init__(self, application_id: str) -> None:
        super().__init__(application_id=application_id)
        self._unshown: tuple[Gtk.ApplicationWindow, Gtk.Overlay, Gtk.Widget] | None = (
            None
        )

    def _widget_css(self) -> str:
        """Rendered CSS for this widget: CSS if set, else style.css beside the subclass's module."""
        if self.CSS:
            return self.CSS
        module = sys.modules.get(type(self).__module__)
        module_file = (module.__file__ if module else None) or sys.argv[0]
        css_path = Path(module_file).resolve().parent / "style.css"
        return load_css(css_path) if css_path.exists() else ""

    @override
    def do_activate(self) -> None:
        if self.get_windows():
            return  # re-activated by a second launch; the popup is already up
        install_css(render_css(BASE_CSS) + self._widget_css())
        win, overlay = popup_window(self, self.quit, self._on_key)
        self._unshown = (win, overlay, self.build_ui())
        if self.SHOW_ON_BUILD:
            self.show_ui()
        else:
            GLib.timeout_add(self.SHOW_TIMEOUT_MS, self.show_ui)

    def show_ui(self) -> bool:
        """Present the popup built by build_ui(); later calls do nothing."""
        if self._unshown is not None:
            win, overlay, container = self._unshown
            self._unshown = None
            show_popup(win, overlay, container, self.MARGIN_TOP)
        return GLib.SOURCE_REMOVE

    def build_ui(self) -> Gtk.Widget:
        """Override to build widget content. Must return the container widget."""
        raise NotImplementedError

    def _on_key(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q):
            self.quit()
            return True
        return False
