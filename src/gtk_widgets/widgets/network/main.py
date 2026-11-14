#!/usr/bin/env python3
"""Network popup — GTK4 nm-applet replacement over libnm (NM 1.0 via PyGObject).

One NM.Client drives everything. Every NetworkManager call is async and the
UI follows client signals (plus a slow tick for signal strength and bitrates),
folded into one debounced sync that updates keyed rows in place, so open
password fields, details and confirmations survive updates.

Pages in a Gtk.Stack: the applet menu (switches, wired, Wi-Fi, the Exit
group of VPNs and Proxy rules), the saved-connections list (delete, hidden
Wi-Fi, WireGuard import/export), the Edit page and the Proxy rules page.
"""

import contextlib
import secrets
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, override

from gi.repository import Gio, GLib, GObject

from gtk_widgets.lib.ui.copy_label import CopyLabel, copyable
from gtk_widgets.lib.ui.widget_base import Gdk, Gtk, VScroller, WidgetPopup
from gtk_widgets.widgets.network import proxy as px
from gtk_widgets.widgets.network.editor import EDITABLE_TYPES, EapForm, EditPage
from gtk_widgets.widgets.network.nmutil import (
    HOTSPOT_ID,
    ICON,
    NM,
    VPN_TYPES,
    EapValues,
    ac_reason_text,
    ap_security,
    connection_security,
    connection_ssid,
    connectivity_problem,
    eap_connection,
    eap_problem,
    error_text,
    failure_text,
    freq_band,
    hidden_connection,
    hotspot_connection,
    ip_lines,
    is_hotspot,
    link_connection,
    nullable,
    password_problem,
    relative_time,
    signal_class,
    vpn_place,
    wifi_connection,
    wireguard_conf,
    write_private,
)
from gtk_widgets.widgets.network.proxypage import ProxyPage
from gtk_widgets.widgets.network.ui import (
    KeyedList,
    KeyedRow,
    button,
    entry,
    error_label,
    glyph_button,
    hbox,
    label,
    section,
    switch,
    vbox,
)

SYNC_DELAY_MS = 150  # debounce for bursts of client signals
TICK_S = 3  # refresh for values NM changes without signals we watch
WIFI_LIST_H = 300  # fixed: networks a scan finds later never resize the popup
ROW_SPACING = 4
SCAN_MAX_S = 15  # placeholders give way even if a device never reports its scan
# a connectivity problem shows once it has lasted this long on one link:
# Wi-Fi on/off and reconnects pass through "no internet" on the way
INET_HOLD_S = 3
INET_HOLD_MARGIN_MS = 50
WG_DIR = Path.home() / "Dropbox" / "wireguard"
MAX_SSID_BYTES = 32
CONNECTIONS_LIST_H = 480

AC_STATE = NM.ActiveConnectionState
PROXY: Final = "proxy-rules"  # the Proxy rules chip's key (VPN chips use profile UUIDs)
type Exit = NM.RemoteConnection | Literal["proxy-rules"]  # a VPN profile or PROXY
type Pairs = list[tuple[str, str]]
type ConnData = tuple[NM.RemoteConnection, str | None]  # profile, active interface
HIDDEN_SECURITY = [
    ("open", "None"),
    ("psk", "WPA/WPA2 Personal"),
    ("sae", "WPA3 Personal"),
]
CONN_GROUPS: list[tuple[str, tuple[str, ...] | None]] = [
    ("Wi-Fi", ("802-11-wireless",)),
    ("Ethernet", ("802-3-ethernet",)),
    ("WireGuard / VPN", VPN_TYPES),
    ("Other", None),
]
OPEN_KINDS = {"open", "owe"}
PASSWORD_KINDS = {"psk", "sae"}
NOT_SAVED = "The profile was not saved."


def ac_name(ac: NM.ActiveConnection) -> str:
    """An active connection's name as its profile has it now: after a rename
    the AC's own id can lag behind the profile's changed signal."""
    conn = nullable(ac.get_connection())
    return conn.get_id() if conn else ac.get_id()


class Details(Gtk.Box):
    """Name/value pairs of an active connection (values copy on click), plus
    an Edit… link to its profile (or the Proxy rules page) when on_edit is set."""

    def __init__(self, on_edit: Callable[[Exit | None], None] | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("net-details")
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=2)
        self.append(self.grid)
        self.on_edit = on_edit
        self._conn: Exit | None = None
        self.edit_btn = button("Edit…", on_click=self._edit)
        self.edit_btn.set_halign(Gtk.Align.START)
        self.edit_btn.set_visible(False)
        self.append(self.edit_btn)
        self._keys: list[str] | None = None
        self._values: list[CopyLabel] = []

    def _edit(self) -> None:
        if self.on_edit is not None:
            self.on_edit(self._conn)

    def update(self, pairs: Pairs, conn: Exit | None = None) -> None:
        keys = [k for k, _ in pairs]
        if keys != self._keys:
            while child := self.grid.get_first_child():
                self.grid.remove(child)
            self._values = []
            for i, key in enumerate(keys):
                name = label(key, "net-detail-key")
                name.set_valign(Gtk.Align.START)
                self.grid.attach(name, 0, i, 1, 1)
                value = CopyLabel("net-detail-value")
                self.grid.attach(value, 1, i, 1, 1)
                self._values.append(value)
            self._keys = keys
        for value, (_k, text) in zip(self._values, pairs, strict=True):
            value.set_content(text)
        self._conn = conn
        self.edit_btn.set_visible(
            conn is not None
            and self.on_edit is not None
            and (conn == PROXY or conn.get_connection_type() in EDITABLE_TYPES)
        )


def connection_details(ac: NM.ActiveConnection) -> Pairs:
    """(label, value) pairs for an active connection: addresses, DNS, link."""
    pairs: Pairs = []
    devices = ac.get_devices()
    dev = devices[0] if devices else None
    if dev:
        pairs.append(("Interface", dev.get_iface()))
    for fam, cfg in (("IPv4", ac.get_ip4_config()), ("IPv6", ac.get_ip6_config())):
        addrs, gw, dns = ip_lines(cfg)
        if addrs:
            pairs.append((fam, ", ".join(addrs)))
        if gw:
            pairs.append((f"{fam} gateway", gw))
        if dns:
            pairs.append((f"{fam} DNS", ", ".join(dns)))
    conn = nullable(ac.get_connection())
    if isinstance(dev, NM.DeviceWifi):
        pairs += _wifi_details(dev, conn)
    elif isinstance(dev, NM.DeviceEthernet) and dev.get_speed():
        pairs.append(("Speed", f"{dev.get_speed()} Mb/s"))
    elif isinstance(dev, NM.DeviceWireGuard):
        s_wg = nullable(conn.get_setting_by_name("wireguard")) if conn else None
        if isinstance(s_wg, NM.SettingWireGuard) and s_wg.get_peers_len():
            endpoint = s_wg.get_peer(0).get_endpoint()
            if endpoint:
                pairs.append(("Endpoint", endpoint))
    if dev and dev.get_hw_address() and not isinstance(dev, NM.DeviceWireGuard):
        pairs.append(("MAC", dev.get_hw_address()))
    return pairs


def _wifi_details(dev: NM.DeviceWifi, conn: NM.RemoteConnection | None) -> Pairs:
    pairs: Pairs = []
    if dev.get_bitrate():
        pairs.append(("Bitrate", f"{dev.get_bitrate() / 1000:g} Mb/s"))
    ap = nullable(dev.get_active_access_point())
    if ap and ap.get_frequency():
        pairs.append(
            ("Frequency", f"{ap.get_frequency()} MHz ({freq_band(ap.get_frequency())})")
        )
    if conn:
        pairs.append(("Security", connection_security(conn)))
    return pairs


# --- rows ---


def skeleton_row(i: int) -> Gtk.Box:
    """Placeholder row in the Wi-Fi list's free space while a scan runs."""
    row = hbox(10, "net-row")
    row.add_css_class("net-skeleton")
    for width in (16, (120, 90, 150, 70, 110, 130, 80)[i % 7]):
        bone = Gtk.Box(valign=Gtk.Align.CENTER)
        bone.add_css_class("net-bone")
        bone.set_size_request(width, -1)
        row.append(bone)
    return row


class ExpandRow[D](KeyedRow[D]):
    """Rounded row: a header line plus a revealer for details or a form."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-row")
        self.head = hbox(10)
        self.append(self.head)
        self.revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.NONE)
        self.revealer.set_visible(False)  # no box spacing below the header while closed
        self.append(self.revealer)
        self.details = Details()

    def reveal(self, child: Gtk.Widget | None) -> None:
        """Show `child` below the header (None hides)."""
        if child is not None and self.revealer.get_child() is not child:
            self.revealer.set_child(child)
        self.revealer.set_reveal_child(child is not None)
        self.revealer.set_visible(child is not None)

    def revealed(self) -> Gtk.Widget | None:
        if not self.revealer.get_reveal_child():
            return None
        return nullable(self.revealer.get_child())


class DeviceRow(ExpandRow[NM.DeviceEthernet]):
    """Wired device: state, Connect/Disconnect, details."""

    def __init__(self, app: NetworkPopup, _key: str) -> None:
        super().__init__()
        self.app = app
        self.icon = label(ICON["wired"], "net-row-icon")
        text = vbox(2)
        text.set_hexpand(True)
        self.title = label("", "net-row-title", ellipsize=True)
        self.subtitle = label("", "net-row-subtitle", ellipsize=True)
        text.append(self.title)
        text.append(self.subtitle)
        self.action = button("", on_click=self._on_action)
        self.expand = glyph_button(ICON["expand"], "Details", self._toggle_details)
        for w in (self.icon, text, self.action, self.expand):
            self.head.append(w)
        self.details.on_edit = app.open_editor
        self.device: NM.DeviceEthernet | None = None
        self.ac: NM.ActiveConnection | None = None

    @override
    def update(self, data: NM.DeviceEthernet) -> None:
        dev = data
        self.device, self.ac = dev, nullable(dev.get_active_connection())
        state = dev.get_state()
        name = ac_name(self.ac) if self.ac else "Ethernet"
        self.title.set_text(name)
        if state == NM.DeviceState.ACTIVATED:
            sub = f"{dev.get_iface()} · connected"
        elif state == NM.DeviceState.UNAVAILABLE:
            sub = f"{dev.get_iface()} · cable unplugged"
        elif self.ac:
            sub = f"{dev.get_iface()} · connecting…"
        else:
            sub = f"{dev.get_iface()} · disconnected"
        self.subtitle.set_text(sub)
        active = self.ac is not None
        self.action.set_label("Disconnect" if active else "Connect")
        self.action.set_visible(state != NM.DeviceState.UNAVAILABLE)
        self.expand.set_visible(active)
        if self.ac is not None and self.revealed():
            self.details.update(
                connection_details(self.ac), nullable(self.ac.get_connection())
            )
        elif not active:
            self.reveal(None)
        self.expand.set_label(ICON["collapse" if self.revealed() else "expand"])

    def _on_action(self) -> None:
        if self.device is None:
            return
        if self.ac:
            self.app.disconnect_device(self.device)
        else:
            self.app.activate_profile(None, self.device, None, self.device.get_iface())

    def _toggle_details(self) -> None:
        self.reveal(None if self.revealed() else self.details)
        self.app.queue_sync()


class PasswordForm(Gtk.Box):
    """Inline password prompt for a new secured network."""

    def __init__(
        self, on_submit: Callable[[str], None], on_cancel: Callable[[], None]
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row = hbox(4)
        self.entry = entry("Password", secret=True, on_activate=self._submit)
        row.append(self.entry)
        row.append(button("Connect", "net-btn-accent", on_click=self._submit))
        row.append(button("Cancel", on_click=on_cancel))
        self.append(row)
        self.error = error_label()
        self.append(self.error)
        self._on_submit = on_submit

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _submit(self) -> None:
        self._on_submit(self.entry.get_text())


@dataclass(slots=True)
class WifiItem:
    """One SSID of the Wi-Fi list: its strongest AP, saved profiles, active
    connection."""

    ssid: str
    ap: NM.AccessPoint | None
    device: NM.DeviceWifi
    kind: str
    security: str
    conns: list[NM.RemoteConnection]
    hotspot: bool
    ac: NM.ActiveConnection | None = None
    pending: bool = False


class WifiRow(ExpandRow[WifiItem]):
    """One SSID (strongest BSSID). Click: connect / reveal password / details."""

    def __init__(self, app: NetworkPopup, ssid: str) -> None:
        super().__init__()
        self.app, self.ssid = app, ssid
        self.item: WifiItem | None = None
        self.icon = label("", "net-row-icon")
        self.title = label(ssid, "net-row-title", hexpand=True, ellipsize=True)
        self.state = label("", "net-row-state")
        self.pct = label("", "net-pct")
        self.lock = label(ICON["lock"], "net-lock")
        self.lock.set_tooltip_text("")
        self.saved = label(ICON["saved"], "net-saved")
        self.saved.set_tooltip_text("Saved network")
        self.action = button("Disconnect", on_click=self._on_disconnect)
        for w in (
            self.icon,
            self.title,
            self.state,
            self.pct,
            self.lock,
            self.saved,
            self.action,
        ):
            self.head.append(w)
        self.head.set_cursor_from_name("pointer")
        click = Gtk.GestureClick()
        _ = click.connect("released", self._released)
        self.head.add_controller(click)
        self.form = PasswordForm(self._on_password, self._hide)
        self.eap_form: EnterpriseForm | None = (
            None  # built on first use: Enterprise only
        )
        self.details.on_edit = app.open_editor

    def _hide(self) -> None:
        self.reveal(None)

    def _released(self, _g: Gtk.GestureClick, _n: int, _x: float, _y: float) -> None:
        self._on_click()

    @override
    def update(self, data: WifiItem) -> None:
        item = self.item = data
        ap, ac = item.ap, item.ac
        hotspot = item.hotspot
        strength = ap.get_strength() if ap and not hotspot else None
        self.icon.set_text(ICON["hotspot"] if hotspot else ICON["wifi"])
        weak = signal_class(strength)
        for cls in ("weak", "very-weak"):
            if cls == weak:
                self.icon.add_css_class(f"net-signal-{cls}")
            else:
                self.icon.remove_css_class(f"net-signal-{cls}")
        self.pct.set_text(f"{ap.get_strength()}%" if ap and not hotspot else "")
        self.lock.set_visible(item.kind not in OPEN_KINDS)
        self.lock.set_tooltip_text(item.security)
        self.saved.set_visible(bool(item.conns) and not ac)
        self.action.set_visible(ac is not None)
        self.action.set_label("Stop" if hotspot else "Disconnect")
        state = ""
        if ac is not None:
            st = ac.get_state()
            state = (
                ("hotspot" if hotspot else ICON["check"])
                if st == AC_STATE.ACTIVATED
                else "connecting…"
            )
        elif item.pending:
            state = "connecting…"
        self.state.set_text(state)
        if ac is not None:
            self.add_css_class("net-row-active")
            if self.revealed() is self.details:
                self.details.update(
                    connection_details(ac), nullable(ac.get_connection())
                )
        else:
            self.remove_css_class("net-row-active")
            if self.revealed() is self.details:
                self.reveal(None)

    def _on_click(self) -> None:
        item = self.item
        if item is None:
            return
        if item.ac is not None:
            self.reveal(None if self.revealed() else self.details)
            self.app.queue_sync()
        elif item.conns:
            self.app.activate_profile(item.conns[0], item.device, item.ap, self.ssid)
        elif item.kind in OPEN_KINDS:
            self.app.connect_new(self, item, None)
        elif item.kind in PASSWORD_KINDS:
            if self.revealed() is self.form:
                self.reveal(None)
            else:
                self.form.show_error(None)
                self.reveal(self.form)
                _ = self.form.entry.grab_focus()
        elif item.kind == "eap":
            self._toggle_eap_form()
        else:
            self.app.set_status(
                f"{item.security} networks aren't supported", error=True
            )

    def _toggle_eap_form(self) -> None:
        if self.eap_form is None:
            self.eap_form = EnterpriseForm(self._on_enterprise, self._hide)
        if self.revealed() is self.eap_form:
            self.reveal(None)
        else:
            self.eap_form.show_error(None)
            self.reveal(self.eap_form)
            _ = self.eap_form.form.identity.grab_focus()

    def _on_enterprise(self, values: EapValues, password: str | None) -> None:
        if self.eap_form is None or self.item is None:
            return
        problem = eap_problem(values, password, password_known=False)
        if problem:
            self.eap_form.show_error(problem)
            return
        self.eap_form.show_error(None)
        self.app.connect_enterprise(self, self.item, values, password)

    def _on_password(self, password: str) -> None:
        if self.item is None:
            return
        problem = password_problem(self.item.kind, password)
        if problem:
            self.form.show_error(problem)
            return
        self.form.show_error(None)
        self.app.connect_new(self, self.item, password)

    def _on_disconnect(self) -> None:
        if self.item is not None and self.item.ac is not None:
            self.app.deactivate(self.item.ac)

    def failed(self, reason: str) -> None:
        """New-network activation failed: back to the password form with the reason."""
        if self.item and self.item.kind in PASSWORD_KINDS:
            self.form.show_error(f"Not connected: {reason}. {NOT_SAVED}")
            self.reveal(self.form)
        elif self.item and self.item.kind == "eap" and self.eap_form is not None:
            self.eap_form.show_error(f"Not connected: {reason}. {NOT_SAVED}")
            self.reveal(self.eap_form)


class EnterpriseForm(Gtk.Box):
    """Inline PEAP/TTLS form for a new WPA Enterprise network."""

    def __init__(
        self,
        on_submit: Callable[[EapValues, str | None], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.form = EapForm(lambda: None)
        self.append(self.form)
        self.error = error_label()
        self.append(self.error)
        self._on_submit = on_submit
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=on_cancel))
        buttons.append(button("Connect", "net-btn-accent", on_click=self._submit))
        self.append(buttons)

    def _submit(self) -> None:
        self._on_submit(self.form.values(), self.form.password_value())

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))


@dataclass(frozen=True, slots=True)
class ProxyInfo:
    """Proxy rules as the Exit group shows it."""

    up: bool  # starting or on, and not stopping
    on: bool
    going: bool
    crashed: bool
    summary: str
    pairs: Pairs


@dataclass(frozen=True, slots=True)
class _ExitSection:
    state: Gtk.Label
    details: Details
    expand: Gtk.Button
    revealer: Gtk.Revealer


type ExitLine = tuple[str, str | None]  # (state text, tone)


def _vpn_line(
    vpn_name: str | None,
    *,
    activated: bool,
    active: NM.ActiveConnection | None,
    going: list[NM.ActiveConnection],
    selected: str | None,
) -> ExitLine:
    if vpn_name and activated:
        place = vpn_place(vpn_name)
        return (f"connected · {vpn_name}" + (f", {place}" if place else ""), "on")
    if vpn_name:
        return (f"connecting · {vpn_name}…", None)
    if active or going:
        return (f"disconnecting · {ac_name(active or going[0])}…", None)
    if selected == PROXY:
        return (
            "off · Proxy rules is on" if activated else "off · Proxy rules is starting",
            None,
        )
    return ("off", None)


def _proxy_line(
    proxy: ProxyInfo,
    vpn_name: str | None,
    *,
    activated: bool,
    selected: str | None,
    going: bool,
) -> ExitLine:
    if selected == PROXY:
        return (f"on · {proxy.summary}", "on") if activated else ("starting…", None)
    if going:
        return ("stopping…", None)
    if proxy.crashed:
        return ("stopped", "bad")
    if vpn_name and activated:
        return (f"off · {vpn_name} is on", None)
    return ("off", None)


class ExitChips(Gtk.Box):
    """The VPN and Proxy sections. Exits are exclusive: a chip per VPN profile
    in a fixed order, and Proxy rules (per-app routing through sing-box). A
    click on a chip connects or switches (the other exit goes down first), a
    click on the selected chip turns it off. Each title line shows its state,
    including when the other exit is the one on, and toggles the details."""

    PER_LINE = 6

    def __init__(self, app: NetworkPopup) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        titles = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)  # the states line up
        self.vpn = self._section("VPN", titles)
        self.flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            homogeneous=True,
            min_children_per_line=self.PER_LINE,
            max_children_per_line=self.PER_LINE,
            row_spacing=4,
            column_spacing=4,
        )
        self.append(self.flow)
        self.append(self.vpn.revealer)
        self.proxy = self._section(
            "Proxy",
            titles,
            glyph_button(
                ICON["settings"], "Proxy rules: proxies and apps", app.open_proxy_page
            ),
        )
        # Proxy rules on a line of its own: its longer label would widen every
        # chip of the homogeneous grid
        self.proxy_line = hbox(8)
        self.proxy_summary = label("", "net-row-subtitle", hexpand=True, ellipsize=True)
        self.proxy_line.append(self.proxy_summary)
        self.append(self.proxy_line)
        self.append(self.proxy.revealer)
        # (uuid, name) per chip: a rename relabels and re-sorts
        self._profiles: list[tuple[str, str]] | None = None
        self._selected: str | None = None  # key shown as selected by the last update
        self._chips: dict[str, Gtk.ToggleButton] = {}  # uuid or PROXY
        self._handlers: dict[str, int] = {}

    def _section(
        self, title: str, titles: Gtk.SizeGroup, *extra: Gtk.Widget
    ) -> _ExitSection:
        """Title line (title, state, details toggle, extra) and a details revealer."""
        line = hbox(8, "net-section-row")
        name = label(title, "net-section")
        titles.add_widget(name)
        line.append(name)
        state = label("", "net-exit-state", hexpand=True, ellipsize=True)
        line.append(state)
        details = Details(on_edit=self.app.open_editor)
        details.add_css_class("net-exit-details")
        revealer = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.NONE,
            child=details,
            visible=False,
        )
        expand = glyph_button(
            ICON["expand"], "Details", lambda: self._toggle_details(revealer)
        )
        line.append(expand)
        for w in extra:
            line.append(w)
        self.append(line)
        return _ExitSection(state, details, expand, revealer)

    def _rebuild(self, conns: list[NM.RemoteConnection]) -> None:
        # no toggle group: a group cannot turn its selected chip off, so update()
        # keeps the chips exclusive
        self.flow.remove_all()
        if PROXY in self._chips:
            self.proxy_line.remove(self._chips[PROXY])
        self._chips, self._handlers = {}, {}
        exits: list[Exit] = [*conns, PROXY]
        for conn in exits:
            if conn == PROXY:
                chip, key = Gtk.ToggleButton(label="Proxy rules"), PROXY
                chip.add_css_class("net-chip-proxy")
            else:
                chip, key = Gtk.ToggleButton(label=conn.get_id()), conn.get_uuid()
                chip.set_tooltip_text(vpn_place(conn.get_id()) or conn.get_id())
            chip.add_css_class("net-chip")
            self._handlers[key] = chip.connect("toggled", self._on_toggled, conn)
            self._chips[key] = chip
            if key == PROXY:
                self.proxy_line.prepend(chip)
            else:
                self.flow.append(chip)
        self.flow.set_visible(bool(conns))
        self._profiles = [(c.get_uuid(), c.get_id()) for c in conns]

    def update(
        self,
        conns: list[NM.RemoteConnection],
        *,
        active: NM.ActiveConnection | None,
        going: list[NM.ActiveConnection],
        target: str | None,
        failed: str | None,
        proxy: ProxyInfo,
    ) -> None:
        """conns: VPN profiles in display order; active: the VPN AC shown as
        selected (activating or activated) or None; going: VPN ACs being torn
        down; target: key the user just picked ("" for off); failed: key whose
        last try failed; proxy: Proxy rules state."""
        if [(c.get_uuid(), c.get_id()) for c in conns] != self._profiles:
            self._rebuild(conns)
        if target is not None:
            selected = target or None
        elif active is not None:
            selected = active.get_uuid()
        else:
            selected = PROXY if proxy.up else None
        if selected == PROXY:
            activated = proxy.on
        else:
            activated = (
                active is not None
                and active.get_state() == AC_STATE.ACTIVATED
                and active.get_uuid() == selected
            )
        self._selected = selected
        going_keys = {ac.get_uuid() for ac in going}
        if active is not None and active.get_uuid() != selected:
            going_keys.add(active.get_uuid())  # still up, but on its way out
        if proxy.going or (proxy.up and selected != PROXY):
            going_keys.add(PROXY)
        self._chips[PROXY].set_tooltip_text(proxy.summary)
        self.proxy_summary.set_text(proxy.summary)
        self._mark_chips(selected, failed, going_keys, activated=activated)

        vpn_name = next((c.get_id() for c in conns if c.get_uuid() == selected), None)
        vpn = _vpn_line(
            vpn_name, activated=activated, active=active, going=going, selected=selected
        )
        prx = _proxy_line(
            proxy,
            vpn_name,
            activated=activated,
            selected=selected,
            going=PROXY in going_keys,
        )
        self.proxy_summary.set_visible(
            not (activated and selected == PROXY)
        )  # the state says it
        vpn_on = bool(vpn_name) and activated
        if self._show(self.vpn, vpn, activated=vpn_on) and active is not None:
            self.vpn.details.update(
                connection_details(active), nullable(active.get_connection())
            )
        if self._show(self.proxy, prx, activated=selected == PROXY and activated):
            self.proxy.details.update(proxy.pairs, PROXY)

    def _mark_chips(
        self,
        selected: str | None,
        failed: str | None,
        going_keys: set[str],
        *,
        activated: bool,
    ) -> None:
        for key, chip in self._chips.items():
            chip.handler_block(self._handlers[key])
            chip.set_active(key == selected)
            chip.handler_unblock(self._handlers[key])
            for cls, on in (
                ("net-chip-connecting", key == selected and not activated),
                ("net-chip-going", key in going_keys and key != selected),
                ("net-chip-failed", key == failed and key != selected),
            ):
                if on:
                    chip.add_css_class(cls)
                else:
                    chip.remove_css_class(cls)

    @staticmethod
    def _show(sec: _ExitSection, state: ExitLine, *, activated: bool) -> bool:
        """Show a section's state line; True when its open details need an update."""
        text, tone = state
        sec.state.set_text(text)
        sec.state.set_css_classes(
            ["net-exit-state", *([f"net-exit-{tone}"] if tone else [])]
        )
        sec.expand.set_visible(activated)
        refresh = activated and sec.revealer.get_visible()
        if not activated:
            sec.revealer.set_visible(False)
            sec.revealer.set_reveal_child(False)
        sec.expand.set_label(
            ICON["collapse" if sec.revealer.get_visible() else "expand"]
        )
        return refresh

    def _on_toggled(self, chip: Gtk.ToggleButton, conn: Exit) -> None:
        key = PROXY if conn == PROXY else conn.get_uuid()
        if chip.get_active() and key != self._selected:
            self.app.select_exit(conn)
        elif not chip.get_active() and key == self._selected:
            self.app.select_exit(None)  # a click on the selected chip turns it off

    def _toggle_details(self, revealer: Gtk.Revealer) -> None:
        show = not revealer.get_visible()
        revealer.set_visible(show)
        revealer.set_reveal_child(show)
        self.app.queue_sync()


class ConnRow(KeyedRow[ConnData]):
    """Saved profile on the Connections page: name, interface, last used,
    export (WireGuard), edit and delete with inline confirmation."""

    def __init__(self, app: NetworkPopup, _uuid: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("net-row")
        self.app = app
        self.conn: NM.RemoteConnection | None = None
        text = vbox(2)
        text.set_hexpand(True)
        self.title = label("", "net-row-title", ellipsize=True)
        self.subtitle = label("", "net-row-subtitle", ellipsize=True)
        text.append(self.title)
        text.append(self.subtitle)
        self.append(text)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self.stack.set_valign(Gtk.Align.CENTER)
        actions = hbox(2)
        self.export = glyph_button(ICON["export"], "Export .conf", self._export)
        actions.append(self.export)
        self.edit_btn = glyph_button(
            ICON["edit"], "Edit", lambda: self.app.open_editor(self.conn)
        )
        actions.append(self.edit_btn)
        actions.append(
            glyph_button(
                ICON["delete"],
                "Delete",
                lambda: self.stack.set_visible_child_name("confirm"),
                "net-delete-btn",
            )
        )
        confirm = hbox(4)
        confirm.append(label("Delete?", "net-confirm"))
        confirm.append(button("Delete", "net-btn-danger", on_click=self._delete))
        confirm.append(
            button(
                "Keep", on_click=lambda: self.stack.set_visible_child_name("actions")
            )
        )
        _ = self.stack.add_named(actions, "actions")
        _ = self.stack.add_named(confirm, "confirm")
        self.append(self.stack)

    @override
    def update(self, data: ConnData) -> None:
        conn, active_dev = data
        self.conn = conn
        self.title.set_text(conn.get_id())
        s_con = conn.get_setting_connection()
        iface = active_dev or s_con.get_interface_name() or "any interface"
        used = (
            "active now"
            if active_dev
            else f"used {relative_time(s_con.get_timestamp())}"
        )
        if s_con.get_timestamp() == 0 and not active_dev:
            used = "never used"
        self.subtitle.set_text(f"{iface} · {used}")
        self.export.set_visible(conn.get_connection_type() == "wireguard")
        editable = conn.get_connection_type() in EDITABLE_TYPES
        self.edit_btn.set_sensitive(editable)
        self.edit_btn.set_tooltip_text(
            "Edit" if editable else "Not editable here (nmcli)"
        )

    def _export(self) -> None:
        if self.conn is not None:
            self.app.export_wireguard(self.conn)

    def _delete(self) -> None:
        self.stack.set_visible_child_name("actions")
        if self.conn is not None:
            self.app.delete(self.conn)


class HiddenForm(Gtk.Box):
    """SSID + security + password for a hidden network."""

    def __init__(self, app: NetworkPopup) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.app = app
        self.append(label("Hidden network", "net-form-title"))
        self.ssid = entry("Network name (SSID)", on_activate=self._submit)
        self.append(self.ssid)
        self.security = Gtk.DropDown.new_from_strings([t for _, t in HIDDEN_SECURITY])
        self.security.add_css_class("net-choice")
        self.security.set_selected(1)
        _ = self.security.connect("notify::selected", self._security_changed)
        self.append(self.security)
        self.password = entry("Password", secret=True, on_activate=self._submit)
        self.append(self.password)
        self.error = error_label()
        self.append(self.error)
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=self.close))
        buttons.append(button("Connect", "net-btn-accent", on_click=self._submit))
        self.append(buttons)
        self.set_visible(False)

    def open(self) -> None:
        self.ssid.set_text("")
        self.password.set_text("")
        self.show_error(None)
        self._sync_password()
        self.set_visible(True)
        _ = self.ssid.grab_focus()

    def close(self) -> None:
        self.set_visible(False)

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _kind(self) -> str:
        return HIDDEN_SECURITY[self.security.get_selected()][0]

    def _security_changed(self, _dd: Gtk.DropDown, _spec: GObject.ParamSpec) -> None:
        self._sync_password()

    def _sync_password(self) -> None:
        self.password.set_visible(self._kind() != "open")

    def _submit(self) -> None:
        ssid, kind = self.ssid.get_text().strip(), self._kind()
        password = self.password.get_text() if kind != "open" else None
        if not ssid:
            self.show_error("Enter the network name")
            return
        if len(ssid.encode()) > MAX_SSID_BYTES:
            self.show_error(f"SSIDs are at most {MAX_SSID_BYTES} bytes")
            return
        problem = password_problem(kind, password) if password is not None else None
        if problem:
            self.show_error(problem)
            return
        self.show_error(None)
        self.app.connect_hidden(self, ssid, kind, password)


class HotspotForm(Gtk.Box):
    BANDS = (("bg", "2.4 GHz"), ("a", "5 GHz"))

    def __init__(self, app: NetworkPopup) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.app = app
        self.append(label("Create hotspot", "net-form-title"))
        self.ssid = entry("Network name (SSID)", on_activate=self._submit)
        self.append(self.ssid)
        self.password = entry(
            "Password (8-63 characters)", secret=True, on_activate=self._submit
        )
        self.append(self.password)
        self.band = Gtk.DropDown.new_from_strings([t for _, t in self.BANDS])
        self.band.add_css_class("net-choice")
        self.append(self.band)
        warn = label(
            "Starting a hotspot drops the current Wi-Fi connection "
            "on cards with a single radio.",
            "net-form-warning",
        )
        warn.set_wrap(True)
        warn.set_max_width_chars(40)
        self.append(warn)
        self.error = error_label()
        self.append(self.error)
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=self.close))
        buttons.append(button("Start", "net-btn-accent", on_click=self._submit))
        self.append(buttons)
        self.set_visible(False)

    def open(self, existing: NM.Connection | None = None) -> None:
        ssid, band = f"{socket.gethostname()}-hotspot", 0
        if existing:
            ssid = connection_ssid(existing) or ssid
            s_wifi = existing.get_setting_wireless()
            band = 1 if s_wifi.get_band() == "a" else 0
        # a fresh random password, like `nmcli device wifi hotspot`
        password = secrets.token_urlsafe(9)
        self.ssid.set_text(ssid)
        self.password.set_text(password)
        self.band.set_selected(band)
        self.show_error(None)
        self.set_visible(True)
        _ = self.ssid.grab_focus()

    def close(self) -> None:
        self.set_visible(False)

    def show_error(self, text: str | None) -> None:
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _submit(self) -> None:
        ssid, password = self.ssid.get_text().strip(), self.password.get_text()
        if not ssid or len(ssid.encode()) > MAX_SSID_BYTES:
            self.show_error(f"Enter a network name of at most {MAX_SSID_BYTES} bytes")
            return
        problem = password_problem("psk", password)
        if problem:
            self.show_error(problem)
            return
        self.app.start_hotspot(
            self, ssid, password, self.BANDS[self.band.get_selected()][0]
        )


@dataclass(slots=True)
class _Teardown:
    """Progress of _take_down_vpns: the removal handler and how it ended."""

    failed: bool = False
    started: bool = False
    handler: int = 0


# --- popup ---


class NetworkPopup(WidgetPopup):
    SHOW_ON_BUILD = (
        False  # shown by _on_client with NM's state in: no empty first frame
    )

    def __init__(self) -> None:
        super().__init__(application_id="dev.dotfiles.network")
        self.client: NM.Client | None = None
        self._sync_id = 0
        self._tick_id = 0
        self._pending: dict[str, bool] = {}  # ssids of new networks being activated
        # uuid or PROXY being switched to, "" while turning off
        self._exit_target: str | None = None
        self._exit_failed: str | None = None  # uuid or PROXY whose last start failed
        self.proxy_state = px.load_state()
        self.proxy_watch: px.ServiceWatch | None = None
        # while the helper runs
        self._proxy_busy: Literal["starting", "stopping"] | None = None
        self._scanning = False
        self._scan_since = 0  # NM timestamp (ms) the running scan started at
        self._scan_wait: set[str] = (
            set()
        )  # Wi-Fi device paths whose scan has not come back
        self._scan_timer = 0
        # last shown Wi-Fi switch value: turning it on starts a scan
        self._wifi_was_on: bool | None = None
        # (link path, problem kind) seen by the last sync
        self._inet_key: tuple[str, str] | None = None
        # when that key appeared; None before the first sync
        self._inet_since: float | None = None

    def _nm(self) -> NM.Client:
        if self.client is None:
            raise RuntimeError("NetworkManager has not answered yet")
        return self.client

    # --- UI ---

    @override
    def build_ui(self) -> Gtk.Widget:
        self._container = vbox(8, "net-container")
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self._stack.set_vhomogeneous(False)
        self._stack.set_hhomogeneous(True)
        _ = self._stack.add_named(self._build_main(), "main")
        _ = self._stack.add_named(self._build_connections(), "connections")
        self._editor_back = "connections"
        self._editor = EditPage(self, lambda: self._show_page(self._editor_back))
        _ = self._stack.add_named(self._editor, "edit")
        self._proxy_page = ProxyPage(self, lambda: self._show_page("main"))
        _ = self._stack.add_named(self._proxy_page, "proxies")
        self._container.append(self._stack)

        self._status = label("", "net-status")
        self._status.set_wrap(True)
        self._status.set_max_width_chars(48)
        self._status.set_visible(False)
        self._container.append(self._status)

        NM.Client.new_async(None, self._on_client)
        self.proxy_watch = px.ServiceWatch(lambda _w: self.queue_sync())
        return self._container

    def _build_main(self) -> Gtk.Box:
        page = vbox(8)
        header = hbox(6)
        header.append(label("Network", "net-title", hexpand=True))
        header.append(label("Networking", "net-switch-label"))
        self._net_switch = switch(self._set_networking)
        header.append(self._net_switch)
        page.append(header)
        page.append(self._build_inet())
        page.append(self._build_offline())

        self._body = vbox(8)
        page.append(self._body)

        # wired
        self._wired_section = section("Wired")
        self._body.append(self._wired_section)
        self._wired: KeyedList[str, NM.DeviceEthernet] = KeyedList(self._device_row)
        self._body.append(self._wired)

        self._build_wifi()

        # VPN and Proxy: one exclusive exit
        self._exit = ExitChips(self)
        self._body.append(self._exit)

        footer = hbox(4)
        footer.add_css_class("net-footer")
        footer.append(
            button("Connections", on_click=lambda: self._show_page("connections"))
        )
        page.append(footer)
        return page

    def _build_inet(self) -> Gtk.Box:
        """The connectivity check's result: captive portal, limited, none."""
        self._inet = hbox(8, "net-inet")
        self._inet_icon = label("", "net-inet-icon")
        self._inet.append(self._inet_icon)
        self._inet_msg = label("", "net-inet-msg", hexpand=True)
        self._inet_msg.set_wrap(True)
        self._inet.append(self._inet_msg)
        self._portal_btn = button(
            "Sign in…",
            tooltip="Open the portal's login page",
            on_click=self._open_portal,
        )
        self._inet.append(self._portal_btn)
        self._inet.set_visible(False)
        return self._inet

    def _build_offline(self) -> Gtk.Box:
        self._offline = vbox(4)
        self._offline.set_halign(Gtk.Align.CENTER)
        self._offline.append(label(ICON["offline"], "net-error-icon", xalign=0.5))
        self._offline_msg = copyable(label("", "net-error-msg", xalign=0.5))
        self._offline.append(self._offline_msg)
        self._offline_hint = copyable(label("", "net-error-hint", xalign=0.5))
        self._offline.append(self._offline_hint)
        self._offline.set_visible(False)
        return self._offline

    def _build_wifi(self) -> None:
        self._scan_btn = glyph_button(ICON["rescan"], "Rescan", self._start_scan)
        self._wifi_switch = switch(self._set_wireless)
        self._wifi_section = section("Wi-Fi", self._scan_btn, self._wifi_switch)
        self._body.append(self._wifi_section)
        # one fixed-height area for the list, its placeholders and its messages
        self._wifi_msg = label("", "net-empty")
        self._wifi: KeyedList[str, WifiItem] = KeyedList(self._wifi_row, ROW_SPACING)
        self._wifi_skel = vbox(ROW_SPACING)
        wifi_area = vbox(ROW_SPACING)
        for w in (self._wifi_msg, self._wifi, self._wifi_skel):
            wifi_area.append(w)
        scroller = VScroller(WIFI_LIST_H, wifi_area)
        scroller.set_min_content_height(WIFI_LIST_H)
        self._wifi_scroller = scroller
        self._body.append(scroller)
        self._wifi_extra = hbox(4)
        self._wifi_extra.append(button("Hidden network…", on_click=self._open_hidden))
        self._wifi_extra.append(button("Create hotspot…", on_click=self._open_hotspot))
        self._body.append(self._wifi_extra)
        self._hidden = HiddenForm(self)
        self._body.append(self._hidden)
        self._hotspot = HotspotForm(self)
        self._body.append(self._hotspot)

    def _device_row(self, key: str) -> DeviceRow:
        return DeviceRow(self, key)

    def _wifi_row(self, ssid: str) -> WifiRow:
        return WifiRow(self, ssid)

    def _conn_row(self, uuid: str) -> ConnRow:
        return ConnRow(self, uuid)

    def _build_connections(self) -> Gtk.Box:
        page = vbox(8)
        header = hbox(6)
        header.append(
            glyph_button(ICON["back"], "Back", lambda: self._show_page("main"))
        )
        header.append(label("Connections", "net-title", hexpand=True))
        page.append(header)

        self._conn_groups: dict[str, tuple[Gtk.Box, KeyedList[str, ConnData]]] = {}
        groups = vbox(8)
        for title, _types in CONN_GROUPS:
            sec = section(title)
            lst: KeyedList[str, ConnData] = KeyedList(self._conn_row)
            groups.append(sec)
            groups.append(lst)
            self._conn_groups[title] = (sec, lst)
        scroller = VScroller(CONNECTIONS_LIST_H)
        scroller.set_child(groups)
        page.append(scroller)

        self._conn_hidden = HiddenForm(self)
        page.append(self._conn_hidden)
        add = hbox(4)
        add.add_css_class("net-footer")
        add.append(label("Add", "net-section"))
        add.append(button("Hidden Wi-Fi…", on_click=self._conn_hidden.open))
        add.append(button("Import WireGuard…", on_click=self._import_wireguard))
        page.append(add)
        return page

    def _show_page(self, name: str) -> None:
        self._stack.set_visible_child_name(name)
        self.set_status(None)
        self.queue_sync()

    def set_status(
        self, text: str | None, *, error: bool = False, ok: bool = False
    ) -> None:
        self._status.set_text(text or "")
        self._status.set_visible(bool(text))
        _ = copyable(self._status, on=error)
        for cls, on in (("net-status-err", error), ("net-status-ok", ok)):
            if on:
                self._status.add_css_class(cls)
            else:
                self._status.remove_css_class(cls)

    def _fail(self, what: str, err: BaseException) -> None:
        self.set_status(f"{what}: {error_text(err)}", error=True)

    @override
    def _on_key(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        win = self.get_active_window()
        focus = win.get_focus() if win else None
        if keyval == Gdk.KEY_q and isinstance(focus, (Gtk.Text, Gtk.TextView)):
            return False
        return super()._on_key(_controller, keyval, _keycode, _state)

    # --- client and signals ---

    def _on_client(self, _src: GObject.Object | None, res: Gio.AsyncResult) -> None:
        try:
            self.client = NM.Client.new_finish(res)
        except GLib.Error as e:
            self._show_offline("Cannot reach NetworkManager", error_text(e))
            _ = self.show_ui()
            return
        c = self.client
        for sig in (
            "device-added",
            "device-removed",
            "active-connection-added",
            "active-connection-removed",
            "connection-added",
            "connection-removed",
            "notify::nm-running",
            "notify::networking-enabled",
            "notify::wireless-enabled",
            "notify::wireless-hardware-enabled",
            "notify::connectivity",
            "notify::primary-connection",
        ):
            _ = c.connect(sig, self._on_client_signal)
        for dev in c.get_devices():
            self._watch_device(dev)
        for ac in c.get_active_connections():
            _ = ac.connect("state-changed", lambda *_: self.queue_sync())
        for conn in c.get_connections():
            _ = conn.connect("changed", lambda *_: self.queue_sync())
        self._tick_id = GLib.timeout_add_seconds(TICK_S, self._tick)
        _ = self.show_ui()  # rooted before the first sync measures rows; drawn after it
        self._start_scan()
        _ = self._sync()
        if c.connectivity_check_get_enabled():  # fresh result, not up to 5 min old
            c.check_connectivity_async(None, self._on_checked)

    def _on_checked(self, client: NM.Client, res: Gio.AsyncResult) -> None:
        with contextlib.suppress(GLib.Error):  # the property keeps NM's last result
            _ = client.check_connectivity_finish(res)

    def _on_client_signal(
        self, _client: NM.Client, obj: GObject.Object | GObject.ParamSpec
    ) -> None:
        if isinstance(obj, NM.Device):
            self._watch_device(obj)
        elif isinstance(obj, NM.ActiveConnection):
            _ = obj.connect("state-changed", lambda *_: self.queue_sync())
        elif isinstance(obj, NM.RemoteConnection):
            _ = obj.connect("changed", lambda *_: self.queue_sync())
        self.queue_sync()

    def _watch_device(self, dev: NM.Device) -> None:
        _ = dev.connect("state-changed", lambda *_: self.queue_sync())
        if isinstance(dev, NM.DeviceWifi):
            for sig in (
                "access-point-added",
                "access-point-removed",
                "notify::active-access-point",
                "notify::last-scan",
            ):
                _ = dev.connect(sig, lambda *_: self.queue_sync())

    def queue_sync(self, *, now: bool = False) -> None:
        """Debounced sync; now=True: on the next idle (a user flip shows at once)."""
        if now and self._sync_id:
            _ = GLib.source_remove(self._sync_id)
            self._sync_id = 0
        if not self._sync_id:
            self._sync_id = (
                GLib.idle_add(self._sync)
                if now
                else GLib.timeout_add(SYNC_DELAY_MS, self._sync)
            )

    def _tick(self) -> bool:
        self.queue_sync()
        return GLib.SOURCE_CONTINUE

    @override
    def do_shutdown(self) -> None:
        for sid in (self._sync_id, self._tick_id, self._scan_timer):
            if sid:
                _ = GLib.source_remove(sid)
        self._sync_id = self._tick_id = self._scan_timer = 0
        Gtk.Application.do_shutdown(self)

    # --- sync ---

    def _show_offline(self, msg: str, hint: str) -> None:
        self._offline_msg.set_text(msg)
        self._offline_hint.set_text(hint)
        self._offline_hint.set_visible(bool(hint))
        self._offline.set_visible(True)
        self._body.set_visible(False)

    def _devices[T: NM.Device](self, cls: type[T]) -> list[T]:
        return [
            d
            for d in self._nm().get_devices()
            if isinstance(d, cls) and d.get_managed() and d.is_real()
        ]

    def _sync(self) -> bool:
        self._sync_id = 0
        c = self.client
        if c is None:
            return GLib.SOURCE_REMOVE
        if not c.get_nm_running():
            self._net_switch.set_sensitive(False)
            self._show_offline(
                "NetworkManager is not running", "systemctl start NetworkManager"
            )
            return GLib.SOURCE_REMOVE
        self._net_switch.set_sensitive(True)
        networking = self._net_switch.set_(active=c.networking_get_enabled())
        if not networking:
            self._inet.set_visible(False)
            self._show_offline("Networking is disabled", "")
        else:
            self._offline.set_visible(False)
            self._body.set_visible(True)
            self._sync_connectivity(c)
            self._sync_wired()
            self._sync_wifi(c)
            self._sync_exit()
        page = self._stack.get_visible_child_name()
        remote = self._editor.remote
        if page == "connections":
            self._sync_connections(c)
        elif page == "proxies":
            self._proxy_page.sync()
        elif (
            page == "edit" and remote is not None and remote not in c.get_connections()
        ):
            name = remote.get_id()
            self._editor.remote = None
            self._show_page("connections")
            self.set_status(f"{name} was deleted", error=True)
        return GLib.SOURCE_REMOVE

    def _sync_connectivity(self, c: NM.Client) -> None:
        link = link_connection(c)
        problem = None
        if link is not None and link.get_state() == AC_STATE.ACTIVATED:
            problem = connectivity_problem(c)
        key = (link.get_path(), problem[0]) if link is not None and problem else None
        now = GLib.get_monotonic_time() / 1e6
        if self._inet_since is None:
            # at open NM's state has settled: a problem shows at once
            self._inet_key, self._inet_since = key, now - INET_HOLD_S
        elif key != self._inet_key:
            self._inet_key, self._inet_since = key, now
            if problem:
                _ = GLib.timeout_add(
                    INET_HOLD_S * 1000 + INET_HOLD_MARGIN_MS, self._inet_hold_done
                )
        if problem and now - self._inet_since < INET_HOLD_S:
            problem = None
        self._inet.set_visible(problem is not None)
        if problem:
            kind, text = problem
            self._inet_icon.set_text(
                ICON["portal"] if kind == "portal" else ICON["limited"]
            )
            self._inet_msg.set_text(text)
            self._portal_btn.set_visible(kind == "portal")

    def _inet_hold_done(self) -> bool:
        self.queue_sync()
        return GLib.SOURCE_REMOVE

    def _sync_wired(self) -> None:
        devs = self._devices(NM.DeviceEthernet)
        self._wired_section.set_visible(bool(devs))
        self._wired.sync([(d.get_iface(), d) for d in devs])

    def _sync_wifi(self, c: NM.Client) -> None:
        devs = self._devices(NM.DeviceWifi)
        hw = c.wireless_hardware_get_enabled()
        # the user's flip shows before NM reports it: the list follows the switch
        on = self._wifi_switch.set_(active=c.wireless_get_enabled() and hw)
        visible = bool(devs)
        for w in (self._wifi_section, self._wifi_scroller, self._wifi_extra):
            w.set_visible(visible)
        self._wifi_switch.set_sensitive(hw)
        if on and self._wifi_was_on is False:
            self._start_scan(request=False)  # NM scans once the radio is up
        elif not on and self._scanning:
            self._end_scan(sync=False)
        self._wifi_was_on = on
        if self._scanning:
            self._scan_wait = {
                d.get_path()
                for d in devs
                if d.get_path() in self._scan_wait
                and d.get_last_scan() < self._scan_since
            }
            if not self._scan_wait:
                self._end_scan(sync=False)
        self._scan_btn.set_sensitive(on and not self._scanning)
        if not visible:
            self._wifi_msg.set_visible(False)
            return
        if not hw:
            msg = "Wi-Fi is blocked by a hardware switch"
        elif not on:
            msg = "Wi-Fi is off"
        else:
            msg = None
        self._wifi_extra.set_sensitive(msg is None)
        if msg:
            self._wifi_msg.set_text(msg)
            self._wifi_msg.set_visible(True)
            self._wifi.sync([])
            self._sync_skeletons(on=False)
            return
        items = self._wifi_items(c, devs)
        self._wifi_msg.set_text("No networks found")
        self._wifi_msg.set_visible(not items and not self._scanning)
        self._wifi.sync([(it.ssid, it) for it in items])
        self._sync_skeletons(on=self._scanning)

    def _sync_skeletons(self, *, on: bool) -> None:
        """Fill the list's free space with placeholder rows while a scan runs."""
        box = self._wifi_skel
        first = box.get_first_child()
        if first is None:
            first = skeleton_row(0)
            box.append(first)  # kept: it measures the row height
        row_h = first.measure(Gtk.Orientation.VERTICAL, -1)[1]
        free = WIFI_LIST_H
        if self._wifi.get_visible():
            free -= self._wifi.measure(Gtk.Orientation.VERTICAL, -1)[1] + ROW_SPACING
        n = max(0, (free + ROW_SPACING) // (row_h + ROW_SPACING)) if on and row_h else 0
        rows: list[Gtk.Widget] = []
        child = box.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        for row in rows[max(n, 1) :]:
            box.remove(row)
        for i in range(len(rows), n):
            box.append(skeleton_row(i))
        box.set_visible(n > 0)

    def _wifi_items(self, c: NM.Client, devs: list[NM.DeviceWifi]) -> list[WifiItem]:
        """One item per SSID: strongest AP, saved profiles, active connection."""
        wifi_conns = [
            conn
            for conn in c.get_connections()
            if conn.get_connection_type() == "802-11-wireless" and not is_hotspot(conn)
        ]
        items: dict[str, WifiItem] = {}
        for dev in devs:
            # per-profile connection_valid(): filter_connections() returns an
            # empty list through PyGObject
            dev_conns = [conn for conn in wifi_conns if dev.connection_valid(conn)]
            for ap in dev.get_access_points():
                raw = nullable(ap.get_ssid())
                data = raw.get_data() if raw else None
                ssid = NM.utils_ssid_to_utf8(data) if data else None
                if not ssid:
                    continue
                cur = items.get(ssid)
                if cur and cur.ap and cur.ap.get_strength() >= ap.get_strength():
                    continue
                kind, sec = ap_security(ap)
                conns = [conn for conn in dev_conns if ap.connection_valid(conn)]
                conns.sort(
                    key=lambda x: x.get_setting_connection().get_timestamp(),
                    reverse=True,
                )
                items[ssid] = WifiItem(ssid, ap, dev, kind, sec, conns, hotspot=False)
            ac = nullable(dev.get_active_connection())
            conn = nullable(ac.get_connection()) if ac else None
            if ac and conn and conn.get_connection_type() == "802-11-wireless":
                ssid = connection_ssid(conn) or ac.get_id()
                item = items.get(ssid)
                if (
                    item is None
                ):  # hotspot, or a hidden network absent from the scan list
                    item = items[ssid] = WifiItem(
                        ssid,
                        nullable(dev.get_active_access_point()),
                        dev,
                        "psk"
                        if nullable(conn.get_setting_wireless_security())
                        else "open",
                        connection_security(conn),
                        [conn],
                        hotspot=is_hotspot(conn),
                    )
                item.ac = ac
        for ssid, item in items.items():
            item.pending = ssid in self._pending
        # active first, then saved networks, then by signal
        return sorted(
            items.values(),
            key=lambda it: (
                it.ac is None,
                not it.conns,
                -(it.ap.get_strength() if it.ap else 0),
                it.ssid.lower(),
            ),
        )

    def _proxy_info(self) -> ProxyInfo:
        """Proxy rules as the Exit group shows it."""
        w, st = self.proxy_watch, self.proxy_state
        active, stopping = bool(w and w.active), self._proxy_busy == "stopping"
        starting = self._proxy_busy == "starting" or bool(w and w.starting)
        pairs = [(r.app, px.exit_label(st, r.exit)) for r in st.rules]
        pairs.append(("everything else", px.exit_label(st, st.default)))
        return ProxyInfo(
            up=(active or starting) and not stopping,
            on=active and not starting and not stopping,
            going=stopping,
            crashed=bool(w and w.crashed),
            summary=px.summary(st),
            pairs=pairs,
        )

    def _proxy_running(self) -> bool:
        """sing-box is up, restarting or failed (a failed one may still hold the kill switch)."""
        w = self.proxy_watch
        return w is not None and w.state not in {None, "inactive"}

    def _sync_exit(self) -> None:
        c = self._nm()
        conns = [
            conn
            for conn in c.get_connections()
            if conn.get_connection_type() in VPN_TYPES
        ]
        conns.sort(key=lambda conn: conn.get_id().lower())  # fixed order: muscle memory
        acs = [
            ac
            for ac in c.get_active_connections()
            if ac.get_connection_type() in VPN_TYPES
        ]
        up = [
            ac
            for ac in acs
            if ac.get_state() in {AC_STATE.ACTIVATING, AC_STATE.ACTIVATED}
        ]
        going = [ac for ac in acs if ac not in up]
        proxy = self._proxy_info()
        if self._exit_target == "" and not acs and not proxy.up and not proxy.going:
            self._exit_target = None  # Off has taken effect
        self._exit.update(
            conns,
            active=up[0] if up else None,
            going=going,
            target=self._exit_target,
            failed=self._exit_failed,
            proxy=proxy,
        )

    def _sync_connections(self, c: NM.Client) -> None:
        active: dict[str, str] = {}
        for ac in c.get_active_connections():
            devs = ac.get_devices()
            active[ac.get_uuid()] = devs[0].get_iface() if devs else ac_name(ac)
        grouped: dict[str, list[NM.RemoteConnection]] = {
            title: [] for title, _ in CONN_GROUPS
        }
        for conn in c.get_connections():
            if hidden_connection(conn):
                continue
            ctype = conn.get_connection_type()
            title = next(
                (t for t, types in CONN_GROUPS if types and ctype in types), "Other"
            )
            grouped[title].append(conn)
        for title, (sec, lst) in self._conn_groups.items():
            conns = sorted(grouped[title], key=lambda x: x.get_id().lower())
            sec.set_visible(bool(conns))
            lst.sync([(x.get_uuid(), (x, active.get(x.get_uuid()))) for x in conns])

    # --- actions ---

    def _set_networking(self, *, on: bool) -> None:
        self.set_status("Enabling networking…" if on else "Disabling networking…")
        self.queue_sync(now=True)

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                _ = c.dbus_call_finish(res)
            except GLib.Error as e:
                # fast clicks: a request can find NM already where it asks
                if not e.matches(
                    NM.ManagerError.quark(), NM.ManagerError.ALREADYENABLEDORDISABLED
                ):
                    self._net_switch.done(ok=False)
                    self._fail("Networking", e)
                    self.queue_sync()
                    return
            self._net_switch.done(ok=True)
            self.set_status(None)
            self.queue_sync()

        self._nm().dbus_call(
            NM.DBUS_PATH,
            NM.DBUS_INTERFACE,
            "Enable",
            GLib.Variant("(b)", (on,)),
            None,
            -1,
            None,
            done,
        )

    def _set_wireless(self, *, on: bool) -> None:
        self.queue_sync(now=True)  # the list follows the switch at once

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                _ = c.dbus_set_property_finish(res)
                self._wifi_switch.done(ok=True)
            except GLib.Error as e:
                self._wifi_switch.done(ok=False)
                self._fail("Wi-Fi", e)
            self.queue_sync()

        self._nm().dbus_set_property(
            NM.DBUS_PATH,
            NM.DBUS_INTERFACE,
            "WirelessEnabled",
            GLib.Variant("b", on),
            -1,
            None,
            done,
        )

    def _start_scan(self, *, request: bool = True) -> None:
        """Placeholders until every Wi-Fi device reports a scan newer than now.
        request=False: NM scans by itself (the radio was just turned on)."""
        c = self.client
        devs = self._devices(NM.DeviceWifi) if c else []
        if c is None or not devs:
            return
        self._scan_since = NM.utils_get_timestamp_msec()
        self._scan_wait = {d.get_path() for d in devs}
        self._scanning = True
        self._scan_btn.set_sensitive(False)
        self._scan_btn.add_css_class("net-scanning")
        if self._scan_timer:
            _ = GLib.source_remove(self._scan_timer)
        self._scan_timer = GLib.timeout_add_seconds(SCAN_MAX_S, self._scan_timed_out)
        if request and c.wireless_get_enabled():

            def done(dev: NM.DeviceWifi, res: Gio.AsyncResult) -> None:
                try:
                    _ = dev.request_scan_finish(res)
                except GLib.Error:
                    # NM rate-limits scans: its list is fresh, nothing to wait for
                    self._scan_wait.discard(dev.get_path())
                    self.queue_sync()

            for dev in devs:
                dev.request_scan_async(None, done)
        self.queue_sync()  # placeholders in the free space

    def _scan_timed_out(self) -> bool:
        self._scan_timer = 0
        self._end_scan()
        return GLib.SOURCE_REMOVE

    def _end_scan(self, *, sync: bool = True) -> None:
        if self._scan_timer:
            _ = GLib.source_remove(self._scan_timer)
            self._scan_timer = 0
        self._scanning = False
        self._scan_wait = set()
        self._scan_btn.remove_css_class("net-scanning")
        if sync:
            self.queue_sync()

    def activate_profile(
        self,
        conn: NM.Connection | None,
        device: NM.Device | None,
        ap: NM.AccessPoint | None,
        name: str,
        *,
        on_activated: Callable[[NM.ActiveConnection], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
    ) -> None:
        """Activate a saved profile (conn None: NM picks one for the device)."""
        self.set_status(f"Connecting to {name}…")
        path = ap.get_path() if ap else None

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                ac = c.activate_connection_finish(res)
            except GLib.Error as e:
                self._fail(f"Could not connect to {name}", e)
                if on_failed:
                    on_failed(error_text(e))
                self.queue_sync()
                return
            self._follow(ac, name, on_activated, on_failed)

        self._nm().activate_connection_async(conn, device, path, None, done)

    def _follow(
        self,
        ac: NM.ActiveConnection,
        name: str,
        on_activated: Callable[[NM.ActiveConnection], None] | None = None,
        on_failed: Callable[[str], None] | None = None,
    ) -> None:
        """Report an activation's outcome on the status line."""
        devices = list(ac.get_devices())
        # Clone now: NM deletes a volatile profile when its activation fails
        profile = nullable(ac.get_connection())
        conn = NM.SimpleConnection.new_clone(profile) if profile else None
        reasons: list[int] = []

        def dev_changed(_dev: NM.Device, _new: int, _old: int, reason: int) -> None:
            if reason not in {NM.DeviceStateReason.NONE, NM.DeviceStateReason.UNKNOWN}:
                reasons.append(reason)

        dev_handlers = [(d, d.connect("state-changed", dev_changed)) for d in devices]

        def finish() -> None:
            # handler_disconnect: NM.Device.disconnect() would disconnect the device
            for d, h in dev_handlers:
                d.handler_disconnect(h)
            ac.handler_disconnect(handler)

        def changed(_ac: NM.ActiveConnection, state: int, reason: int) -> None:
            if state == AC_STATE.ACTIVATED:
                finish()
                self.set_status(f"Connected to {name}", ok=True)
                if on_activated:
                    on_activated(ac)
            elif state == AC_STATE.DEACTIVATED:
                finish()
                why = (
                    failure_text(reasons[-1], devices, conn)
                    if reasons
                    else ac_reason_text(reason)
                )
                self.set_status(f"Could not connect to {name}: {why}", error=True)
                if on_failed:
                    on_failed(why)
            self.queue_sync()

        handler = ac.connect("state-changed", changed)
        if ac.get_state() == AC_STATE.ACTIVATED:
            changed(ac, AC_STATE.ACTIVATED, 0)

    def _add_and_activate(
        self,
        conn: NM.Connection,
        device: NM.Device,
        ap: NM.AccessPoint | None,
        name: str,
        *,
        on_failed: Callable[[str], None],
        persist: Literal["volatile", "disk"] = "volatile",
        on_activated: Callable[[NM.ActiveConnection], None] | None = None,
    ) -> None:
        """Create and activate `conn`. A volatile profile is saved to disk
        only once it connects; NM itself deletes it if activation fails,
        so a wrong password never stays saved (even if the popup closes)."""
        self.set_status(f"Connecting to {name}…")
        self._pending[name] = True
        self.queue_sync()

        def saved(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                _ = rc.update2_finish(res)
            except GLib.Error as e:
                self._fail(f"Connected, but saving {name} failed", e)

        def activated(ac: NM.ActiveConnection) -> None:
            _ = self._pending.pop(name, None)
            rc = nullable(ac.get_connection())
            if persist == "volatile" and rc:
                rc.update2(None, NM.SettingsUpdate2Flags.TO_DISK, None, None, saved)
            if on_activated:
                on_activated(ac)

        def failed(why: str) -> None:
            _ = self._pending.pop(name, None)
            on_failed(why)

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                ac, _result = c.add_and_activate_connection2_finish(res)
            except GLib.Error as e:
                _ = self._pending.pop(name, None)
                self._fail(f"Could not connect to {name}", e)
                on_failed(error_text(e))
                self.queue_sync()
                return
            self._follow(ac, name, activated, failed)

        opts = GLib.Variant("a{sv}", {"persist": GLib.Variant("s", persist)})
        self._nm().add_and_activate_connection2(
            conn, device, ap.get_path() if ap else None, opts, None, done
        )

    def connect_new(self, row: WifiRow, item: WifiItem, password: str | None) -> None:
        conn = wifi_connection(item.ssid, item.kind, password)
        self._add_and_activate(
            conn,
            item.device,
            item.ap,
            item.ssid,
            on_failed=row.failed,
            on_activated=lambda _ac: row.reveal(None),
        )

    def connect_enterprise(
        self, row: WifiRow, item: WifiItem, values: EapValues, password: str | None
    ) -> None:
        conn = eap_connection(item.ssid, values, None if values["ask"] else password)
        self._add_and_activate(
            conn,
            item.device,
            item.ap,
            item.ssid,
            on_failed=row.failed,
            on_activated=lambda _ac: row.reveal(None),
        )

    def connect_hidden(
        self, form: HiddenForm, ssid: str, kind: str, password: str | None
    ) -> None:
        devs = self._devices(NM.DeviceWifi)
        if not devs:
            form.show_error("No Wi-Fi device")
            return
        form.close()
        self._show_page("main")
        conn = wifi_connection(ssid, kind, password, hidden=True)

        def failed(why: str) -> None:
            form.open()
            form.ssid.set_text(ssid)
            form.show_error(f"Not connected: {why}. {NOT_SAVED}")

        self._add_and_activate(conn, devs[0], None, ssid, on_failed=failed)

    def _open_hidden(self) -> None:
        self._hotspot.close()
        self._hidden.open()

    def _hotspot_profile(self) -> NM.RemoteConnection | None:
        """The "Hotspot" profile, reused like nmcli does instead of piling up copies."""
        return next(
            (
                x
                for x in self._nm().get_connections()
                if x.get_id() == HOTSPOT_ID and is_hotspot(x)
            ),
            None,
        )

    def _open_hotspot(self) -> None:
        self._hidden.close()
        self._hotspot.open(self._hotspot_profile() if self.client else None)

    def start_hotspot(
        self, form: HotspotForm, ssid: str, password: str, band: str
    ) -> None:
        devs = self._devices(NM.DeviceWifi)
        if not devs:
            form.show_error("No Wi-Fi device")
            return
        dev = devs[0]
        if not dev.get_capabilities() & NM.DeviceWifiCapabilities.AP:
            form.show_error(f"{dev.get_iface()} does not support access point mode")
            return
        conn = hotspot_connection(ssid, password, band, dev.get_iface())
        form.close()

        def failed(why: str) -> None:
            form.open()
            form.show_error(f"Hotspot failed: {why}")

        existing = self._hotspot_profile()
        if existing is None:
            self._add_and_activate(
                conn, dev, None, ssid, on_failed=failed, persist="disk"
            )
            return
        conn.get_setting_connection().set_property(
            NM.SETTING_CONNECTION_UUID, existing.get_uuid()
        )

        def updated(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                _ = rc.update2_finish(res)
            except GLib.Error as e:
                failed(error_text(e))
                return
            self.activate_profile(rc, dev, None, ssid)

        existing.update2(
            conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            NM.SettingsUpdate2Flags.TO_DISK,
            None,
            None,
            updated,
        )

    def select_exit(self, conn: Exit | None) -> None:
        """Off (None), a VPN profile or PROXY. Exits are exclusive: the current
        one goes down first, so two never hold routes at once."""
        if conn is None:
            self._exit_off()
        elif conn == PROXY:
            self._start_proxy()
        else:
            self._activate_vpn(conn)

    def _activate_vpn(self, conn: NM.RemoteConnection) -> None:
        name, uuid = conn.get_id(), conn.get_uuid()
        self._exit_target, self._exit_failed = uuid, None
        self._sync_exit()  # show the pick as connecting right away, not after the debounce

        def activated(_ac: NM.ActiveConnection) -> None:
            if self._exit_target == uuid:
                self._exit_target = None

        def failed(_why: str) -> None:
            if self._exit_target == uuid:
                self._exit_target, self._exit_failed = None, uuid
            self.queue_sync()

        def start() -> None:
            self.activate_profile(
                conn, None, None, name, on_activated=activated, on_failed=failed
            )

        def proxy_stopped(err: str | None = None) -> None:
            if err:
                failed(err)
            else:
                self._take_down_vpns(uuid, name, start, failed)

        if self._proxy_running():
            self._stop_proxy(proxy_stopped)
        else:
            proxy_stopped()

    def _take_down_vpns(
        self,
        keep: str | None,
        name: str,
        start: Callable[[], None],
        failed: Callable[[str], None],
    ) -> None:
        """Deactivate every VPN but `keep`, wait until NM has removed them,
        then start()."""
        client = self._nm()
        others = [
            ac
            for ac in client.get_active_connections()
            if ac.get_connection_type() in VPN_TYPES and ac.get_uuid() != keep
        ]
        if not others:
            start()
            return
        paths = {ac.get_path() for ac in others}
        self.set_status(
            f"Switching to {name}: disconnecting "
            f"{', '.join(ac_name(ac) for ac in others)}…"
        )
        state = _Teardown()

        def gone() -> bool:
            live = {ac.get_path() for ac in client.get_active_connections()}
            return not paths & live

        def removed() -> None:
            # runs from the removal signal and from each deactivate reply
            if not state.failed and not state.started and gone():
                state.started = True
                client.handler_disconnect(state.handler)
                start()

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                _ = c.deactivate_connection_finish(res)
            except GLib.Error as e:
                if not state.failed:
                    state.failed = True
                    c.handler_disconnect(state.handler)
                    self._fail(f"Not switching to {name}", e)
                    failed(error_text(e))
                return
            removed()

        state.handler = client.connect(
            "active-connection-removed", lambda *_: removed()
        )
        for ac in others:
            client.deactivate_connection_async(ac, None, done)

    def _exit_off(self) -> None:
        self._exit_target, self._exit_failed = "", None
        acs = [
            ac
            for ac in self._nm().get_active_connections()
            if ac.get_connection_type() in VPN_TYPES
        ]

        def failed() -> None:
            if self._exit_target == "":
                self._exit_target = None  # still connected: show it again

        def proxy_stopped(err: str | None) -> None:
            if err:
                failed()

        for ac in acs:
            self.deactivate(ac, failed)
        if self._proxy_running():
            self._stop_proxy(proxy_stopped)
        self._sync_exit()

    # --- Proxy rules ---

    def open_proxy_page(self) -> None:
        self._show_page("proxies")

    def _start_proxy(self) -> None:
        problem = px.usable_problem(self.proxy_state)
        if problem:
            self.open_proxy_page()
            self._proxy_page.show_msg(
                f"{problem}, then pick Proxy rules again", error=True
            )
            return
        if self.proxy_watch is not None and self.proxy_watch.installed is False:
            self.set_status(
                "Proxy rules need setup: pacman -S sing-box, then run install.sh",
                error=True,
            )
            self.queue_sync()  # the chip goes back to the current exit
            return
        self._exit_target, self._exit_failed = PROXY, None
        self._proxy_busy = "starting"
        self._sync_exit()

        def done(err: str | None) -> None:
            self._proxy_busy = None
            if self._exit_target == PROXY:
                self._exit_target = None
            if err:
                self._exit_failed = PROXY
                self.set_status(f"Proxy rules did not start: {err}", error=True)
            else:
                self.set_status(
                    f"Proxy rules on: {px.summary(self.proxy_state)}", ok=True
                )
            self.queue_sync()

        def start() -> None:
            self.set_status("Starting proxy rules…")
            px.apply(self.proxy_state, done)

        def failed(_why: str) -> None:
            self._proxy_busy = None
            if self._exit_target == PROXY:
                self._exit_target, self._exit_failed = None, PROXY
            self.queue_sync()

        self._take_down_vpns(None, "Proxy rules", start, failed)

    def _stop_proxy(self, then: Callable[[str | None], None]) -> None:
        self._proxy_busy = "stopping"
        self.set_status("Stopping proxy rules…")
        self.queue_sync()

        def done(err: str | None) -> None:
            self._proxy_busy = None
            if err:
                self.set_status(f"Could not stop proxy rules: {err}", error=True)
            else:
                self.set_status("Proxy rules off", ok=True)
            self.queue_sync()
            then(err)

        px.stop(done)

    def deactivate(
        self, ac: NM.ActiveConnection, on_failed: Callable[[], None] | None = None
    ) -> None:
        name = ac_name(ac)
        self.set_status(f"Disconnecting {name}…")

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                _ = c.deactivate_connection_finish(res)
                self.set_status(f"Disconnected {name}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not disconnect {name}", e)
                if on_failed:
                    on_failed()
            self.queue_sync()

        self._nm().deactivate_connection_async(ac, None, done)

    def disconnect_device(self, dev: NM.Device) -> None:
        self.set_status(f"Disconnecting {dev.get_iface()}…")

        def done(d: NM.Device, res: Gio.AsyncResult) -> None:
            try:
                _ = d.disconnect_finish(res)
                self.set_status(f"Disconnected {d.get_iface()}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not disconnect {d.get_iface()}", e)
            self.queue_sync()

        dev.disconnect_async(None, done)

    def delete(self, conn: NM.RemoteConnection) -> None:
        name = conn.get_id()

        def done(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                _ = rc.delete_finish(res)
                self.set_status(f"Deleted {name}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not delete {name}", e)
            self.queue_sync()

        conn.delete_async(None, done)

    def open_editor(self, conn: Exit | None) -> None:
        """The Edit page for Wi-Fi, Ethernet and WireGuard profiles, the Proxy
        rules page for PROXY. Other types (plugin VPNs, bridges, PPPoE, …)
        aren't editable here: no Edit is offered."""
        if conn == PROXY:
            self.open_proxy_page()
            return
        if conn is None or conn.get_connection_type() not in EDITABLE_TYPES:
            return
        page = self._stack.get_visible_child_name()
        self._editor_back = page if page and page != "edit" else self._editor_back
        self._editor.open(conn)
        self._stack.set_visible_child_name("edit")
        self.set_status(None)

    def _open_portal(self) -> None:
        """Any plain-http page gets redirected to the portal's login; NM's check
        URI is one (connectivity is only PORTAL while checks are enabled)."""
        uri = self.client.connectivity_check_get_uri() if self.client else None
        if not uri:
            return
        try:
            _ = Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as e:
            self._fail("Cannot open the login page", e)
            return
        self.quit()

    # --- WireGuard import / export ---

    def _file_dialog(self, title: str, save_name: str | None = None) -> Gtk.FileDialog:
        dialog = Gtk.FileDialog(title=title, modal=True)
        folder = WG_DIR if WG_DIR.is_dir() else Path.home()
        dialog.set_initial_folder(Gio.File.new_for_path(str(folder)))
        conf = Gtk.FileFilter(name="WireGuard configs (*.conf)")
        conf.add_pattern("*.conf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(conf)
        dialog.set_filters(filters)
        if save_name:
            dialog.set_initial_name(save_name)
        return dialog

    def _run_dialog(
        self, dialog: Gtk.FileDialog, on_path: Callable[[str], None], *, save: bool
    ) -> None:
        """Hide the overlay (it would cover the dialog) while a file dialog runs."""
        win = self.get_active_window()
        if win:
            win.set_visible(False)

        def done(d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            if win:
                win.set_visible(True)
            try:
                gfile = d.save_finish(res) if save else d.open_finish(res)
            except GLib.Error:
                return  # dismissed
            path = gfile.get_path() if gfile else None
            if path:
                on_path(path)

        if save:
            dialog.save(win, None, done)
        else:
            dialog.open(win, None, done)

    def _import_wireguard(self) -> None:
        dialog = self._file_dialog("Import WireGuard config")
        self._run_dialog(dialog, self.import_wireguard, save=False)

    def import_wireguard(self, path: str) -> None:
        """Import like `nmcli connection import type wireguard`, but never autoconnect."""
        try:
            conn = NM.conn_wireguard_import(path)
        except GLib.Error as e:
            self._fail(f"Cannot import {Path(path).name}", e)
            return
        name = conn.get_id()
        client = self._nm()
        if any(x.get_id() == name for x in client.get_connections()):
            self.set_status(
                f"A profile named {name} already exists: delete it first", error=True
            )
            return
        # VPNs are only ever connected by hand: autoconnect=no before the
        # profile exists, and autoconnect blocked while it is being added
        conn.get_setting_connection().props.autoconnect = False
        self.set_status(f"Importing {name}…")

        def done(c: NM.Client, res: Gio.AsyncResult) -> None:
            try:
                rc, _result = c.add_connection2_finish(res)
            except GLib.Error as e:
                self._fail(f"Cannot import {name}", e)
                return
            if rc.get_setting_connection().get_autoconnect():
                rc.get_setting_connection().props.autoconnect = False
                rc.commit_changes_async(
                    save_to_disk=True, cancellable=None, callback=None
                )
            self.set_status(f"Imported {name} (autoconnect off)", ok=True)
            self.queue_sync()

        client.add_connection2(
            conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            NM.SettingsAddConnection2Flags.TO_DISK
            | NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT,
            args=None,
            ignore_out_result=True,
            cancellable=None,
            callback=done,
        )

    def export_wireguard(self, conn: NM.RemoteConnection) -> None:
        iface = conn.get_setting_connection().get_interface_name() or conn.get_id()
        dialog = self._file_dialog(f"Export {conn.get_id()}", f"{iface}.conf")
        self._run_dialog(
            dialog, lambda path: self.write_wireguard(conn, path), save=True
        )

    def write_wireguard(
        self,
        conn: NM.RemoteConnection,
        path: str,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        """Fetch the private key and peer PSKs, then write a wg-quick .conf (0600)."""
        name = conn.get_id()

        def done(rc: NM.RemoteConnection, res: Gio.AsyncResult) -> None:
            try:
                secrets_ = rc.get_secrets_finish(res)
                full = NM.SimpleConnection.new_clone(rc)
                _ = full.update_secrets(NM.SETTING_WIREGUARD_SETTING_NAME, secrets_)
                write_private(path, wireguard_conf(full))
            except (GLib.Error, OSError) as e:
                self._fail(f"Cannot export {name}", e)
            else:
                self.set_status(f"Exported {name} to {path}", ok=True)
            if on_done:
                on_done()

        conn.get_secrets_async(NM.SETTING_WIREGUARD_SETTING_NAME, None, done)


def main() -> int:
    return NetworkPopup().run()
