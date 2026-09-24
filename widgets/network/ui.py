"""Small GTK helpers shared by the network popup (main.py) and its editor page."""

from lib.copy_label import copyable
from lib.widget_base import Gtk

from gi.repository import GLib, Pango

SWITCH_PENDING_S = 10  # a flip NM has not confirmed by then gives way to NM's value


def label(text="", css_class=None, xalign=0, hexpand=False, ellipsize=False):
    lbl = Gtk.Label(label=text, xalign=xalign, hexpand=hexpand)
    if css_class:
        lbl.add_css_class(css_class)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    return lbl


def error_label():
    """Hidden, wrapping, click-to-copy error line under a form."""
    lbl = copyable(label("", "net-form-error"))
    lbl.set_wrap(True)
    lbl.set_visible(False)
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
    otherwise moved by set_(NM's value). A flip shows at once; on_toggle sends
    a request and calls done(ok) when it returns. set_() leaves the last flip
    until every request has returned and NM reports the flipped value (fast
    clicks: NM passes through the earlier values on the way), until the last
    request failed, or for SWITCH_PENDING_S; set_() returns the value shown."""
    sw = Gtk.Switch(valign=Gtk.Align.CENTER)
    sw.add_css_class("net-switch")
    pending = {"want": None, "since": 0, "busy": 0}

    def state_set(_sw, active):
        pending["want"], pending["since"] = active, GLib.get_monotonic_time()
        pending["busy"] += 1
        on_toggle(active)
        return False  # show the flip now; syncs before NM catches up keep it

    handler = sw.connect("state-set", state_set)

    def set_(active):
        want = pending["want"]
        if want is not None:
            waited = (GLib.get_monotonic_time() - pending["since"]) / 1e6
            if (pending["busy"] or active != want) and waited < SWITCH_PENDING_S:
                return want
            pending["want"] = None
        sw.handler_block(handler)
        sw.set_active(active)
        sw.set_state(active)
        sw.handler_unblock(handler)
        return active

    def done(ok):
        pending["busy"] = max(0, pending["busy"] - 1)
        if not ok and not pending["busy"]:
            pending["want"] = None  # follow NM again
    sw.set_, sw.done = set_, done
    return sw


def section(text, *extra):
    row = hbox(6)
    row.add_css_class("net-section-row")
    row.append(label(text, "net-section", hexpand=True))
    for w in extra:
        row.append(w)
    return row


class KeyedList(Gtk.Box):
    """Rows keyed by id, updated in place and reordered on each sync."""

    def __init__(self, make_row, spacing=4):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        self._make_row = make_row
        self.rows = {}

    def sync(self, items):
        """items: [(key, data)] in display order; row.update(data) refreshes a row."""
        keys = {k for k, _ in items}
        for key in [k for k in self.rows if k not in keys]:
            self.remove(self.rows.pop(key))
        prev = None
        for key, data in items:
            row = self.rows.get(key)
            if row is None:
                row = self.rows[key] = self._make_row(key)
                self.append(row)
            row.update(data)
            self.reorder_child_after(row, prev)
            prev = row
        self.set_visible(bool(items))
