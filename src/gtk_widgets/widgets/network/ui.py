"""Small GTK helpers shared by the network popup (main.py) and its editor page."""

from collections.abc import Callable
from typing import Protocol

from gi.repository import GLib, Pango

from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk

SWITCH_PENDING_S = 10  # a flip NM has not confirmed by then gives way to NM's value
US_PER_S = 1e6  # GLib's monotonic time is in microseconds


def label(
    text: str = "",
    css_class: str | None = None,
    xalign: float = 0,
    *,
    hexpand: bool = False,
    ellipsize: bool = False,
) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=xalign, hexpand=hexpand)
    if css_class:
        lbl.add_css_class(css_class)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    return lbl


def error_label() -> Gtk.Label:
    """Hidden, wrapping, click-to-copy error line under a form."""
    lbl = copyable(label("", "net-form-error"))
    lbl.set_wrap(True)
    lbl.set_visible(False)
    return lbl


def button(
    text: str,
    css_class: str = "net-btn",
    tooltip: str | None = None,
    on_click: Callable[[], None] | None = None,
) -> Gtk.Button:
    btn = Gtk.Button(label=text)
    btn.add_css_class(css_class)
    btn.set_valign(Gtk.Align.CENTER)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    if on_click:
        click = on_click

        def clicked(_btn: Gtk.Button) -> None:
            click()

        _ = btn.connect("clicked", clicked)
    return btn


def glyph_button(
    glyph: str,
    tooltip: str,
    on_click: Callable[[], None] | None = None,
    css_class: str | None = None,
) -> Gtk.Button:
    btn = button(glyph, "net-icon-btn", tooltip, on_click)
    if css_class:
        btn.add_css_class(css_class)
    return btn


def hbox(spacing: int = 8, css_class: str | None = None) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if css_class:
        box.add_css_class(css_class)
    return box


def vbox(spacing: int = 4, css_class: str | None = None) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    if css_class:
        box.add_css_class(css_class)
    return box


def entry(
    placeholder: str,
    *,
    secret: bool = False,
    on_activate: Callable[[], None] | None = None,
) -> Gtk.Entry | Gtk.PasswordEntry:
    ent = Gtk.PasswordEntry(show_peek_icon=True) if secret else Gtk.Entry()
    ent.add_css_class("net-entry")
    ent.set_hexpand(True)
    if isinstance(ent, Gtk.PasswordEntry):
        ent.set_property("placeholder-text", placeholder)
    else:
        ent.set_placeholder_text(placeholder)
    if on_activate:
        activate = on_activate

        def activated(_ent: Gtk.Entry | Gtk.PasswordEntry) -> None:
            activate()

        _ = ent.connect("activate", activated)
    return ent


class OnToggle(Protocol):
    def __call__(self, *, on: bool) -> None: ...


class NetSwitch(Gtk.Switch):
    """Gtk.Switch that reports user flips via on_toggle(on=active) and is
    otherwise moved by set_(active=NM's value). A flip shows at once; on_toggle sends
    a request and calls done(ok=...) when it returns. set_() leaves the last
    flip until every request has returned and NM reports the flipped value
    (fast clicks: NM passes through the earlier values on the way), until the
    last request failed, or for SWITCH_PENDING_S; set_() returns the value
    shown."""

    def __init__(self, on_toggle: OnToggle) -> None:
        super().__init__(valign=Gtk.Align.CENTER)
        self.add_css_class("net-switch")
        self._on_toggle = on_toggle
        self._want: bool | None = None
        self._since = 0
        self._busy = 0
        self._handler = self.connect("state-set", self._state_set)

    def _state_set(self, _sw: Gtk.Switch, state: int) -> bool:
        active = bool(state)  # a gboolean
        self._want, self._since = active, GLib.get_monotonic_time()
        self._busy += 1
        self._on_toggle(on=active)
        return False  # show the flip now; syncs before NM catches up keep it

    def set_(self, *, active: bool) -> bool:
        want = self._want
        if want is not None:
            waited = (GLib.get_monotonic_time() - self._since) / US_PER_S
            if (self._busy or active != want) and waited < SWITCH_PENDING_S:
                return want
            self._want = None
        self.handler_block(self._handler)
        self.set_active(active)
        self.set_state(active)
        self.handler_unblock(self._handler)
        return active

    def done(self, *, ok: bool) -> None:
        self._busy = max(0, self._busy - 1)
        if not ok and not self._busy:
            self._want = None  # follow NM again


def switch(on_toggle: OnToggle) -> NetSwitch:
    return NetSwitch(on_toggle)


def section(text: str, *extra: Gtk.Widget) -> Gtk.Box:
    row = hbox(6)
    row.add_css_class("net-section-row")
    row.append(label(text, "net-section", hexpand=True))
    for w in extra:
        row.append(w)
    return row


class KeyedRow[D](Gtk.Box):
    """A KeyedList row: update(data) refreshes it."""

    def update(self, data: D) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.update({type(data).__name__})"
        )


class KeyedList[K, D](Gtk.Box):
    """Rows keyed by id, updated in place and reordered on each sync."""

    def __init__(self, make_row: Callable[[K], KeyedRow[D]], spacing: int = 4) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        self._make_row = make_row
        self.rows: dict[K, KeyedRow[D]] = {}

    def sync(self, items: list[tuple[K, D]]) -> None:
        """items: [(key, data)] in display order; row.update(data) refreshes a row."""
        keys = {k for k, _ in items}
        for key in [k for k in self.rows if k not in keys]:
            self.remove(self.rows.pop(key))
        prev: KeyedRow[D] | None = None
        for key, data in items:
            row = self.rows.get(key)
            if row is None:
                row = self.rows[key] = self._make_row(key)
                self.append(row)
            row.update(data)
            self.reorder_child_after(row, prev)
            prev = row
        self.set_visible(bool(items))
