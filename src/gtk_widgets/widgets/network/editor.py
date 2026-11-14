"""Edit page of the network popup: settings of one saved Wi-Fi, Ethernet or
WireGuard profile (general, Wi-Fi, security, MAC, Ethernet, IPv4/IPv6, routes,
WireGuard interface and peers). Other profile types, security types other than
WPA/WPA3 Personal and PEAP/TTLS without certificates, and every setting not shown
aren't editable here; a save keeps them as stored. The less common fields of a
section sit in its collapsed More part.

The page edits a clone of the saved profile and writes only the fields it
shows, so every other setting survives a save. Save is enabled while the
candidate differs from that baseline and passes the field checks plus
NM's own verify(). Secrets are fetched when a secret field is revealed, and
before any save that carries a secret or changes the set of WireGuard peers:
NM keeps the stored secrets of an update that has none, but an update with
any secret replaces them all (a new peer PSK alone wipes the private key and
the other PSKs), and re-applying its cached secrets fails once a peer that
had a PSK is gone. Such updates must carry the complete set.
"""

import base64
import os
import pwd
import re
import shutil
import socket
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from gi.repository import NM, Gio, GLib, GObject

from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import Gtk, VScroller, pass_wheel
from gtk_widgets.widgets.network.nmutil import (
    EAP_INNER,
    EAP_METHODS,
    IPV4_BITS,
    IPV6_BITS,
    VPN_TYPES,
    EapValues,
    apply_eap,
    connection_security,
    connection_ssid,
    eap_problem,
    eap_values,
    error_text,
    freq_band,
    is_hotspot,
    mac_problem,
    nullable,
    parse_cidr,
    parse_ip,
    password_problem,
    reapply_refusal_text,
    ssid_text,
    wg_key_problem,
)
from gtk_widgets.widgets.network.ui import (
    button,
    error_label,
    glyph_button,
    hbox,
    label,
    vbox,
)

EDITABLE_TYPES = ("802-11-wireless", "802-3-ethernet", "wireguard")
SECRET_SETTINGS = ("802-11-wireless-security", "802-1x", "wireguard")
FAMILIES = ((socket.AF_INET, "ipv4", "IPv4"), (socket.AF_INET6, "ipv6", "IPv6"))
IP_METHODS = {
    "ipv4": [
        ("auto", "Automatic (DHCP)"),
        ("manual", "Manual"),
        ("link-local", "Link-local"),
        ("disabled", "Disabled"),
    ],
    "ipv6": [
        ("auto", "Automatic"),
        ("dhcp", "DHCP only"),
        ("manual", "Manual"),
        ("link-local", "Link-local"),
        ("ignore", "Ignore"),
        ("disabled", "Disabled"),
    ],
}
METERED = [
    (NM.Metered.UNKNOWN, "Automatic"),
    (NM.Metered.YES, "Yes"),
    (NM.Metered.NO, "No"),
]
BANDS: list[tuple[str | None, str]] = [
    (None, "Automatic"),
    ("bg", "2.4 GHz"),
    ("a", "5 GHz"),
]
MAC_MODES: list[tuple[str | None, str]] = [
    (None, "Default"),
    ("permanent", "Permanent"),
    ("random", "Random (new every connect)"),
    ("stable", "Stable (fixed per network)"),
    ("preserve", "Preserve"),
    ("custom", "Custom"),
]
WOL = NM.SettingWiredWakeOnLan
WOWL = NM.SettingWirelessWakeOnWLan
POWERSAVE = [
    (int(NM.SettingWirelessPowersave.DEFAULT), "Default"),
    (int(NM.SettingWirelessPowersave.DISABLE), "Off"),
    (int(NM.SettingWirelessPowersave.ENABLE), "On"),
]
WAKE_ON_WLAN = [
    (int(WOWL.DEFAULT), "Default"),
    (0, "Off"),
    (int(WOWL.MAGIC), "Magic packet"),
    (int(WOWL.ANY), "Any"),
]
# None: negotiated; "kept": a stored forced mode, left as it is
type LinkMode = tuple[int, str | None] | Literal["kept"] | None
HALF_DUPLEX_MAX_MBPS = 100  # half duplex only where it still exists in practice
# fixed link modes
LINK_MODES: list[tuple[LinkMode, str]] = [
    (None, "Automatic"),
    *(
        ((speed, duplex), f"{speed} Mb/s, {duplex} duplex")
        for speed in (10, 100, 1000, 2500, 5000, 10000)
        for duplex in (("full", "half") if speed <= HALF_DUPLEX_MAX_MBPS else ("full",))
    ),
]
CLIENT_IDS: list[tuple[str | None, str]] = [
    (None, "Default"),
    ("mac", "MAC address"),
    ("perm-mac", "Permanent MAC"),
    ("stable", "Stable (per profile)"),
    ("duid", "DUID"),
    ("custom", "Custom"),
]
IP6_PRIVACY = [
    (-1, "Default"),
    (0, "Off"),
    (1, "Prefer public"),
    (2, "Prefer temporary"),
]
HEX_ID = re.compile(r"[0-9a-fA-F]{2}(:[0-9a-fA-F]{2})+")
# NM refuses to reapply these to a connected device (see _reapply)
ON_RECONNECT = "Takes effect on reconnect"
LABEL_CHARS = 15
LAST_2GHZ_CHANNEL = 14
LAST_5GHZ_CHANNEL = 177  # leaves out the 4.9 GHz (Japan) block
MAX_MTU = 9000
MAX_PORT = 65535
MAX_FWMARK = 0xFFFFFFFF
DNS_PRIORITY_RANGE = (-(2**31), 2**31 - 1)
ROUTE_TABLE_RANGE = (0, 2**32 - 1)
WG_PUBKEY_TIMEOUT_S = 2

type Applier = Callable[[NM.Connection], None]
"""Writes some fields into the candidate; raises FieldError on a bad one."""
type SecretGetter = Callable[[NM.Connection], str | None]


class EditHost(Protocol):
    """What the page needs of the popup."""

    @property
    def client(self) -> NM.Client | None: ...

    def queue_sync(self) -> None: ...


class FieldError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(message)
        self.key = key


def shown_metered(s_con: NM.SettingConnection) -> NM.Metered:
    """Metered value the dropdown shows: the guessed values show as Automatic."""
    cur = s_con.get_metered()
    return cur if cur in {NM.Metered.YES, NM.Metered.NO} else NM.Metered.UNKNOWN


def split_list(text: str) -> list[str]:
    return [x for x in (p.strip() for p in text.replace(";", ",").split(",")) if x]


def on_reconnect(hint: str | None = None) -> str:
    return f"{hint}. {ON_RECONNECT}" if hint else ON_RECONNECT


def channels(band: str) -> list[int]:
    """Channels NM accepts for a band ('bg' or 'a'); which ones a hotspot may
    really use is up to the regulatory domain."""
    top = LAST_2GHZ_CHANNEL if band == "bg" else LAST_5GHZ_CHANNEL
    return [c for c in range(1, top + 1) if NM.utils_wifi_is_channel_valid(c, band)]


def _ip_setting(conn: NM.Connection, key: str) -> NM.SettingIPConfig | None:
    s = conn.get_setting_by_name(key)
    return s if isinstance(s, NM.SettingIPConfig) else None


def _wg_setting(conn: NM.Connection) -> NM.SettingWireGuard | None:
    s = conn.get_setting_by_name(NM.SETTING_WIREGUARD_SETTING_NAME)
    return s if isinstance(s, NM.SettingWireGuard) else None


def _needed[S](setting: S | None, what: str) -> S:
    """A setting the page was built from: the candidate, a clone, has it too."""
    if setting is None:
        raise TypeError(f"the profile has no {what} setting")
    return setting


# --- input widgets (each reports edits through on_change) ---


class Choice[V](Gtk.DropDown):
    """Dropdown over (value, label) pairs; unknown saved values are kept as extra items."""

    def __init__(
        self, options: Sequence[tuple[V, str]], on_change: Callable[[], None]
    ) -> None:
        self._values = [v for v, _ in options]
        self._model = Gtk.StringList.new([t for _, t in options])
        super().__init__(model=self._model)
        self.add_css_class("net-choice")
        self.set_hexpand(True)
        self._on_change = on_change
        _ = self.connect("notify::selected", self._selected)

    def _selected(self, _dd: Gtk.DropDown, _pspec: GObject.ParamSpec) -> None:
        self._on_change()

    def set_options(self, options: Sequence[tuple[V, str]], value: V) -> None:
        """Replace the items, selecting `value` (the first item when it is gone)."""
        self._values = [v for v, _ in options]
        self._model.splice(0, self._model.get_n_items(), [t for _, t in options])
        self.set_selected(self._values.index(value) if value in self._values else 0)

    def set_value(self, value: V, unknown_label: str | None = None) -> None:
        if value not in self._values:
            self._values.append(value)
            self._model.append(unknown_label or str(value))
        self.set_selected(self._values.index(value))

    def value(self) -> V:
        return self._values[self.get_selected()]


def _on_selected(dropdown: Gtk.DropDown, then: Callable[[], None]) -> None:
    """Call `then` whenever the dropdown's selection changes."""

    def selected(_dd: Gtk.DropDown, _pspec: GObject.ParamSpec) -> None:
        then()

    _ = dropdown.connect("notify::selected", selected)


def text_entry(on_change: Callable[[], None], placeholder: str = "") -> Gtk.Entry:
    ent = Gtk.Entry(hexpand=True, placeholder_text=placeholder)
    ent.add_css_class("net-entry")

    def changed(_ent: Gtk.Entry) -> None:
        on_change()

    _ = ent.connect("changed", changed)
    return ent


class Spin(Gtk.SpinButton):
    """Integer spin button that reports edits as they are typed: value-changed
    alone waits for Enter or focus-out, so value() reads the text."""

    def __init__(self, lo: int, hi: int, on_change: Callable[[], None]) -> None:
        super().__init__(
            adjustment=Gtk.Adjustment(
                lower=lo, upper=hi, step_increment=1, page_increment=10
            ),
            numeric=True,
        )
        self.add_css_class("net-spin")
        pass_wheel(self)  # the page scrolls under the pointer
        self._on_change = on_change
        _ = self.connect("value-changed", self._changed)
        _ = self.connect("changed", self._changed)

    def _changed(self, _spin: Gtk.SpinButton) -> None:
        self._on_change()

    def value(self) -> int:
        """The typed number clamped to the range, as a commit would make it."""
        try:
            typed = int(self.get_text().strip())
        except ValueError:
            return int(self.get_value())
        adj = self.get_adjustment()
        return int(min(max(typed, adj.get_lower()), adj.get_upper()))


def toggle(on_change: Callable[[], None]) -> Gtk.Switch:
    sw = Gtk.Switch(valign=Gtk.Align.CENTER)
    sw.add_css_class("net-switch")

    def notified(_sw: Gtk.Switch, _pspec: GObject.ParamSpec) -> None:
        on_change()

    _ = sw.connect("notify::active", notified)
    return sw


class SecretEntry(Gtk.Box):
    """Hidden entry for a stored secret. It stays empty (and the stored value
    untouched) until Show fetches it or the user types a new one."""

    def __init__(
        self, page: EditPage, setting: str, placeholder: str = "Saved (Show to reveal)"
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4, hexpand=True
        )
        self.page, self.setting, self.placeholder = page, setting, placeholder
        self.entry = Gtk.Entry(
            visibility=False,
            hexpand=True,
            placeholder_text=placeholder,
            input_purpose=Gtk.InputPurpose.PASSWORD,
        )
        self.entry.add_css_class("net-entry")
        self._handler = self.entry.connect("changed", self._changed)
        self.append(self.entry)
        self.show_btn = button("Show", on_click=self._toggle)
        self.append(self.show_btn)
        self.loaded = self.edited = False

    def _changed(self, _ent: Gtk.Entry) -> None:
        self.edited = True
        self.page.changed()

    def _toggle(self) -> None:
        if self.entry.get_visibility():
            self.entry.set_visibility(False)
            self.show_btn.set_label("Show")
            return

        def show() -> None:
            self.entry.set_visibility(True)
            self.show_btn.set_label("Hide")

        if self.loaded or self.edited:
            show()
        else:
            self.page.fetch_secrets(self.setting, show)

    def fill(self, value: str | None) -> None:
        """Secrets arrived: show the stored value unless the user already typed one."""
        if not self.edited:
            self.entry.handler_block(self._handler)
            self.entry.set_text(value or "")
            self.entry.handler_unblock(self._handler)
            if not value:
                self.entry.set_placeholder_text("Not stored")
        self.loaded = True

    def value(self) -> str | None:
        """The secret to write, or None to leave the stored one alone."""
        return self.entry.get_text() if self.loaded or self.edited else None


class _EntryRow(Gtk.Box):
    """One RowList row: its entries, then a remove button."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.entries: list[Gtk.Entry] = []


class RowList(Gtk.Box):
    """Rows of entries with remove buttons plus an Add button (addresses, routes)."""

    def __init__(
        self,
        columns: list[tuple[str, int]],  # [(placeholder, width_chars)]
        on_change: Callable[[], None],
        add_label: str = "Add",
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.columns, self.on_change = columns, on_change
        self.rows = vbox(4)
        self.append(self.rows)
        add = button(add_label, on_click=self._add_clicked)
        add.set_halign(Gtk.Align.START)
        self.append(add)

    def _add_clicked(self) -> None:
        _ = self.add_row()
        self.on_change()

    def add_row(
        self, values: Sequence[str] = (), placeholders: Sequence[str] = ()
    ) -> _EntryRow:
        row = _EntryRow()
        for i, (ph, width) in enumerate(self.columns):
            ent = text_entry(
                self.on_change, placeholders[i] if i < len(placeholders) else ph
            )
            ent.set_width_chars(width)
            ent.set_hexpand(i == 0)
            if i < len(values):
                ent.set_text(values[i])
            row.entries.append(ent)
            row.append(ent)

        def remove() -> None:
            self.rows.remove(row)
            self.on_change()

        row.append(glyph_button("\U000f0156", "Remove", remove))  # nf-md-close
        self.rows.append(row)
        return row

    def values(self) -> list[tuple[str, ...]]:
        """Non-empty rows as tuples of stripped strings."""
        out: list[tuple[str, ...]] = []
        child = self.rows.get_first_child()
        while child:
            if isinstance(child, _EntryRow):
                vals = tuple(e.get_text().strip() for e in child.entries)
                if any(vals):
                    out.append(vals)
            child = child.get_next_sibling()
        return out


class EapForm(Gtk.Box):
    """PEAP/TTLS username + password without a CA certificate. Used inline in
    the Wi-Fi list (new network) and on the edit page (saved profile)."""

    def __init__(
        self, on_change: Callable[[], None], password: SecretEntry | None = None
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.on_change = on_change
        self._inner_method: str | None = None
        self.method = Choice(EAP_METHODS, self._method_changed)
        self.inner = Choice(
            [(v, t) for v, t, _ in EAP_INNER["peap"]], on_change
        )  # rebuilt per method
        self.anonymous = text_entry(on_change, "optional")
        self.identity = text_entry(on_change, "username")
        self.password: SecretEntry | Gtk.PasswordEntry
        if password is None:
            entry = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True)
            entry.add_css_class("net-entry")
            _ = entry.connect("changed", self._password_changed)
            self.password = entry
        else:
            self.password = password
        self.ask = Gtk.CheckButton(label="Ask every time")
        _ = self.ask.connect("toggled", self._ask_changed)
        self.domain = text_entry(on_change, "optional, e.g. example.org")
        self.inner_row = field_row("Inner auth", self.inner)
        self.rows: dict[str, FieldRow] = {}
        rows: tuple[tuple[str, str, Gtk.Widget], ...] = (
            ("method", "EAP method", self.method),
            ("anonymous", "Anonymous ID", self.anonymous),
            ("identity", "Identity", self.identity),
            ("password", "Password", self.password),
        )
        for key, name, widget in rows:
            self.rows[key] = field_row(name, widget)
            self.append(self.rows[key])
        self.append(field_row("", self.ask))
        self.append(self.inner_row)
        self.append(field_row("Domain", self.domain))
        warn = label(
            "No CA certificate: the server's identity is not verified",
            "net-form-warning",
        )
        warn.set_wrap(True)
        self.append(warn)
        self._set_inner("peap")

    def _password_changed(self, _ent: Gtk.PasswordEntry) -> None:
        self.on_change()

    def _set_inner(self, method: str, value: str | None = None) -> None:
        if method != self._inner_method:
            new = Choice([(v, t) for v, t, _ in EAP_INNER[method]], self.on_change)
            self.inner_row.replace_widget(self.inner, new)
            self.inner, self._inner_method = new, method
        if value is not None:
            self.inner.set_value(value)

    def _method_changed(self) -> None:
        self._set_inner(self.method.value())
        self.on_change()

    def _ask_changed(self, _btn: Gtk.CheckButton) -> None:
        self._sync_password()
        self.on_change()

    def _sync_password(self) -> None:
        ask = self.ask.get_active()
        self.password.set_sensitive(not ask)
        if isinstance(self.password, SecretEntry):
            self.password.entry.set_placeholder_text(
                "Asked when connecting" if ask else self.password.placeholder
            )

    def set_values(self, v: EapValues) -> None:
        self.method.set_value(v["method"])
        self._set_inner(v["method"], v["inner"])
        self.anonymous.set_text(v["anonymous"])
        self.identity.set_text(v["identity"])
        self.domain.set_text(v["domain"])
        self.ask.set_active(v["ask"])
        self._sync_password()

    def values(self) -> EapValues:
        return {
            "method": self.method.value(),
            "inner": self.inner.value(),
            "identity": self.identity.get_text().strip(),
            "anonymous": self.anonymous.get_text().strip(),
            "domain": self.domain.get_text().strip(),
            "ask": self.ask.get_active(),
        }

    def password_value(self) -> str | None:
        if isinstance(self.password, SecretEntry):
            return self.password.value()
        return self.password.get_text()


class FieldRow(Gtk.Box):
    """Label + widget on one line, an error line under it."""

    def __init__(self, name: str, widget: Gtk.Widget, hint: str | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        line = hbox(8)
        key = label(name, "net-edit-key")
        key.set_width_chars(LABEL_CHARS)
        key.set_valign(
            Gtk.Align.START if isinstance(widget, RowList) else Gtk.Align.CENTER
        )
        line.append(key)
        line.append(widget)
        self.line, self.widget = line, widget
        self.more: More | None = None  # the More part holding this row, if any
        self.append(line)
        self.hint = label(hint or "", "net-edit-hint")
        self.hint.set_wrap(True)
        self.hint.set_visible(bool(hint))
        self.append(self.hint)
        self.error = error_label()
        self.append(self.error)

    def replace_widget(self, old: Gtk.Widget, new: Gtk.Widget) -> None:
        self.line.insert_child_after(new, old)
        self.line.remove(old)
        self.widget = new

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))


def field_row(name: str, widget: Gtk.Widget, hint: str | None = None) -> FieldRow:
    return FieldRow(name, widget, hint)


def edit_section(title: str) -> Gtk.Box:
    box = vbox(6)
    box.add_css_class("net-edit-section")
    box.append(label(title, "net-section"))
    return box


class _MoreContent(Gtk.Box):
    """The rows of a More part."""

    def __init__(self, more: More) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.more = more


class More(Gtk.Box):
    """Collapsed tail of a section for the less common fields. Rows go into
    `content`; it opens by itself when one of them holds a non-default value
    or an error."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-more")
        self.toggle = button("More", "net-more-btn", on_click=self._flip)
        self.toggle.set_halign(Gtk.Align.START)
        self.content = _MoreContent(self)
        self.append(self.toggle)
        self.append(self.content)
        self.set_open(open_=False)

    def _flip(self) -> None:
        self.set_open(open_=not self.is_open())

    def is_open(self) -> bool:
        return self.content.get_visible()

    def set_open(self, *, open_: bool) -> None:
        self.content.set_visible(open_)
        # nf-md-chevron_down / nf-md-chevron_right
        self.toggle.set_label(("\U000f0140" if open_ else "\U000f0142") + " More")


@dataclass(slots=True, frozen=True)
class _IpExtra:
    """An IP section's More part: whether it holds a non-default value, what
    shows for a method, and its applier."""

    nondefault: bool
    sync_visible: Callable[[str], None]
    apply: Applier


# --- the page ---


class EditPage(Gtk.Box):
    def __init__(self, app: EditHost, on_back: Callable[[], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app, self.on_back = app, on_back
        header = hbox(6)
        header.append(
            glyph_button("\U000f004d", "Back", self._cancel)
        )  # nf-md-arrow_left
        self.title = label("", "net-title", hexpand=True, ellipsize=True)
        header.append(self.title)
        self.append(header)
        self.body = vbox(12)
        scroller = VScroller(560)
        scroller.set_child(self.body)
        self.scroller = scroller
        self.append(scroller)
        self.msg = label("", "net-edit-msg")
        self.msg.set_wrap(True)
        self.msg.set_visible(False)
        self.append(self.msg)
        self.apply_bar = hbox(8, "net-inet")
        self.apply_msg = label("", "net-inet-msg", hexpand=True)
        self.apply_msg.set_wrap(True)
        self.apply_bar.append(self.apply_msg)
        self.reconnect_btn = button("Reconnect now", on_click=self._reconnect)
        self.apply_bar.append(self.reconnect_btn)
        self.apply_bar.set_visible(False)
        self.append(self.apply_bar)
        footer = hbox(4)
        footer.add_css_class("net-footer")
        footer.append(Gtk.Box(hexpand=True))
        footer.append(button("Cancel", on_click=self._cancel))
        self.save_btn = button("Save", "net-btn-accent", on_click=self._save)
        footer.append(self.save_btn)
        self.append(footer)
        # the profile being edited; None while closed (the popup also clears it
        # when the profile goes away)
        self.remote: NM.RemoteConnection | None = None
        self.base: NM.Connection = NM.SimpleConnection.new()  # the saved values
        self.active: NM.ActiveConnection | None = None
        self._msg_error = False
        self._fetched: set[str] = set()
        self._secret_fields: list[tuple[str, SecretEntry, SecretGetter]] = []
        self._appliers: list[Applier] = []
        self._rows: dict[str, FieldRow] = {}  # "setting.property" -> FieldRow
        self._peers: list[PeerEditor] = []
        self._peer_box = vbox(8)
        self._pub: tuple[Gtk.Label, FieldRow, SecretEntry] | None = None
        self._pub_for: str | None = None  # private key the shown public key is of
        self._loading = False

    def _client(self) -> NM.Client:
        client = self.app.client
        if client is None:
            raise RuntimeError("the editor opened before NetworkManager answered")
        return client

    # --- open / build ---

    def open(self, remote: NM.RemoteConnection) -> None:
        self.remote = remote
        self.base = NM.SimpleConnection.new_clone(remote)
        self._fetched = set()
        self._secret_fields = []
        self._appliers = []
        self._rows = {}
        self._peers = []
        self._pub = None
        self._loading = True
        while child := self.body.get_first_child():
            self.body.remove(child)
        self.title.set_text(f"Edit {remote.get_id()}")
        self.apply_bar.set_visible(False)
        self._show_msg(None)
        ctype = remote.get_connection_type()
        self.active = next(
            (
                ac
                for ac in self._client().get_active_connections()
                if ac.get_uuid() == remote.get_uuid()
            ),
            None,
        )
        self._build_general(ctype)
        if ctype == "802-11-wireless":
            self._build_wifi()
            self._build_security()
        if ctype in {"802-11-wireless", "802-3-ethernet"}:
            self._build_mac(ctype)
        if ctype == "802-3-ethernet":
            self._build_ethernet()
        if ctype == "wireguard":
            self._build_wireguard()
            self._build_peers()
        for family, key, title in FAMILIES:
            self._build_ip(family, key, title)
        self._build_routes(ctype)
        self._loading = False
        self.scroller.get_vadjustment().set_value(0)
        self.changed()

    def _row(
        self,
        section: Gtk.Box,
        key: str | None,
        name: str,
        widget: Gtk.Widget,
        hint: str | None = None,
    ) -> FieldRow:
        row = field_row(name, widget, hint)
        row.more = section.more if isinstance(section, _MoreContent) else None
        if key:
            self._rows[key] = row
        section.append(row)
        return row

    @staticmethod
    def _more(section: Gtk.Box) -> More:
        more = More()
        section.append(more)
        return more

    def _device(self, cls: type[NM.Device]) -> NM.Device | None:
        """The profile's device: the active one, else the first managed one of `cls`."""
        if self.active and self.active.get_devices():
            return self.active.get_devices()[0]
        iface = self.base.get_setting_connection().get_interface_name()
        for dev in self._client().get_devices():
            if (
                isinstance(dev, cls)
                and dev.get_managed()
                and (not iface or dev.get_iface() == iface)
            ):
                return dev
        return None

    def _build_general(self, ctype: str) -> None:
        s_con = self.base.get_setting_connection()
        sec = edit_section("General")
        name = text_entry(self.changed)
        name.set_text(s_con.get_id())
        _ = self._row(sec, "connection.id", "Name", name)
        vpn = ctype in VPN_TYPES
        auto = toggle(self.changed)
        auto.set_active(s_con.get_autoconnect())
        auto.set_halign(Gtk.Align.START)
        if not vpn:  # VPNs are only ever connected by hand
            _ = self._row(sec, "connection.autoconnect", "Autoconnect", auto)
        prio = Spin(-999, 999, self.changed)
        prio.set_value(s_con.get_autoconnect_priority())
        prio.set_halign(Gtk.Align.START)
        _ = self._row(
            sec,
            "connection.autoconnect-priority",
            "Priority",
            prio,
            None if vpn else "Higher is tried first among autoconnect profiles",
        )
        metered = Choice(METERED, self.changed)
        metered.set_value(shown_metered(s_con))
        _ = self._row(sec, "connection.metered", "Metered", metered)
        # connection.permissions only: secret flags stay as they are, so
        # system-owned secrets stay stored and the save carries none
        more = self._more(sec)
        me = pwd.getpwuid(os.getuid()).pw_name
        perms = list(s_con.props.permissions or [])
        everyone = toggle(self.changed)
        everyone.set_active(not perms)
        everyone.set_halign(Gtk.Align.START)
        users = [p.split(":")[1] for p in perms if p.startswith("user:")]
        hint = (
            f"Now only {', '.join(users) or 'nobody'}, while logged in"
            if perms and users != [me]
            else f"Off: only {me}, and only while logged in"
        )
        _ = self._row(
            more.content,
            "connection.permissions",
            "All users",
            everyone,
            on_reconnect(hint),
        )
        more.set_open(open_=bool(perms))
        self.body.append(sec)
        uuid = s_con.get_uuid()

        def apply(cand: NM.Connection) -> None:
            c = cand.get_setting_connection()
            new = name.get_text().strip()
            if not new:
                raise FieldError("connection.id", "Enter a name")
            if any(
                x.get_id() == new and x.get_uuid() != uuid
                for x in self._client().get_connections()
            ):
                raise FieldError(
                    "connection.id", f"Another profile is already named {new}"
                )
            c.set_property("id", new)
            if not vpn:
                c.set_property("autoconnect", auto.get_active())
            c.set_property("autoconnect-priority", prio.value())
            if metered.value() != shown_metered(c):  # keep guess-yes/-no unless changed
                c.set_property("metered", metered.value())
            if everyone.get_active():
                c.set_property("permissions", [])
            elif not perms:  # a stored user list stays as it is
                c.set_property("permissions", [f"user:{me}:"])

        self._appliers.append(apply)

    def _build_wifi(self) -> None:
        s_wifi = self.base.get_setting_wireless()
        sec = edit_section("Wi-Fi")
        hotspot = is_hotspot(self.base)
        band = Choice(BANDS, self.changed)
        band.set_value(s_wifi.get_band() or None)
        _ = self._row(sec, "802-11-wireless.band", "Band", band, on_reconnect())
        # a client follows the access point's channel
        channel = self._channel_row(sec, band, s_wifi) if hotspot else None
        bssid, custom = self._bssid_row(sec, s_wifi)
        mtu = Spin(0, MAX_MTU, self.changed)
        mtu.set_value(s_wifi.get_mtu())
        mtu.set_halign(Gtk.Align.START)
        _ = self._row(sec, "802-11-wireless.mtu", "MTU", mtu, "0 = automatic")
        more = self._more(sec)
        powersave = Choice(POWERSAVE, self.changed)
        powersave.set_value(int(s_wifi.get_powersave()), "Not managed (kept)")
        _ = self._row(
            more.content,
            "802-11-wireless.powersave",
            "Power saving",
            powersave,
            on_reconnect(
                "Default leaves it to the driver unless NetworkManager.conf sets it"
            ),
        )
        wowl: Choice[int] | None = None
        if not hotspot:
            wowl = Choice(WAKE_ON_WLAN, self.changed)
            wowl.set_value(int(s_wifi.get_wake_on_wlan()), "Custom (kept)")
            _ = self._row(
                more.content,
                "802-11-wireless.wake-on-wlan",
                "Wake on WLAN",
                wowl,
                "Wake from suspend on a packet from the network; not every card can",
            )
        more.set_open(
            open_=powersave.value() != POWERSAVE[0][0]
            or (wowl is not None and wowl.value() != WAKE_ON_WLAN[0][0])
        )
        self.body.append(sec)

        def apply(cand: NM.Connection) -> None:
            w = cand.get_setting_wireless()
            w.set_property("band", band.value())
            value = bssid.value()
            if value == "custom":
                value = custom.get_text().strip()
                problem = mac_problem(value)
                if problem:
                    raise FieldError("802-11-wireless.bssid", problem)
            if (value or None) != ((w.get_bssid() or "").upper() or None):
                w.set_property("bssid", value)
            w.set_property("mtu", mtu.value())
            if channel is not None:
                w.set_property("channel", channel.value())
            w.set_property("powersave", powersave.value())
            if wowl is not None:
                w.set_property("wake-on-wlan", wowl.value())

        self._appliers.append(apply)

    def _channel_row(
        self, sec: Gtk.Box, band: Choice[str | None], s_wifi: NM.SettingWireless
    ) -> Choice[int]:
        """A hotspot's channel, its options following the band."""
        chan: Choice[int] = Choice([(0, "Automatic")], self.changed)
        chan_row = self._row(sec, "802-11-wireless.channel", "Channel", chan)
        stored_band = s_wifi.get_band()

        def sync_channels(keep: int) -> None:
            b = band.value()
            listed = channels(b) if b in {"bg", "a"} else []
            chan.set_options([(0, "Automatic")] + [(c, str(c)) for c in listed], keep)
            if keep and chan.value() != keep and b == stored_band:
                chan.set_value(keep, f"{keep} (kept)")  # e.g. a 6 GHz channel
            chan.set_sensitive(bool(listed) or chan.value() != 0)
            chan_row.hint.set_text(
                on_reconnect(
                    "Only channels your country allows will start"
                    if listed
                    else "Pick a band to choose a channel"
                )
            )
            chan_row.hint.set_visible(True)

        def band_changed() -> None:
            sync_channels(chan.value())

        sync_channels(s_wifi.get_channel())
        _on_selected(band, band_changed)
        return chan

    def _bssid_row(
        self, sec: Gtk.Box, s_wifi: NM.SettingWireless
    ) -> tuple[Choice[str | None], Gtk.Entry]:
        """The BSSID lock: Any, the profile's access points in range, or Other
        (the entry)."""
        ssid = connection_ssid(self.base)
        cur_bssid = (s_wifi.get_bssid() or "").upper() or None
        options: list[tuple[str | None, str]] = [(None, "Any")]
        dev = self._device(NM.DeviceWifi)
        if isinstance(dev, NM.DeviceWifi) and ssid:
            aps = [
                ap
                for ap in dev.get_access_points()
                if ssid_text(nullable(ap.get_ssid())) == ssid
            ]
            aps.sort(key=lambda ap: -ap.get_strength())
            options += [
                (
                    ap.get_bssid().upper(),
                    (
                        f"{ap.get_bssid()} · {ap.get_strength()}% · "
                        f"{freq_band(ap.get_frequency())}"
                    ),
                )
                for ap in aps
            ]
        options.append(("custom", "Other…"))
        bssid = Choice(options, self.changed)
        custom = text_entry(self.changed, "aa:bb:cc:dd:ee:ff")
        box = vbox(4)
        box.set_hexpand(True)
        box.append(bssid)
        box.append(custom)
        if cur_bssid and cur_bssid not in [v for v, _ in options]:
            bssid.set_value(cur_bssid, f"{cur_bssid} (not in range)")
        else:
            bssid.set_value(cur_bssid)
        custom.set_visible(False)

        def bssid_changed() -> None:
            custom.set_visible(bssid.value() == "custom")

        _on_selected(bssid, bssid_changed)
        _ = self._row(
            sec,
            "802-11-wireless.bssid",
            "BSSID lock",
            box,
            on_reconnect("Locking to one access point stops roaming between them"),
        )
        return bssid, custom

    def _build_security(self) -> None:
        s_wsec = nullable(self.base.get_setting_wireless_security())
        s_8021x = nullable(self.base.get_setting_802_1x())
        eap = eap_values(s_8021x)
        sec = edit_section("Security")
        kind = connection_security(self.base)
        km = s_wsec.get_key_mgmt() if s_wsec else None
        _ = self._row(sec, None, "Type", label(kind, "net-edit-value", hexpand=True))
        if km in {"wpa-psk", "sae"}:
            self._build_psk(sec, "psk" if km == "wpa-psk" else "sae")
        elif km == "wpa-eap" and s_8021x is not None and eap is not None:
            self._build_eap(sec, s_8021x, eap)
        elif km:
            # nothing of it is shown, so a save carries none of its secrets and
            # NM keeps the stored ones (see the module docstring)
            hint = label(
                "This security type isn't editable here; it is kept as is.",
                "net-edit-hint",
            )
            hint.set_wrap(True)
            sec.append(hint)
        self.body.append(sec)

    def _build_psk(self, sec: Gtk.Box, check: str) -> None:
        pw = SecretEntry(self, "802-11-wireless-security")
        _ = self._row(sec, "802-11-wireless-security.psk", "Password", pw)

        def stored(c: NM.Connection) -> str | None:
            s = nullable(c.get_setting_wireless_security())
            return s.get_psk() if s else None

        self._secret_fields.append(("802-11-wireless-security", pw, stored))

        def apply(cand: NM.Connection) -> None:
            value = pw.value()
            if value is None:
                return
            problem = password_problem(check, value)
            if problem:
                raise FieldError("802-11-wireless-security.psk", problem)
            cand.get_setting_wireless_security().set_property("psk", value)

        self._appliers.append(apply)

    def _build_eap(
        self, sec: Gtk.Box, s_8021x: NM.Setting8021x, eap: EapValues
    ) -> None:
        pw = SecretEntry(self, "802-1x")
        form = EapForm(self.changed, pw)
        form.set_values(eap)
        sec.append(form)
        self._rows["802-1x.identity"] = form.rows["identity"]

        def stored_password(c: NM.Connection) -> str | None:
            s = nullable(c.get_setting_802_1x())
            return s.get_password() if s else None

        self._secret_fields.append(("802-1x", pw, stored_password))
        stored = s_8021x.get_password_flags() & NM.SettingSecretFlags.NOT_SAVED == 0

        def apply(cand: NM.Connection) -> None:
            values, password = form.values(), form.password_value()
            problem = eap_problem(
                values, password, password_known=stored and password is None
            )
            if problem:
                raise FieldError("802-1x.identity", problem)
            apply_eap(cand.get_setting_802_1x(), values, password)

        self._appliers.append(apply)

    def _build_mac(self, ctype: str) -> None:
        wifi = ctype == "802-11-wireless"
        setting_name = "802-11-wireless" if wifi else "802-3-ethernet"
        setting = self._mac_setting(self.base, setting_name)
        cur = setting.get_cloned_mac_address() if setting else None
        sec = edit_section("MAC address")
        mode = Choice(MAC_MODES, self.changed)
        custom = text_entry(self.changed, "aa:bb:cc:dd:ee:ff")
        box = vbox(4)
        box.set_hexpand(True)
        box.append(mode)
        box.append(custom)
        if cur and cur not in [v for v, _ in MAC_MODES]:
            mode.set_value("custom")
            custom.set_text(cur)
        else:
            mode.set_value(cur)
        custom.set_visible(mode.value() == "custom")

        def mode_changed() -> None:
            custom.set_visible(mode.value() == "custom")

        _on_selected(mode, mode_changed)
        dev = self._device(NM.DeviceWifi if wifi else NM.DeviceEthernet)
        hint = None
        if dev is not None:
            perm = (
                dev.get_permanent_hw_address()
                if isinstance(dev, NM.DeviceWifi | NM.DeviceEthernet)
                else None
            )
            hint = f"Device {dev.get_iface()}: {perm or dev.get_hw_address()}"
            if (
                perm
                and dev.get_hw_address()
                and dev.get_hw_address().upper() != perm.upper()
            ):
                hint += f" (now {dev.get_hw_address()})"
        _ = self._row(
            sec,
            f"{setting_name}.cloned-mac-address",
            "Cloned MAC",
            box,
            on_reconnect(hint),
        )
        self.body.append(sec)

        def apply(cand: NM.Connection) -> None:
            value = mode.value()
            if value == "custom":
                value = custom.get_text().strip()
                problem = mac_problem(value)
                if problem:
                    raise FieldError(f"{setting_name}.cloned-mac-address", problem)
            s = self._mac_setting(cand, setting_name)
            if s is None:
                if value is None:
                    return
                s = NM.SettingWireless.new() if wifi else NM.SettingWired.new()
                cand.add_setting(s)
            if (value or None) != s.get_cloned_mac_address():
                s.set_property("cloned-mac-address", value)

        self._appliers.append(apply)

    @staticmethod
    def _mac_setting(
        conn: NM.Connection, setting_name: str
    ) -> NM.SettingWireless | NM.SettingWired | None:
        s = conn.get_setting_by_name(setting_name)
        return s if isinstance(s, NM.SettingWireless | NM.SettingWired) else None

    def _build_ethernet(self) -> None:
        s_wired = nullable(self.base.get_setting_wired())
        flags = int(s_wired.get_wake_on_lan()) if s_wired else int(WOL.DEFAULT)
        sec = edit_section("Ethernet")
        wol = toggle(self.changed)
        wol.set_active(bool(flags & WOL.MAGIC))
        wol.set_halign(Gtk.Align.START)
        other = flags & ~(WOL.MAGIC | WOL.DEFAULT | WOL.IGNORE)
        hint = "Off: the system default" + (
            " (other wake flags stay as set)" if other else ""
        )
        _ = self._row(sec, "802-3-ethernet.wake-on-lan", "Wake on LAN", wol, hint)
        more = self._more(sec)
        mtu = Spin(0, MAX_MTU, self.changed)
        mtu.set_value(s_wired.get_mtu() if s_wired else 0)
        mtu.set_halign(Gtk.Align.START)
        _ = self._row(more.content, "802-3-ethernet.mtu", "MTU", mtu, "0 = automatic")
        # A fixed mode keeps auto-negotiation on, advertising only that mode:
        # forcing it without negotiation drops gigabit links. A stored forced
        # mode is kept as it is until another one is picked.
        speed = s_wired.get_speed() if s_wired else 0
        duplex = nullable(s_wired.get_duplex()) if s_wired else None
        forced = (
            s_wired is not None
            and not s_wired.get_auto_negotiate()
            and bool(speed or duplex)
        )
        stored_mode: LinkMode = (
            None if not (speed or duplex) else "kept" if forced else (speed, duplex)
        )
        link = Choice(LINK_MODES, self.changed)
        link.set_value(
            stored_mode,
            f"{speed or '?'} Mb/s, {duplex or '?'} duplex, "
            f"{'forced' if forced else 'negotiated'} (kept)",
        )
        _ = self._row(
            more.content,
            "802-3-ethernet.speed",
            "Link speed",
            link,
            "Forced without negotiation; another choice turns negotiation back on"
            if forced
            else "A fixed speed is still negotiated: only that mode is offered",
        )
        more.set_open(open_=mtu.value() != 0 or stored_mode is not None)
        self.body.append(sec)

        def apply(cand: NM.Connection) -> None:
            on = wol.get_active()
            s = nullable(cand.get_setting_wired())
            flags = int(s.get_wake_on_lan()) if s else int(WOL.DEFAULT)
            if on == bool(flags & WOL.MAGIC):
                return  # leave the flags exactly as stored
            if s is None:
                s = NM.SettingWired.new()
                cand.add_setting(s)
            new = (
                (flags & ~(WOL.DEFAULT | WOL.IGNORE)) | WOL.MAGIC
                if on
                else flags & ~WOL.MAGIC
            )
            s.set_property("wake-on-lan", int(new) or int(WOL.DEFAULT))

        self._appliers.append(apply)

        def apply_link(cand: NM.Connection) -> None:
            s = nullable(cand.get_setting_wired())
            mode = link.value()
            if s is None and not mtu.value() and mode is None:
                return
            if s is None:
                s = NM.SettingWired.new()
                cand.add_setting(s)
            s.set_property("mtu", mtu.value())
            if mode in {stored_mode, "kept"}:
                return  # leave speed, duplex and auto-negotiate exactly as stored
            new_speed, new_duplex = mode or (0, None)
            s.set_property("speed", new_speed)
            s.set_property("duplex", new_duplex)
            s.props.auto_negotiate = True  # never false: see above

        self._appliers.append(apply_link)

    def _runtime(self, key: str) -> NM.IPConfig | None:
        """Active connection's IP config for placeholders, or None."""
        if not self.active:
            return None
        return nullable(
            self.active.get_ip4_config()
            if key == "ipv4"
            else self.active.get_ip6_config()
        )

    def _build_ip(self, family: int, key: str, title: str) -> None:
        s_ip = _ip_setting(self.base, key)
        if s_ip is None:
            return
        rt = self._runtime(key)
        sec = edit_section(title)
        method = Choice(IP_METHODS[key], self.changed)
        method.set_value(s_ip.get_method())
        _ = self._row(sec, f"{key}.method", "Method", method)
        addrs = RowList([("address/prefix", 20)], self.changed, "Add address")
        orig_addrs = [s_ip.get_address(i) for i in range(s_ip.get_num_addresses())]
        for a in orig_addrs:
            _ = addrs.add_row((f"{a.get_address()}/{a.get_prefix()}",))
        rt_addrs = (
            [f"{a.get_address()}/{a.get_prefix()}" for a in rt.get_addresses()]
            if rt
            else []
        )
        if not orig_addrs and rt_addrs:
            _ = addrs.add_row((), (rt_addrs[0],))
        addr_row = self._row(sec, f"{key}.addresses", "Addresses", addrs)
        gw = text_entry(self.changed, (rt.get_gateway() or "") if rt else "")
        gw.set_text(s_ip.get_gateway() or "")
        gw_row = self._row(sec, f"{key}.gateway", "Gateway", gw)
        rt_dns = ", ".join(rt.get_nameservers() or []) if rt else ""
        dns = text_entry(self.changed, rt_dns or "comma-separated")
        dns.set_text(", ".join(s_ip.get_dns(i) for i in range(s_ip.get_num_dns())))
        dns_row = self._row(sec, f"{key}.dns", "DNS servers", dns)
        ignore_dns = toggle(self.changed)
        ignore_dns.set_active(s_ip.get_ignore_auto_dns())
        ignore_dns.set_halign(Gtk.Align.START)
        ign_row = self._row(
            sec, f"{key}.ignore-auto-dns", "Ignore auto DNS", ignore_dns
        )
        rt_dom = ", ".join(rt.get_domains() or []) if rt else ""
        search = text_entry(self.changed, rt_dom or "comma-separated")
        search.set_text(
            ", ".join(
                s_ip.get_dns_search(i) for i in range(s_ip.get_num_dns_searches())
            )
        )
        search_row = self._row(sec, f"{key}.dns-search", "Search domains", search)
        more = self._more(sec)
        extra = self._ip_extra(more.content, key, title, s_ip)
        more.set_open(open_=extra.nondefault)
        self.body.append(sec)

        def sync_visible() -> None:
            m = method.value()
            off = m in {"disabled", "ignore"}
            manual = m == "manual"
            addr_row.set_visible(manual or (not off and bool(addrs.values())))
            gw_row.set_visible(manual)
            for row in (dns_row, ign_row, search_row):
                row.set_visible(not off)
            more.set_visible(not off)
            extra.sync_visible(m)

        sync_visible()
        _on_selected(method, sync_visible)

        self._appliers.append(
            _IpApplier(
                family,
                key,
                title,
                method,
                addrs,
                orig_addrs,
                gw,
                dns,
                ignore_dns,
                search,
            ).apply
        )
        self._appliers.append(extra.apply)

    def _ip_extra(
        self, box: Gtk.Box, key: str, title: str, s_ip: NM.SettingIPConfig
    ) -> _IpExtra:
        """The More part of an IP section: required, DHCP, privacy, DNS priority, table."""
        require = toggle(self.changed)
        require.set_active(not s_ip.get_may_fail())
        require.set_halign(Gtk.Align.START)
        _ = self._row(
            box,
            f"{key}.may-fail",
            f"Require {title}",
            require,
            f"Off: the connection comes up without {title} when it gets none",
        )
        # NM 1.52 made this a ternary; "default" falls back to NetworkManager.conf,
        # then to the deprecated boolean, which must match any explicit value
        stored_send = s_ip.props.dhcp_send_hostname_v2
        old_no = stored_send == -1 and not s_ip.props.dhcp_send_hostname
        send: Choice[int] = Choice(
            [(-1, f"Default ({'no' if old_no else 'yes'})"), (1, "Yes"), (0, "No")],
            self.changed,
        )
        send.set_value(stored_send)
        send_row = self._row(
            box,
            f"{key}.dhcp-send-hostname",
            "Send hostname",
            send,
            "Some DHCP servers put it in local DNS",
        )
        hostname = text_entry(self.changed, socket.gethostname())
        hostname.set_text(s_ip.get_dhcp_hostname() or "")
        host_row = self._row(
            box,
            f"{key}.dhcp-hostname",
            "DHCP hostname",
            hostname,
            "Empty: this computer's hostname",
        )
        client_id: Choice[str | None] | None = None
        custom_id = text_entry(self.changed, "01:aa:bb:cc:dd:ee:ff")
        cid_row: FieldRow | None = None
        privacy: Choice[int] | None = None
        privacy_row: FieldRow | None = None
        stored_cid = (
            nullable(s_ip.get_dhcp_client_id())
            if isinstance(s_ip, NM.SettingIP4Config)
            else None
        )
        if isinstance(s_ip, NM.SettingIP4Config):
            client_id, cid_row = self._client_id_row(box, key, stored_cid, custom_id)
        elif isinstance(s_ip, NM.SettingIP6Config):
            privacy = Choice(IP6_PRIVACY, self.changed)
            privacy.set_value(int(s_ip.get_ip6_privacy()))
            privacy_row = self._row(
                box,
                f"{key}.ip6-privacy",
                "IPv6 privacy",
                privacy,
                "Temporary addresses for outgoing connections (SLAAC)",
            )
        dns_prio = Spin(*DNS_PRIORITY_RANGE, self.changed)
        dns_prio.set_value(s_ip.get_dns_priority())
        dns_prio.set_halign(Gtk.Align.START)
        _ = self._row(
            box,
            f"{key}.dns-priority",
            "DNS priority",
            dns_prio,
            "Lower wins; 0 = default (100, VPNs 50). Negative, with systemd-resolved here: "
            "while it is up, lookups in its search domains go only to its DNS servers, "
            "and all lookups do if it has the default route",
        )
        table = Spin(*ROUTE_TABLE_RANGE, self.changed)
        table.set_value(s_ip.get_route_table())
        table.set_halign(Gtk.Align.START)
        _ = self._row(
            box,
            f"{key}.route-table",
            "Route table",
            table,
            "0 = main. Another table turns on policy routing: its routes go there",
        )
        nondefault = bool(
            not s_ip.get_may_fail()
            or stored_send != -1
            or s_ip.get_dhcp_hostname()
            or stored_cid
            or (privacy is not None and privacy.value() != -1)
            or s_ip.get_dns_priority()
            or s_ip.get_route_table()
        )

        def sync_visible(method: str) -> None:
            dhcp = method in (("auto",) if key == "ipv4" else ("auto", "dhcp"))
            send_row.set_visible(dhcp)
            host_row.set_visible(dhcp and send.value() != 0)
            if cid_row:
                cid_row.set_visible(dhcp)
            if privacy_row:
                privacy_row.set_visible(method == "auto")

        def send_changed() -> None:
            host_row.set_visible(send_row.get_visible() and send.value() != 0)

        _on_selected(send, send_changed)

        applier = _IpExtraApplier(
            key,
            require,
            send,
            stored_send,
            hostname,
            client_id,
            custom_id,
            stored_cid,
            privacy,
            dns_prio,
            table,
        )
        return _IpExtra(nondefault, sync_visible, applier.apply)

    def _client_id_row(
        self, box: Gtk.Box, key: str, stored_cid: str | None, custom_id: Gtk.Entry
    ) -> tuple[Choice[str | None], FieldRow]:
        """DHCPv4 client ID: a mode, or Custom with the ID in `custom_id`."""
        cid = Choice(CLIENT_IDS, self.changed)
        special = [v for v, _ in CLIENT_IDS if v not in {None, "custom"}]
        if stored_cid in {"ipv6-duid", "none"}:
            cid.set_value(stored_cid, f"{stored_cid} (kept)")
        elif stored_cid and stored_cid not in special:
            cid.set_value("custom")
            custom_id.set_text(stored_cid)
        else:
            cid.set_value(stored_cid)
        cid_box = vbox(4)
        cid_box.set_hexpand(True)
        cid_box.append(cid)
        cid_box.append(custom_id)
        custom_id.set_visible(cid.value() == "custom")

        def cid_changed() -> None:
            custom_id.set_visible(cid.value() == "custom")

        _on_selected(cid, cid_changed)
        row = self._row(
            box,
            f"{key}.dhcp-client-id",
            "DHCP client ID",
            cid_box,
            "What the DHCP server keys the lease on",
        )
        return cid, row

    def _build_routes(self, ctype: str) -> None:
        sec = edit_section("Routes")
        if ctype == "wireguard":
            note = label(
                "Peer Allowed IPs are the main way to choose what goes through the "
                "tunnel; routes here are extra.",
                "net-edit-hint",
            )
            note.set_wrap(True)
            sec.append(note)
        any_family = False
        for family, key, title in FAMILIES:
            s_ip = _ip_setting(self.base, key)
            if s_ip is None:
                continue
            any_family = True
            orig = [s_ip.get_route(i) for i in range(s_ip.get_num_routes())]
            routes = RowList(
                [("destination/prefix", 18), ("next hop", 12), ("metric", 6)],
                self.changed,
                "Add route",
            )
            for r in orig:
                _ = routes.add_row(
                    (
                        f"{r.get_dest()}/{r.get_prefix()}",
                        r.get_next_hop() or "",
                        str(r.get_metric()) if r.get_metric() >= 0 else "",
                    )
                )
            _ = self._row(sec, f"{key}.routes", f"{title} routes", routes)
            ign = toggle(self.changed)
            ign.set_active(s_ip.get_ignore_auto_routes())
            ign.set_halign(Gtk.Align.START)
            _ = self._row(sec, f"{key}.ignore-auto-routes", "Ignore auto routes", ign)
            never = toggle(self.changed)
            never.set_active(s_ip.get_never_default())
            never.set_halign(Gtk.Align.START)
            _ = self._row(
                sec,
                f"{key}.never-default",
                "Only its network",
                never,
                f"Use {title} only for resources on this connection's network (never-default)",
            )
            self._appliers.append(
                _RoutesApplier(family, key, routes, orig, ign, never).apply
            )
        if any_family:
            self.body.append(sec)

    def _build_wireguard(self) -> None:
        s_wg = _needed(_wg_setting(self.base), "wireguard")
        sec = edit_section("WireGuard")
        key = SecretEntry(self, "wireguard")
        _ = self._row(sec, "wireguard.private-key", "Private key", key)

        def stored_key(c: NM.Connection) -> str | None:
            s = _wg_setting(c)
            return s.get_private_key() if s else None

        self._secret_fields.append(("wireguard", key, stored_key))
        pub = label("", "net-edit-value", hexpand=True, ellipsize=True)
        pub.set_selectable(True)
        pub_row = self._row(sec, None, "Public key", pub)
        dev = (
            self.active.get_devices()[0]
            if self.active and self.active.get_devices()
            else None
        )
        pub_row.set_visible(False)
        if isinstance(dev, NM.DeviceWireGuard) and dev.get_public_key():
            data = dev.get_public_key().get_data() or b""
            pub.set_text(base64.b64encode(bytes(data)).decode())
            pub_row.set_visible(True)
        self._pub = (pub, pub_row, key)
        self._pub_for = None
        port = Spin(0, MAX_PORT, self.changed)
        port.set_value(s_wg.get_listen_port())
        port.set_halign(Gtk.Align.START)
        _ = self._row(sec, "wireguard.listen-port", "Listen port", port, "0 = random")
        fwmark = text_entry(self.changed, "0 = off")
        fwmark.set_text(f"{s_wg.get_fwmark():#x}" if s_wg.get_fwmark() else "")
        _ = self._row(sec, "wireguard.fwmark", "Firewall mark", fwmark)
        mtu = Spin(0, MAX_MTU, self.changed)
        mtu.set_value(s_wg.get_mtu())
        mtu.set_halign(Gtk.Align.START)
        _ = self._row(sec, "wireguard.mtu", "MTU", mtu, "0 = automatic")
        peer_routes = toggle(self.changed)
        peer_routes.set_active(s_wg.get_peer_routes())
        peer_routes.set_halign(Gtk.Align.START)
        _ = self._row(
            sec,
            "wireguard.peer-routes",
            "Peer routes",
            peer_routes,
            "Add routes for the peers' Allowed IPs",
        )
        self.body.append(sec)

        self._appliers.append(
            _WireGuardApplier(key, port, fwmark, mtu, peer_routes).apply
        )

    def _update_public_key(self) -> None:
        """Public key from the private key via `wg pubkey` (shown only when wg exists)."""
        if self._pub is None:
            return
        pub, row, key = self._pub
        value = key.value()
        if (
            not value
            or value == self._pub_for
            or wg_key_problem(value)
            or not shutil.which("wg")
        ):
            return
        self._pub_for = value
        try:
            out = subprocess.run(
                ["wg", "pubkey"],
                input=value,
                capture_output=True,
                text=True,
                timeout=WG_PUBKEY_TIMEOUT_S,
                check=True,
            ).stdout.strip()
        except OSError, subprocess.SubprocessError:
            return
        pub.set_text(out)
        row.set_visible(bool(out))

    def _build_peers(self) -> None:
        s_wg = _needed(_wg_setting(self.base), "wireguard")
        sec = edit_section("Peers")
        self._peer_box = vbox(8)
        sec.append(self._peer_box)
        add = button("Add peer", on_click=self._add_new_peer)
        add.set_halign(Gtk.Align.START)
        sec.append(add)
        _ = self._row(sec, "wireguard.peers", "", Gtk.Box())
        for i in range(s_wg.get_peers_len()):
            self._add_peer(s_wg.get_peer(i))
        self.body.append(sec)

        def apply(cand: NM.Connection) -> None:
            s = _needed(_wg_setting(cand), "wireguard")
            peers = [p.build() for p in self._peers]
            s.clear_peers()
            for peer in peers:
                s.append_peer(peer)

        self._appliers.append(apply)

    def _add_new_peer(self) -> None:
        self._add_peer(None)
        self.changed()

    def _add_peer(self, peer: NM.WireGuardPeer | None) -> None:
        editor = PeerEditor(self, peer)
        self._peers.append(editor)
        self._peer_box.append(editor)
        if peer is not None:
            self._secret_fields.append(("wireguard", editor.psk, editor.stored_psk))

    def _rebase_peers(self) -> None:
        """Point each peer editor at its saved peer (the candidate lists them in
        editor order), so stored-PSK lookups use the saved public key."""
        s_wg = _wg_setting(self.base)
        if s_wg is None:
            return
        for i, editor in enumerate(self._peers):
            if editor.peer is None:  # a new peer is now stored
                self._secret_fields.append(("wireguard", editor.psk, editor.stored_psk))
            editor.peer = s_wg.get_peer(i)

    def remove_peer(self, editor: PeerEditor) -> None:
        self._peers.remove(editor)
        self._peer_box.remove(editor)
        self._secret_fields = [f for f in self._secret_fields if f[1] is not editor.psk]
        self.changed()

    # --- secrets ---

    def fetch_secrets(
        self,
        setting: str,
        then: Callable[[], None],
        on_error: Callable[[str, GLib.Error], None] | None = None,
    ) -> None:
        if setting in self._fetched:
            then()
            return
        remote = self.remote
        if remote is None:
            return

        def done(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                secrets = nullable(rc.get_secrets_finish(res))
            except GLib.Error as e:
                self._show_msg(f"Cannot read the secrets: {error_text(e)}", error=True)
                if on_error:
                    on_error(setting, e)
                return
            if rc is not self.remote:
                return  # the page moved on
            if secrets is not None:
                _ = self.base.update_secrets(setting, secrets)
            self._fetched.add(setting)
            for name, entry, getter in self._secret_fields:
                if name == setting:
                    entry.fill(getter(self.base))
            self.changed()
            then()

        remote.get_secrets_async(setting, None, done)

    # --- candidate, validation, save ---

    def candidate(self) -> tuple[NM.Connection, list[tuple[str | None, str]]]:
        """(connection built from the fields, [(key, message)])."""
        cand = NM.SimpleConnection.new_clone(self.base)
        errors: list[tuple[str | None, str]] = []
        for apply in self._appliers:
            try:
                apply(cand)
            except FieldError as e:
                errors.append((e.key, str(e)))
        if not errors:
            try:
                _ = cand.verify()
            except GLib.Error as e:
                key, _, text = e.message.partition(": ")
                errors.append((key, text) if key in self._rows else (None, e.message))
        return cand, errors

    def changed(self) -> None:
        remote = self.remote
        if self._loading or remote is None:
            return
        cand, errors = self.candidate()
        for row in self._rows.values():
            row.show_error(None)
        loose = [msg for key, msg in errors if key is None or key not in self._rows]
        for key, msg in errors:
            row = self._rows.get(key) if key is not None else None
            if row is not None:
                row.show_error(msg)
                if row.more:
                    row.more.set_open(open_=True)
        if loose:
            self._show_msg("; ".join(loose), error=True)
        elif self._msg_error:
            self._show_msg(None)  # clear only errors; keep "Saved" and the like
        dirty = not cand.compare(self.base, NM.SettingCompareFlags.EXACT)
        self.save_btn.set_sensitive(dirty and not errors)
        if remote.get_connection_type() == "wireguard":
            self._update_public_key()

    def _show_msg(
        self, text: str | None, *, error: bool = False, ok: bool = False
    ) -> None:
        self._msg_error = bool(text) and error
        self.msg.set_text(text or "")
        self.msg.set_visible(bool(text))
        self.msg.set_css_classes(
            ["net-edit-msg"]
            + (["net-status-err"] if error else [])
            + (["net-status-ok"] if ok else [])
        )
        _ = copyable(self.msg, on=error)

    @staticmethod
    def _peer_keys(conn: NM.Connection) -> set[str]:
        s_wg = _wg_setting(conn)
        return (
            {s_wg.get_peer(i).get_public_key() for i in range(s_wg.get_peers_len())}
            if s_wg
            else set()
        )

    def _missing_secrets(self, cand: NM.Connection) -> list[str]:
        """Settings whose stored secrets must be fetched before `cand` can be
        sent: none if it carries no secret and keeps the same peers."""
        # a{sa{sv}}: each setting's secrets, empty when it carries none
        secrets = cand.to_dbus(NM.ConnectionSerializationFlags.ONLY_SECRETS)
        carried = any(
            secrets.get_child_value(i).get_child_value(1).n_children()
            for i in range(secrets.n_children())
        )
        if not carried and self._peer_keys(cand) == self._peer_keys(self.base):
            return []
        return [
            name
            for name in SECRET_SETTINGS
            if nullable(self.base.get_setting_by_name(name)) is not None
            and name not in self._fetched
        ]

    def _save(self) -> None:
        remote = self.remote
        if remote is None:
            return
        cand, errors = self.candidate()
        if errors:
            self.changed()
            return
        missing = self._missing_secrets(cand)
        if missing:
            self.save_btn.set_sensitive(False)
            self._show_msg("Reading the stored secrets…")
            # fetched secrets land in the baseline; user edits in the fields win
            self.fetch_secrets(missing[0], self._save, on_error=self._save_unreadable)
            return
        name = cand.get_id()
        self.save_btn.set_sensitive(False)
        self.apply_bar.set_visible(False)
        self._show_msg(f"Saving {name}…")

        def done(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                _ = rc.update2_finish(res)
            except GLib.Error as e:
                self._show_msg(f"Not saved: {error_text(e)}", error=True)
                self.changed()
                return
            if rc is not self.remote:
                return
            self.base = cand
            self._rebase_peers()
            self.title.set_text(f"Edit {name}")
            self.active = next(
                (
                    ac
                    for ac in self._client().get_active_connections()
                    if ac.get_uuid() == rc.get_uuid()
                ),
                None,
            )
            devs = self.active.get_devices() if self.active else []
            if devs:
                self._reapply(devs[0], name)
            else:
                self._show_msg(f"Saved {name}", ok=True)
            self.changed()
            self.app.queue_sync()

        remote.update2(
            cand.to_dbus(NM.ConnectionSerializationFlags.ALL),
            NM.SettingsUpdate2Flags.TO_DISK,
            None,
            None,
            done,
        )

    def _save_unreadable(self, setting: str, err: GLib.Error) -> None:
        """NM answers "no agents" when a required secret is already missing (it
        asks agents instead of returning a partial set): nothing complete is
        stored to lose, so save with what the fields hold. Other errors stop."""
        if err.domain != GLib.quark_to_string(NM.AgentManagerError.quark()):
            self.changed()
            return
        self._fetched.add(setting)
        self._save()

    def _reapply(self, dev: NM.Device, name: str) -> None:
        """Apply the saved profile to the connected device without a disconnect.
        NM refuses changes it cannot make live (SSID, security, band, channel,
        BSSID, power saving, MAC, user permissions, some MTUs): those wait for
        the user's Reconnect now, since a reconnect drops open sessions. Their
        fields say so (ON_RECONNECT)."""
        remote = self.remote
        self._show_msg(f"Saved {name}; applying…")

        def reapplied(d: NM.Device, res: Gio.AsyncResult) -> None:
            try:
                _ = d.reapply_finish(res)
            except GLib.Error as e:
                if remote is not self.remote:
                    return
                self._show_msg(None)
                self.apply_msg.set_text(
                    f"Saved. Takes effect after reconnecting "
                    f"({reapply_refusal_text(e)})"
                )
                _ = copyable(self.apply_msg)
                self.reconnect_btn.set_visible(True)
                self.apply_bar.set_visible(True)
                return
            if remote is self.remote:
                self._show_msg(f"Saved and applied to {name}", ok=True)
            self.app.queue_sync()

        # None: the saved profile, secrets included
        dev.reapply_async(None, 0, 0, None, reapplied)

    def _reconnect(self) -> None:
        ac, remote = self.active, self.remote
        devs = ac.get_devices() if ac else []
        if not devs or remote is None:
            return
        dev, name = devs[0], remote.get_id()
        self.reconnect_btn.set_visible(False)
        self.apply_msg.set_text(f"Reconnecting {name}…")
        _ = copyable(self.apply_msg, on=False)

        def reconnected(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                _ = c.activate_connection_finish(res)
            except GLib.Error as e:
                self.apply_msg.set_text(f"Reconnecting {name} failed: {error_text(e)}")
                _ = copyable(self.apply_msg)
                return
            self.apply_msg.set_text(f"Reconnected {name}: the changes are applied")
            self.app.queue_sync()

        self._client().activate_connection_async(remote, dev, None, None, reconnected)

    def _cancel(self) -> None:
        self.remote = None
        self.base = NM.SimpleConnection.new()
        self.on_back()


@dataclass(slots=True, frozen=True)
class _IpApplier:
    """Writes an IP section's method, addresses, gateway and DNS."""

    family: int
    key: str
    title: str
    method: Choice[str]
    addrs: RowList
    orig_addrs: list[NM.IPAddress]
    gw: Gtk.Entry
    dns: Gtk.Entry
    ignore_dns: Gtk.Switch
    search: Gtk.Entry

    def apply(self, cand: NM.Connection) -> None:
        key, family = self.key, self.family
        s = _needed(_ip_setting(cand, key), key)
        s.set_property("method", self.method.value())
        parsed: list[tuple[str, int]] = []
        for (text,) in self.addrs.values():
            try:
                parsed.append(parse_cidr(text, family))
            except ValueError as e:
                raise FieldError(f"{key}.addresses", str(e)) from None
        # keep the stored address objects (and any attributes) for unchanged rows
        s.clear_addresses()
        for addr, prefix in parsed:
            same = next(
                (
                    a
                    for a in self.orig_addrs
                    if a.get_address() == addr and a.get_prefix() == prefix
                ),
                None,
            )
            _ = s.add_address(same or NM.IPAddress.new(family, addr, prefix))
        gateway = self.gw.get_text().strip()
        if gateway:
            try:
                _ = parse_ip(gateway, family)
            except ValueError as e:
                raise FieldError(f"{key}.gateway", str(e)) from None
        s.set_property("gateway", gateway or None)
        servers = split_list(self.dns.get_text())
        for server in servers:
            if not NM.utils_ipaddr_valid(family, server.split("#")[0]):
                raise FieldError(f"{key}.dns", f"{server}: not an {self.title} address")
        if servers != [s.get_dns(i) for i in range(s.get_num_dns())]:
            s.clear_dns()
            for server in servers:
                _ = s.add_dns(server)
        s.set_property("ignore-auto-dns", self.ignore_dns.get_active())
        domains = split_list(self.search.get_text())
        s.clear_dns_searches()
        for d in domains:
            _ = s.add_dns_search(d)


@dataclass(slots=True, frozen=True)
class _IpExtraApplier:
    """Writes the fields of an IP section's More part."""

    key: str
    require: Gtk.Switch
    send: Choice[int]
    stored_send: int
    hostname: Gtk.Entry
    client_id: Choice[str | None] | None  # IPv4 only
    custom_id: Gtk.Entry
    stored_cid: str | None
    privacy: Choice[int] | None  # IPv6 only
    dns_prio: Spin
    table: Spin

    def apply(self, cand: NM.Connection) -> None:
        key = self.key
        s = _needed(_ip_setting(cand, key), key)
        s.set_property("may-fail", not self.require.get_active())
        send = self.send.value()
        if send != self.stored_send:
            s.set_property("dhcp-send-hostname-v2", send)
            s.set_property("dhcp-send-hostname", send != 0)
        s.set_property("dhcp-hostname", self.hostname.get_text().strip() or None)
        if self.client_id is not None:
            value = self.client_id.value()
            if value == "custom":
                value = self.custom_id.get_text().strip()
                if not value:
                    raise FieldError(f"{key}.dhcp-client-id", "Enter the client ID")
                if value != self.stored_cid and not HEX_ID.fullmatch(value):
                    raise FieldError(
                        f"{key}.dhcp-client-id",
                        "Hex bytes, e.g. 01:aa:bb:cc:dd:ee:ff (01 = Ethernet MAC)",
                    )
            s.set_property("dhcp-client-id", value)
        if self.privacy is not None:
            s.set_property("ip6-privacy", self.privacy.value())
        s.set_property("dns-priority", self.dns_prio.value())
        s.set_property("route-table", self.table.value())


@dataclass(slots=True, frozen=True)
class _WireGuardApplier:
    """Writes the WireGuard section: private key, port, mark, MTU, peer routes."""

    key: SecretEntry
    port: Spin
    fwmark: Gtk.Entry
    mtu: Spin
    peer_routes: Gtk.Switch

    def apply(self, cand: NM.Connection) -> None:
        s = _needed(_wg_setting(cand), "wireguard")
        value = self.key.value()
        if value is not None:
            problem = (
                wg_key_problem(value, "Private key")
                if value
                else "Enter the private key"
            )
            if problem:
                raise FieldError("wireguard.private-key", problem)
            s.set_property("private-key", value)
        s.set_property("listen-port", self.port.value())
        text = self.fwmark.get_text().strip() or "0"
        try:
            mark = int(text, 0)
        except ValueError:
            raise FieldError(
                "wireguard.fwmark", "A number (decimal or 0x hex)"
            ) from None
        if not 0 <= mark <= MAX_FWMARK:
            raise FieldError("wireguard.fwmark", "At most 0xffffffff")
        s.set_property("fwmark", mark)
        s.set_property("mtu", self.mtu.value())
        s.set_property("peer-routes", self.peer_routes.get_active())


@dataclass(slots=True, frozen=True)
class _RoutesApplier:
    """Writes one family's routes, ignore-auto-routes and never-default."""

    family: int
    key: str
    routes: RowList
    orig: list[NM.IPRoute]
    ign: Gtk.Switch
    never: Gtk.Switch

    def apply(self, cand: NM.Connection) -> None:
        s = _needed(_ip_setting(cand, self.key), self.key)
        host_bits = IPV4_BITS if self.family == socket.AF_INET else IPV6_BITS
        new: list[NM.IPRoute] = []
        for dest, hop_text, metric in self.routes.values():
            try:
                addr, prefix = parse_cidr(dest, self.family, host_bits)
                hop = parse_ip(hop_text, self.family) if hop_text else None
            except ValueError as e:
                raise FieldError(f"{self.key}.routes", str(e)) from None
            if metric and not metric.isdigit():
                raise FieldError(
                    f"{self.key}.routes", f"{metric}: metric must be a number"
                )
            m = int(metric) if metric else -1
            same = next(
                (
                    r
                    for r in self.orig
                    if r.get_dest() == addr
                    and r.get_prefix() == prefix
                    and (r.get_next_hop() or None) == hop
                    and r.get_metric() == m
                ),
                None,
            )
            new.append(same or NM.IPRoute.new(self.family, addr, prefix, hop, m))
        s.clear_routes()
        for r in new:
            _ = s.add_route(r)
        s.set_property("ignore-auto-routes", self.ign.get_active())
        s.set_property("never-default", self.never.get_active())


class PeerEditor(Gtk.Box):
    """One WireGuard peer. NM.WireGuardPeer is immutable once sealed, so
    build() clones the stored peer (keeping fields not shown) and reseals it."""

    def __init__(self, page: EditPage, peer: NM.WireGuardPeer | None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("net-row")
        self.page, self.peer = page, peer
        ch = page.changed
        head = hbox(6)
        head.append(
            label("Peer" if peer else "New peer", "net-row-title", hexpand=True)
        )
        head.append(
            glyph_button(
                "\U000f0a7a",  # nf-md-trash_can_outline
                "Remove peer",
                self._remove,
                "net-delete-btn",
            )
        )
        self.append(head)
        self.pubkey = text_entry(ch, "base64 public key")
        self.endpoint = text_entry(ch, "host:port")
        self.allowed = text_entry(ch, "e.g. 0.0.0.0/0, ::/0")
        self.psk = SecretEntry(
            page, "wireguard", "Saved (Show to reveal)" if peer else "optional"
        )
        if peer is None:
            self.psk.loaded = True  # nothing stored to fetch
        self.keepalive = Spin(0, MAX_PORT, ch)
        self.keepalive.set_halign(Gtk.Align.START)
        self.rows: dict[str, FieldRow] = {}
        rows: tuple[tuple[str, str, Gtk.Widget, str | None], ...] = (
            ("pubkey", "Public key", self.pubkey, None),
            ("endpoint", "Endpoint", self.endpoint, None),
            (
                "allowed",
                "Allowed IPs",
                self.allowed,
                "Comma-separated; what goes through the tunnel",
            ),
            ("psk", "Preshared key", self.psk, None),
            ("keepalive", "Keepalive (s)", self.keepalive, "0 = off"),
        )
        for key, name, widget, hint in rows:
            self.rows[key] = field_row(name, widget, hint)
            self.append(self.rows[key])
        if peer is not None:
            self.pubkey.set_text(peer.get_public_key() or "")
            self.endpoint.set_text(peer.get_endpoint() or "")
            self.allowed.set_text(
                ", ".join(
                    x
                    for x in (
                        peer.get_allowed_ip(i, None)
                        for i in range(peer.get_allowed_ips_len())
                    )
                    if x
                )
            )
            self.keepalive.set_value(peer.get_persistent_keepalive())

    def _remove(self) -> None:
        self.page.remove_peer(self)

    def stored_psk(self, conn: NM.Connection) -> str | None:
        s_wg = _wg_setting(conn)
        if s_wg is None or self.peer is None:
            return None
        key = self.peer.get_public_key()
        for i in range(s_wg.get_peers_len()):
            p = s_wg.get_peer(i)
            if p.get_public_key() == key:
                return p.get_preshared_key()
        return None

    def _error(self, key: str | None, text: str | None) -> None:
        for k, row in self.rows.items():
            row.show_error(text if k == key else None)
        if text:
            raise FieldError("wireguard.peers", "Fix the peer fields above")

    def build(self) -> NM.WireGuardPeer:
        pubkey = self.pubkey.get_text().strip()
        self._error("pubkey", wg_key_problem(pubkey, "Public key"))
        endpoint = self.endpoint.get_text().strip()
        host, _, port = endpoint.rpartition(":")
        if endpoint and (
            not host or not port.isdigit() or not 0 < int(port) <= MAX_PORT
        ):
            self._error("endpoint", "Use host:port ([v6addr]:port for IPv6)")
        allowed = split_list(self.allowed.get_text())
        for ip in allowed:
            fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
            try:
                _ = parse_cidr(
                    ip, fam, IPV4_BITS if fam == socket.AF_INET else IPV6_BITS
                )
            except ValueError as e:
                self._error("allowed", str(e))
        psk = self.psk.value()
        if psk:
            self._error("psk", wg_key_problem(psk, "Preshared key"))
        self._error(None, None)
        if self.peer is None or (not endpoint and self.peer.get_endpoint()):
            # new peer, or one losing its endpoint: set_endpoint() takes no None
            # through GI, so start from a fresh peer and carry the flags over
            peer = NM.WireGuardPeer.new()
            # new() defaults the PSK to NOT_REQUIRED, which NM does not store;
            # system-owned (0) like `nmcli connection import` and nmutil's profiles
            peer.set_preshared_key_flags(NM.SettingSecretFlags.NONE)
            if self.peer is not None:
                peer.set_preshared_key_flags(self.peer.get_preshared_key_flags())
                _ = peer.set_preshared_key(
                    self.peer.get_preshared_key(), accept_invalid=True
                )
        else:
            peer = self.peer.new_clone(with_secrets=True)
        _ = peer.set_public_key(pubkey, accept_invalid=True)
        if endpoint:
            _ = peer.set_endpoint(endpoint, allow_invalid=True)
        peer.clear_allowed_ips()
        for ip in allowed:
            _ = peer.append_allowed_ip(ip, accept_invalid=True)
        if psk is not None:
            _ = peer.set_preshared_key(psk or None, accept_invalid=True)
        peer.set_persistent_keepalive(self.keepalive.value())
        peer.seal()
        err = _peer_problem(peer)
        if err:
            raise FieldError("wireguard.peers", err)
        return peer


def _peer_problem(peer: NM.WireGuardPeer) -> str | None:
    try:
        _ = peer.is_valid(check_non_secrets=True, check_secrets=True)
    except GLib.Error as e:
        return e.message
    return None
