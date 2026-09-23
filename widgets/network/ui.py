"""Small GTK helpers shared by the network popup (main.py) and its editor page."""

from lib.widget_base import Gtk

from gi.repository import Pango


def label(text="", css_class=None, xalign=0, hexpand=False, ellipsize=False):
    lbl = Gtk.Label(label=text, xalign=xalign, hexpand=hexpand)
    if css_class:
        lbl.add_css_class(css_class)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    return lbl


def button(text, css_class="net-btn", tooltip=None, on_click=None):
    btn = Gtk.Button(label=text)
    btn.add_css_class(css_class)
    btn.set_valign(Gtk.Align.CENTER)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    if on_click:
        btn.connect("clicked", lambda *_: on_click())
    return btn


def glyph_button(glyph, tooltip, on_click=None, css_class=None):
    btn = button(glyph, "net-icon-btn", tooltip, on_click)
    if css_class:
        btn.add_css_class(css_class)
    return btn


def hbox(spacing=8, css_class=None):
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if css_class:
        box.add_css_class(css_class)
    return box


def vbox(spacing=4, css_class=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    if css_class:
        box.add_css_class(css_class)
    return box


def entry(placeholder, secret=False, on_activate=None):
    ent = Gtk.PasswordEntry(show_peek_icon=True) if secret else Gtk.Entry()
    ent.add_css_class("net-entry")
    ent.set_hexpand(True)
    if secret:
        ent.set_property("placeholder-text", placeholder)
    else:
        ent.set_placeholder_text(placeholder)
    if on_activate:
        ent.connect("activate", lambda *_: on_activate())
    return ent


def switch(on_toggle):
    """Gtk.Switch that reports user flips via on_toggle(active) and is
    otherwise only moved by set(), so NM state stays the source of truth."""
    sw = Gtk.Switch(valign=Gtk.Align.CENTER)
    sw.add_css_class("net-switch")

    def state_set(_sw, active):
        on_toggle(active)
        return True  # keep the visual state until NM reports the change

    handler = sw.connect("state-set", state_set)

    def set_(active):
        sw.handler_block(handler)
        sw.set_active(active)
        sw.set_state(active)
        sw.handler_unblock(handler)
    sw.set_ = set_
    return sw


def section(text, *extra):
    row = hbox(6)
    row.add_css_class("net-section-row")
    row.append(label(text, "net-section", hexpand=True))
    for w in extra:
        row.append(w)
    return row
