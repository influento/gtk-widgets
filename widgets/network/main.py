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

import os, secrets, socket, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from lib.copy_label import CopyLabel, copyable
from lib.widget_base import Gdk, Gtk, VScroller, WidgetPopup

from gi.repository import Gio, GLib, GObject

from ui import (KeyedList, button, entry, error_label, glyph_button, hbox, label,  # noqa: E402
                section, switch, vbox)
from editor import EDITABLE_TYPES, EapForm, EditPage  # noqa: E402
from proxypage import ProxyPage  # noqa: E402
import proxy as px  # noqa: E402
from nmutil import (  # noqa: E402
    HOTSPOT_ID, ICON, NM, VPN_TYPES, ac_reason_text, ap_security, connection_security,
    connection_ssid, connectivity_problem, device_reason_text, eap_connection, eap_problem,
    error_text, freq_band,
    hidden_connection, hotspot_connection, ip_lines, is_hotspot, link_connection,
    password_problem, relative_time, signal_glyph, vpn_place, wifi_connection,
    wireguard_conf, write_private,
)

SYNC_DELAY_MS = 150    # debounce for bursts of client signals
TICK_S = 3             # refresh for values NM changes without signals we watch
WG_DIR = os.path.expanduser("~/Dropbox/wireguard")

AC_STATE = NM.ActiveConnectionState
PROXY = "proxy-rules"  # the Proxy rules chip's key (VPN chips use profile UUIDs)
HIDDEN_SECURITY = [("open", "None"), ("psk", "WPA/WPA2 Personal"), ("sae", "WPA3 Personal")]
CONN_GROUPS = [("Wi-Fi", ("802-11-wireless",)), ("Ethernet", ("802-3-ethernet",)),
               ("WireGuard / VPN", VPN_TYPES), ("Other", None)]


def ac_name(ac):
    """An active connection's name as its profile has it now: after a rename
    the AC's own id can lag behind the profile's changed signal."""
    conn = ac.get_connection()
    return conn.get_id() if conn else ac.get_id()


class Details(Gtk.Box):
    """Name/value pairs of an active connection (values copy on click), plus
    an Edit… link to its profile when on_edit is set."""

    def __init__(self, on_edit=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("net-details")
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=2)
        self.append(self.grid)
        self.on_edit = on_edit
        self._conn = None
        self.edit_btn = button("Edit…", on_click=lambda: self.on_edit(self._conn))
        self.edit_btn.set_halign(Gtk.Align.START)
        self.edit_btn.set_visible(False)
        self.append(self.edit_btn)
        self._keys = None
        self._values = []

    def update(self, pairs, conn=None):
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
        for value, (_k, text) in zip(self._values, pairs):
            value.set_content(text)
        self._conn = conn
        self.edit_btn.set_visible(conn is not None and self.on_edit is not None
                                  and conn.get_connection_type() in EDITABLE_TYPES)


def connection_details(client, ac):
    """(label, value) pairs for an active connection: addresses, DNS, link."""
    pairs = []
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
    conn = ac.get_connection()
    if isinstance(dev, NM.DeviceWifi):
        if dev.get_bitrate():
            pairs.append(("Bitrate", f"{dev.get_bitrate() / 1000:g} Mb/s"))
        ap = dev.get_active_access_point()
        if ap and ap.get_frequency():
            pairs.append(("Frequency", f"{ap.get_frequency()} MHz ({freq_band(ap.get_frequency())})"))
        if conn:
            pairs.append(("Security", connection_security(conn)))
    elif isinstance(dev, NM.DeviceEthernet) and dev.get_speed():
        pairs.append(("Speed", f"{dev.get_speed()} Mb/s"))
    elif isinstance(dev, NM.DeviceWireGuard):
        s_wg = conn.get_setting_by_name("wireguard") if conn else None
        if s_wg and s_wg.get_peers_len():
            peer = s_wg.get_peer(0)
            if peer.get_endpoint():
                pairs.append(("Endpoint", peer.get_endpoint()))
    if dev and dev.get_hw_address() and not isinstance(dev, NM.DeviceWireGuard):
        pairs.append(("MAC", dev.get_hw_address()))
    return pairs


# --- rows ---

class ExpandRow(Gtk.Box):
    """Rounded row: a header line plus a revealer for details or a form."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-row")
        self.head = hbox(10)
        self.append(self.head)
        self.revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.NONE)
        self.revealer.set_visible(False)  # no box spacing below the header while closed
        self.append(self.revealer)
        self.details = Details()

    def reveal(self, child):
        """Show `child` below the header (None hides)."""
        if child is not None:
            if self.revealer.get_child() is not child:
                self.revealer.set_child(child)
        self.revealer.set_reveal_child(child is not None)
        self.revealer.set_visible(child is not None)

    def revealed(self):
        return self.revealer.get_reveal_child() and self.revealer.get_child()


class DeviceRow(ExpandRow):
    """Wired device: state, Connect/Disconnect, details."""

    def __init__(self, app, _key):
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
        self.device = self.ac = None

    def update(self, dev):
        self.device, self.ac = dev, dev.get_active_connection()
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
        if active and self.revealed():
            self.details.update(connection_details(self.app.client, self.ac), self.ac.get_connection())
        elif not active:
            self.reveal(None)
        self.expand.set_label(ICON["collapse" if self.revealed() else "expand"])

    def _on_action(self):
        if self.ac:
            self.app.disconnect_device(self.device)
        else:
            self.app.activate(None, self.device, None, self.device.get_iface())

    def _toggle_details(self):
        self.reveal(None if self.revealed() else self.details)
        self.app.queue_sync()


class PasswordForm(Gtk.Box):
    """Inline password prompt for a new secured network."""

    def __init__(self, on_submit, on_cancel):
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

    def show_error(self, text):
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _submit(self):
        self._on_submit(self.entry.get_text())


class WifiRow(ExpandRow):
    """One SSID (strongest BSSID). Click: connect / reveal password / details."""

    def __init__(self, app, ssid):
        super().__init__()
        self.app, self.ssid = app, ssid
        self.item = None
        self.icon = label("", "net-row-icon")
        self.title = label(ssid, "net-row-title", hexpand=True, ellipsize=True)
        self.state = label("", "net-row-state")
        self.pct = label("", "net-pct")
        self.lock = label(ICON["lock"], "net-lock")
        self.lock.set_tooltip_text("")
        self.saved = label(ICON["saved"], "net-saved")
        self.saved.set_tooltip_text("Saved network")
        self.action = button("Disconnect", on_click=self._on_disconnect)
        for w in (self.icon, self.title, self.state, self.pct, self.lock, self.saved, self.action):
            self.head.append(w)
        self.head.set_cursor_from_name("pointer")
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self._on_click())
        self.head.add_controller(click)
        self.form = PasswordForm(self._on_password, lambda: self.reveal(None))
        self.eap_form = None  # built on first use: Enterprise networks only
        self.details.on_edit = app.open_editor

    def update(self, item):
        self.item = item
        ap, ac = item["ap"], item["ac"]
        hotspot = item["hotspot"]
        if hotspot:
            self.icon.set_text(ICON["hotspot"])
        else:
            self.icon.set_text(signal_glyph(ap.get_strength()) if ap else ICON["wifi"][0])
        self.pct.set_text(f"{ap.get_strength()}%" if ap and not hotspot else "")
        self.lock.set_visible(item["kind"] not in ("open", "owe"))
        self.lock.set_tooltip_text(item["security"])
        self.saved.set_visible(bool(item["conns"]) and not ac)
        self.action.set_visible(ac is not None)
        self.action.set_label("Stop" if hotspot else "Disconnect")
        state = ""
        if ac is not None:
            st = ac.get_state()
            state = ("hotspot" if hotspot else ICON["check"]) if st == AC_STATE.ACTIVATED else "connecting…"
        elif item["pending"]:
            state = "connecting…"
        self.state.set_text(state)
        if ac is not None:
            self.add_css_class("net-row-active")
            if self.revealed() is self.details:
                self.details.update(connection_details(self.app.client, ac), ac.get_connection())
        else:
            self.remove_css_class("net-row-active")
            if self.revealed() is self.details:
                self.reveal(None)

    def _on_click(self):
        item = self.item
        if item["ac"] is not None:
            self.reveal(None if self.revealed() else self.details)
            self.app.queue_sync()
        elif item["conns"]:
            self.app.activate(item["conns"][0], item["device"], item["ap"], self.ssid)
        elif item["kind"] in ("open", "owe"):
            self.app.connect_new(self, item, None)
        elif item["kind"] in ("psk", "sae"):
            if self.revealed() is self.form:
                self.reveal(None)
            else:
                self.form.show_error(None)
                self.reveal(self.form)
                self.form.entry.grab_focus()
        elif item["kind"] == "eap":
            if self.eap_form is None:
                self.eap_form = EnterpriseForm(self._on_enterprise, lambda: self.reveal(None))
            if self.revealed() is self.eap_form:
                self.reveal(None)
            else:
                self.eap_form.show_error(None)
                self.reveal(self.eap_form)
                self.eap_form.form.identity.grab_focus()
        else:
            self.app.set_status(f"{item['security']} networks aren't supported", error=True)

    def _on_enterprise(self, values, password):
        problem = eap_problem(values, password, False)
        if problem:
            self.eap_form.show_error(problem)
            return
        self.eap_form.show_error(None)
        self.app.connect_enterprise(self, self.item, values, password)

    def _on_password(self, password):
        problem = password_problem(self.item["kind"], password)
        if problem:
            self.form.show_error(problem)
            return
        self.form.show_error(None)
        self.app.connect_new(self, self.item, password)

    def _on_disconnect(self):
        self.app.deactivate(self.item["ac"])

    def failed(self, reason):
        """New-network activation failed: back to the password form with the reason."""
        if self.item and self.item["kind"] in ("psk", "sae"):
            self.form.show_error(f"Not connected: {reason}. The profile was not saved.")
            self.reveal(self.form)
        elif self.item and self.item["kind"] == "eap" and self.eap_form is not None:
            self.eap_form.show_error(f"Not connected: {reason}. The profile was not saved.")
            self.reveal(self.eap_form)


class EnterpriseForm(Gtk.Box):
    """Inline PEAP/TTLS form for a new WPA Enterprise network."""

    def __init__(self, on_submit, on_cancel):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.form = EapForm(lambda: None)
        self.append(self.form)
        self.error = error_label()
        self.append(self.error)
        buttons = hbox(4)
        buttons.set_halign(Gtk.Align.END)
        buttons.append(button("Cancel", on_click=on_cancel))
        buttons.append(button("Connect", "net-btn-accent",
                              on_click=lambda: on_submit(self.form.values(), self.form.password_value())))
        self.append(buttons)

    def show_error(self, text):
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))


class ExitChips(Gtk.Box):
    """The VPN and Proxy sections. Exits are exclusive: a chip per VPN profile
    in a fixed order, and Proxy rules (per-app routing through sing-box). A
    click on a chip connects or switches (the other exit goes down first), a
    click on the selected chip turns it off. Each title line shows its state,
    including when the other exit is the one on, and toggles the details."""

    PER_LINE = 6

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        titles = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)  # the states line up
        self.vpn = self._section("VPN", titles)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=self.PER_LINE,
                                max_children_per_line=self.PER_LINE,
                                row_spacing=4, column_spacing=4)
        self.append(self.flow)
        self.append(self.vpn["revealer"])
        self.proxy = self._section("Proxy", titles, glyph_button(
            ICON["settings"], "Proxy rules: proxies and apps", app.open_proxy_page))
        # Proxy rules on a line of its own: its longer label would widen every
        # chip of the homogeneous grid
        self.proxy_line = hbox(8)
        self.proxy_summary = label("", "net-row-subtitle", hexpand=True, ellipsize=True)
        self.proxy_line.append(self.proxy_summary)
        self.append(self.proxy_line)
        self.append(self.proxy["revealer"])
        self._profiles = None  # (uuid, name) per chip: a rename relabels and re-sorts
        self._selected = None  # key shown as selected by the last update
        self._chips = {}   # uuid or PROXY -> ToggleButton
        self._handlers = {}

    def _section(self, title, titles, *extra):
        """Title line (title, state, details toggle, extra) and a details revealer."""
        line = hbox(8, "net-section-row")
        name = label(title, "net-section")
        titles.add_widget(name)
        line.append(name)
        sec = {"line": line, "state": label("", "net-exit-state", hexpand=True, ellipsize=True),
               "details": Details(on_edit=self._edit)}
        line.append(sec["state"])
        sec["expand"] = glyph_button(ICON["expand"], "Details", lambda: self._toggle_details(sec))
        line.append(sec["expand"])
        for w in extra:
            line.append(w)
        self.append(line)
        sec["details"].add_css_class("net-exit-details")
        sec["revealer"] = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.NONE,
                                       child=sec["details"], visible=False)
        return sec

    def _rebuild(self, conns):
        # no toggle group: a group cannot turn its selected chip off, so update()
        # keeps the chips exclusive
        self.flow.remove_all()
        if PROXY in self._chips:
            self.proxy_line.remove(self._chips[PROXY])
        self._chips, self._handlers = {}, {}
        for conn in conns + [PROXY]:
            if conn is PROXY:
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

    def update(self, conns, active, going, target, failed, proxy):
        """conns: VPN profiles in display order; active: the VPN AC shown as
        selected (activating or activated) or None; going: VPN ACs being torn
        down; target: key the user just picked ("" for off); failed: key whose
        last try failed; proxy: Proxy rules state (up, on, going, crashed,
        summary, pairs)."""
        if [(c.get_uuid(), c.get_id()) for c in conns] != self._profiles:
            self._rebuild(conns)
        if target is not None:
            selected = target or None
        elif active is not None:
            selected = active.get_uuid()
        else:
            selected = PROXY if proxy["up"] else None
        if selected == PROXY:
            activated = proxy["on"]
        else:
            activated = active is not None and active.get_state() == AC_STATE.ACTIVATED \
                and active.get_uuid() == selected
        self._selected = selected
        going_keys = {ac.get_uuid() for ac in going}
        if active is not None and active.get_uuid() != selected:
            going_keys.add(active.get_uuid())  # still up, but on its way out
        if proxy["going"] or (proxy["up"] and selected != PROXY):
            going_keys.add(PROXY)
        self._chips[PROXY].set_tooltip_text(proxy["summary"])
        self.proxy_summary.set_text(proxy["summary"])
        for key, chip in self._chips.items():
            chip.handler_block(self._handlers[key])
            chip.set_active(key == selected)
            chip.handler_unblock(self._handlers[key])
            for cls, on in (("net-chip-connecting", key == selected and not activated),
                            ("net-chip-going", key in going_keys and key != selected),
                            ("net-chip-failed", key == failed and key != selected)):
                (chip.add_css_class if on else chip.remove_css_class)(cls)

        vpn_name = next((c.get_id() for c in conns if c.get_uuid() == selected), None)
        if vpn_name and activated:
            place = vpn_place(vpn_name)
            vpn = (f"connected · {vpn_name}" + (f", {place}" if place else ""), "on")
        elif vpn_name:
            vpn = (f"connecting · {vpn_name}…", None)
        elif active or going:
            vpn = (f"disconnecting · {ac_name(active or going[0])}…", None)
        elif selected == PROXY:
            vpn = ("off · Proxy rules is on" if activated else "off · Proxy rules is starting", None)
        else:
            vpn = ("off", None)
        if selected == PROXY:
            prx = (f"on · {proxy['summary']}", "on") if activated else ("starting…", None)
        elif PROXY in going_keys:
            prx = ("stopping…", None)
        elif proxy["crashed"]:
            prx = ("stopped", "bad")
        elif vpn_name and activated:
            prx = (f"off · {vpn_name} is on", None)
        else:
            prx = ("off", None)
        self.proxy_summary.set_visible(not (activated and selected == PROXY))  # the state says it
        self._show(self.vpn, vpn, bool(vpn_name) and activated,
                   lambda: (connection_details(self.app.client, active), active.get_connection()))
        self._show(self.proxy, prx, selected == PROXY and activated,
                   lambda: (proxy["pairs"], PROXY))

    def _show(self, sec, state, activated, details):
        text, tone = state
        sec["state"].set_text(text)
        sec["state"].set_css_classes(["net-exit-state"] + ([f"net-exit-{tone}"] if tone else []))
        sec["expand"].set_visible(activated)
        if activated and sec["revealer"].get_visible():
            sec["details"].update(*details())
        elif not activated:
            sec["revealer"].set_visible(False)
            sec["revealer"].set_reveal_child(False)
        sec["expand"].set_label(ICON["collapse" if sec["revealer"].get_visible() else "expand"])

    def _on_toggled(self, chip, conn):
        key = PROXY if conn is PROXY else conn.get_uuid()
        if chip.get_active() and key != self._selected:
            self.app.select_exit(conn)
        elif not chip.get_active() and key == self._selected:
            self.app.select_exit(None)  # a click on the selected chip turns it off

    def _edit(self, conn):
        if conn is PROXY:
            self.app.open_proxy_page()
        else:
            self.app.open_editor(conn)

    def _toggle_details(self, sec):
        show = not sec["revealer"].get_visible()
        sec["revealer"].set_visible(show)
        sec["revealer"].set_reveal_child(show)
        self.app.queue_sync()


class ConnRow(Gtk.Box):
    """Saved profile on the Connections page: name, interface, last used,
    export (WireGuard), edit and delete with inline confirmation."""

    def __init__(self, app, _uuid):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("net-row")
        self.app = app
        self.conn = None
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
        self.export = glyph_button(ICON["export"], "Export .conf",
                                   lambda: self.app.export_wireguard(self.conn))
        actions.append(self.export)
        self.edit_btn = glyph_button(ICON["edit"], "Edit", lambda: self.app.open_editor(self.conn))
        actions.append(self.edit_btn)
        actions.append(glyph_button(ICON["delete"], "Delete",
                                    lambda: self.stack.set_visible_child_name("confirm"),
                                    "net-delete-btn"))
        confirm = hbox(4)
        confirm.append(label("Delete?", "net-confirm"))
        confirm.append(button("Delete", "net-btn-danger", on_click=self._delete))
        confirm.append(button("Keep", on_click=lambda: self.stack.set_visible_child_name("actions")))
        self.stack.add_named(actions, "actions")
        self.stack.add_named(confirm, "confirm")
        self.append(self.stack)

    def update(self, data):
        self.conn, active_dev = data
        self.title.set_text(self.conn.get_id())
        s_con = self.conn.get_setting_connection()
        iface = active_dev or s_con.get_interface_name() or "any interface"
        used = "active now" if active_dev else f"used {relative_time(s_con.get_timestamp())}"
        if s_con.get_timestamp() == 0 and not active_dev:
            used = "never used"
        self.subtitle.set_text(f"{iface} · {used}")
        self.export.set_visible(self.conn.get_connection_type() == "wireguard")
        editable = self.conn.get_connection_type() in EDITABLE_TYPES
        self.edit_btn.set_sensitive(editable)
        self.edit_btn.set_tooltip_text("Edit" if editable else "Not editable here (nmcli)")

    def _delete(self):
        self.stack.set_visible_child_name("actions")
        self.app.delete(self.conn)


class HiddenForm(Gtk.Box):
    """SSID + security + password for a hidden network."""

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.app = app
        self.append(label("Hidden network", "net-form-title"))
        self.ssid = entry("Network name (SSID)", on_activate=self._submit)
        self.append(self.ssid)
        self.security = Gtk.DropDown.new_from_strings([t for _, t in HIDDEN_SECURITY])
        self.security.add_css_class("net-choice")
        self.security.set_selected(1)
        self.security.connect("notify::selected", lambda *_: self._sync_password())
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

    def open(self):
        self.ssid.set_text("")
        self.password.set_text("")
        self.show_error(None)
        self._sync_password()
        self.set_visible(True)
        self.ssid.grab_focus()

    def close(self):
        self.set_visible(False)

    def show_error(self, text):
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _kind(self):
        return HIDDEN_SECURITY[self.security.get_selected()][0]

    def _sync_password(self):
        self.password.set_visible(self._kind() != "open")

    def _submit(self):
        ssid, kind = self.ssid.get_text().strip(), self._kind()
        password = self.password.get_text() if kind != "open" else None
        if not ssid:
            self.show_error("Enter the network name")
            return
        if len(ssid.encode()) > 32:
            self.show_error("SSIDs are at most 32 bytes")
            return
        problem = password_problem(kind, password)
        if problem:
            self.show_error(problem)
            return
        self.show_error(None)
        self.app.connect_hidden(self, ssid, kind, password)


class HotspotForm(Gtk.Box):
    BANDS = [("bg", "2.4 GHz"), ("a", "5 GHz")]

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("net-form")
        self.app = app
        self.append(label("Create hotspot", "net-form-title"))
        self.ssid = entry("Network name (SSID)", on_activate=self._submit)
        self.append(self.ssid)
        self.password = entry("Password (8-63 characters)", secret=True, on_activate=self._submit)
        self.append(self.password)
        self.band = Gtk.DropDown.new_from_strings([t for _, t in self.BANDS])
        self.band.add_css_class("net-choice")
        self.append(self.band)
        warn = label("Starting a hotspot drops the current Wi-Fi connection "
                     "on cards with a single radio.", "net-form-warning")
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

    def open(self, existing=None):
        ssid, password, band = f"{socket.gethostname()}-hotspot", "", 0
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
        self.ssid.grab_focus()

    def close(self):
        self.set_visible(False)

    def show_error(self, text):
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))

    def _submit(self):
        ssid, password = self.ssid.get_text().strip(), self.password.get_text()
        if not ssid or len(ssid.encode()) > 32:
            self.show_error("Enter a network name of at most 32 bytes")
            return
        problem = password_problem("psk", password)
        if problem:
            self.show_error(problem)
            return
        self.app.start_hotspot(self, ssid, password, self.BANDS[self.band.get_selected()][0])


# --- popup ---

class NetworkPopup(WidgetPopup):
    def __init__(self):
        super().__init__(application_id="dev.dotfiles.network")
        self.client = None
        self._sync_id = self._tick_id = 0
        self._pending = {}       # ssid -> WifiRow for new networks being activated
        self._exit_target = None  # uuid or PROXY being switched to, "" while turning off
        self._exit_failed = None  # uuid or PROXY whose last start failed
        self.proxy_state = px.load_state()
        self.proxy_watch = None
        self._proxy_busy = None   # "starting" / "stopping" while the helper runs
        self._scanning = False

    # --- UI ---

    def build_ui(self):
        self._container = vbox(8, "net-container")
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self._stack.set_vhomogeneous(False)
        self._stack.set_hhomogeneous(True)
        self._stack.add_named(self._build_main(), "main")
        self._stack.add_named(self._build_connections(), "connections")
        self._editor = EditPage(self, lambda: self._show_page(self._editor_back))
        self._editor_back = "connections"
        self._stack.add_named(self._editor, "edit")
        self._proxy_page = ProxyPage(self, lambda: self._show_page("main"))
        self._stack.add_named(self._proxy_page, "proxies")
        self._container.append(self._stack)

        self._status = label("", "net-status")
        self._status.set_wrap(True)
        self._status.set_max_width_chars(48)
        self._status.set_visible(False)
        self._container.append(self._status)

        NM.Client.new_async(None, self._on_client)
        self.proxy_watch = px.ServiceWatch(lambda _w: self.queue_sync())
        return self._container

    def _build_main(self):
        page = vbox(8)
        header = hbox(6)
        header.append(label("Network", "net-title", hexpand=True))
        header.append(label("Networking", "net-switch-label"))
        self._net_switch = switch(self._set_networking)
        header.append(self._net_switch)
        page.append(header)

        # connectivity check result: captive portal, limited, none
        self._inet = hbox(8, "net-inet")
        self._inet_icon = label("", "net-inet-icon")
        self._inet.append(self._inet_icon)
        self._inet_msg = label("", "net-inet-msg", hexpand=True)
        self._inet_msg.set_wrap(True)
        self._inet.append(self._inet_msg)
        self._portal_btn = button("Sign in…", tooltip="Open the portal's login page",
                                  on_click=self._open_portal)
        self._inet.append(self._portal_btn)
        self._inet.set_visible(False)
        page.append(self._inet)

        self._offline = vbox(4)
        self._offline.set_halign(Gtk.Align.CENTER)
        self._offline.append(label(ICON["offline"], "net-error-icon", xalign=0.5))
        self._offline_msg = copyable(label("", "net-error-msg", xalign=0.5))
        self._offline.append(self._offline_msg)
        self._offline_hint = copyable(label("", "net-error-hint", xalign=0.5))
        self._offline.append(self._offline_hint)
        self._offline.set_visible(False)
        page.append(self._offline)

        self._body = vbox(8)
        page.append(self._body)

        # wired
        self._wired_section = section("Wired")
        self._body.append(self._wired_section)
        self._wired = KeyedList(lambda k: DeviceRow(self, k))
        self._body.append(self._wired)

        # Wi-Fi
        self._scan_btn = glyph_button(ICON["rescan"], "Rescan", self._rescan)
        self._wifi_switch = switch(self._set_wireless)
        self._wifi_section = section("Wi-Fi", self._scan_btn, self._wifi_switch)
        self._body.append(self._wifi_section)
        self._wifi_msg = label("", "net-empty")
        self._body.append(self._wifi_msg)
        self._wifi = KeyedList(lambda ssid: WifiRow(self, ssid))
        scroller = VScroller(300)
        scroller.set_child(self._wifi)
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

        # VPN and Proxy: one exclusive exit
        self._exit = ExitChips(self)
        self._body.append(self._exit)

        footer = hbox(4)
        footer.add_css_class("net-footer")
        footer.append(button("Connections", on_click=lambda: self._show_page("connections")))
        page.append(footer)
        return page

    def _build_connections(self):
        page = vbox(8)
        header = hbox(6)
        header.append(glyph_button(ICON["back"], "Back", lambda: self._show_page("main")))
        header.append(label("Connections", "net-title", hexpand=True))
        page.append(header)

        self._conn_groups = {}
        groups = vbox(8)
        for title, _types in CONN_GROUPS:
            sec = section(title)
            lst = KeyedList(lambda k: ConnRow(self, k))
            groups.append(sec)
            groups.append(lst)
            self._conn_groups[title] = (sec, lst)
        scroller = VScroller(480)
        scroller.set_child(groups)
        page.append(scroller)

        self._conn_hidden = HiddenForm(self)
        page.append(self._conn_hidden)
        add = hbox(4)
        add.add_css_class("net-footer")
        add.append(label("Add", "net-section"))
        add.append(button("Hidden Wi-Fi…", on_click=lambda: self._conn_hidden.open()))
        add.append(button("Import WireGuard…", on_click=self._import_wireguard))
        page.append(add)
        return page

    def _show_page(self, name):
        self._stack.set_visible_child_name(name)
        self.set_status(None)
        self.queue_sync()

    def set_status(self, text, error=False, ok=False):
        self._status.set_text(text or "")
        self._status.set_visible(bool(text))
        copyable(self._status, error)
        for cls, on in (("net-status-err", error), ("net-status-ok", ok)):
            if on:
                self._status.add_css_class(cls)
            else:
                self._status.remove_css_class(cls)

    def _fail(self, what, err):
        self.set_status(f"{what}: {error_text(err)}", error=True)

    def _on_key(self, controller, keyval, keycode, state):
        win = self.get_active_window()
        focus = win.get_focus() if win else None
        if keyval == Gdk.KEY_q and isinstance(focus, (Gtk.Text, Gtk.TextView)):
            return False
        return super()._on_key(controller, keyval, keycode, state)

    # --- client and signals ---

    def _on_client(self, _src, res):
        try:
            self.client = NM.Client.new_finish(res)
        except GLib.Error as e:
            self._show_offline("Cannot reach NetworkManager", error_text(e))
            return
        c = self.client
        for sig in ("device-added", "device-removed", "active-connection-added",
                    "active-connection-removed", "connection-added", "connection-removed",
                    "notify::nm-running", "notify::networking-enabled",
                    "notify::wireless-enabled", "notify::wireless-hardware-enabled",
                    "notify::connectivity", "notify::primary-connection"):
            c.connect(sig, self._on_client_signal)
        for dev in c.get_devices():
            self._watch_device(dev)
        for ac in c.get_active_connections():
            ac.connect("state-changed", lambda *_: self.queue_sync())
        for conn in c.get_connections():
            conn.connect("changed", lambda *_: self.queue_sync())
        self._tick_id = GLib.timeout_add_seconds(TICK_S, self._tick)
        self._sync()
        self._rescan(quiet=True)
        if c.connectivity_check_get_enabled():  # fresh result, not up to 5 min old
            c.check_connectivity_async(None, self._on_checked)

    def _on_checked(self, client, res):
        try:
            client.check_connectivity_finish(res)
        except GLib.Error:
            pass  # the property keeps NM's last result

    def _on_client_signal(self, _client, *args):
        obj = args[0] if args and isinstance(args[0], GObject.Object) else None
        if isinstance(obj, NM.Device):
            self._watch_device(obj)
        elif isinstance(obj, NM.ActiveConnection):
            obj.connect("state-changed", lambda *_: self.queue_sync())
        elif isinstance(obj, NM.RemoteConnection):
            obj.connect("changed", lambda *_: self.queue_sync())
        self.queue_sync()

    def _watch_device(self, dev):
        dev.connect("state-changed", lambda *_: self.queue_sync())
        if isinstance(dev, NM.DeviceWifi):
            for sig in ("access-point-added", "access-point-removed", "notify::active-access-point"):
                dev.connect(sig, lambda *_: self.queue_sync())

    def queue_sync(self):
        if not self._sync_id:
            self._sync_id = GLib.timeout_add(SYNC_DELAY_MS, self._sync)

    def _tick(self):
        self.queue_sync()
        return GLib.SOURCE_CONTINUE

    def do_shutdown(self):
        for sid in (self._sync_id, self._tick_id):
            if sid:
                GLib.source_remove(sid)
        self._sync_id = self._tick_id = 0
        Gtk.Application.do_shutdown(self)

    # --- sync ---

    def _show_offline(self, msg, hint):
        self._offline_msg.set_text(msg)
        self._offline_hint.set_text(hint)
        self._offline_hint.set_visible(bool(hint))
        self._offline.set_visible(True)
        self._body.set_visible(False)

    def _devices(self, cls):
        return [d for d in self.client.get_devices()
                if isinstance(d, cls) and d.get_managed() and d.is_real()]

    def _sync(self):
        self._sync_id = 0
        c = self.client
        if c is None:
            return GLib.SOURCE_REMOVE
        if not c.get_nm_running():
            self._net_switch.set_sensitive(False)
            self._show_offline("NetworkManager is not running", "systemctl start NetworkManager")
            return GLib.SOURCE_REMOVE
        networking = c.networking_get_enabled()
        self._net_switch.set_sensitive(True)
        self._net_switch.set_(networking)
        if not networking:
            self._inet.set_visible(False)
            self._show_offline("Networking is disabled", "")
        else:
            self._offline.set_visible(False)
            self._body.set_visible(True)
            self._sync_connectivity()
            self._sync_wired()
            self._sync_wifi()
            self._sync_exit()
        page = self._stack.get_visible_child_name()
        if page == "connections":
            self._sync_connections()
        elif page == "proxies":
            self._proxy_page.sync()
        elif page == "edit" and self._editor.remote is not None \
                and self._editor.remote not in c.get_connections():
            name = self._editor.remote.get_id()
            self._editor.remote = None
            self._show_page("connections")
            self.set_status(f"{name} was deleted", error=True)
        return GLib.SOURCE_REMOVE

    def _sync_connectivity(self):
        problem = connectivity_problem(self.client) if link_connection(self.client) else None
        self._inet.set_visible(problem is not None)
        if problem:
            kind, text = problem
            self._inet_icon.set_text(ICON["portal"] if kind == "portal" else ICON["limited"])
            self._inet_msg.set_text(text)
            self._portal_btn.set_visible(kind == "portal")

    def _sync_wired(self):
        devs = self._devices(NM.DeviceEthernet)
        self._wired_section.set_visible(bool(devs))
        self._wired.sync([(d.get_iface(), d) for d in devs])

    def _sync_wifi(self):
        c = self.client
        devs = self._devices(NM.DeviceWifi)
        enabled, hw = c.wireless_get_enabled(), c.wireless_hardware_get_enabled()
        visible = bool(devs)
        for w in (self._wifi_section, self._wifi_scroller, self._wifi_extra):
            w.set_visible(visible)
        self._wifi_switch.set_(enabled and hw)
        self._wifi_switch.set_sensitive(hw)
        self._scan_btn.set_sensitive(enabled and hw and not self._scanning)
        if not visible:
            self._wifi_msg.set_visible(False)
            return
        if not hw:
            msg = "Wi-Fi is blocked by a hardware switch"
        elif not enabled:
            msg = "Wi-Fi is off"
        else:
            msg = None
        if msg:
            self._wifi_msg.set_text(msg)
            self._wifi_msg.set_visible(True)
            self._wifi.sync([])
            self._wifi_extra.set_visible(False)
            return
        items = self._wifi_items(devs)
        self._wifi_msg.set_text("No networks found" if not items else "")
        self._wifi_msg.set_visible(not items)
        self._wifi.sync([(it["ssid"], it) for it in items])

    def _wifi_items(self, devs):
        """One item per SSID: strongest AP, saved profiles, active connection."""
        wifi_conns = [conn for conn in self.client.get_connections()
                      if conn.get_connection_type() == "802-11-wireless" and not is_hotspot(conn)]
        items = {}
        for dev in devs:
            # per-profile connection_valid(): filter_connections() returns an
            # empty list through PyGObject
            dev_conns = [conn for conn in wifi_conns if dev.connection_valid(conn)]
            for ap in dev.get_access_points():
                ssid = ap.get_ssid()
                ssid = NM.utils_ssid_to_utf8(ssid.get_data()) if ssid and ssid.get_data() else None
                if not ssid:
                    continue
                cur = items.get(ssid)
                if cur and cur["ap"].get_strength() >= ap.get_strength():
                    continue
                kind, sec = ap_security(ap)
                conns = [conn for conn in dev_conns if ap.connection_valid(conn)]
                conns.sort(key=lambda x: x.get_setting_connection().get_timestamp(), reverse=True)
                items[ssid] = {"ssid": ssid, "ap": ap, "device": dev, "kind": kind,
                               "security": sec, "conns": conns, "ac": None, "hotspot": False}
            ac = dev.get_active_connection()
            conn = ac.get_connection() if ac else None
            if conn and conn.get_connection_type() == "802-11-wireless":
                ssid = connection_ssid(conn) or ac.get_id()
                item = items.get(ssid)
                if item is None:  # hotspot, or a hidden network absent from the scan list
                    item = items[ssid] = {
                        "ssid": ssid, "ap": dev.get_active_access_point(), "device": dev,
                        "kind": "psk" if conn.get_setting_wireless_security() else "open",
                        "security": connection_security(conn), "conns": [conn], "ac": None,
                        "hotspot": is_hotspot(conn)}
                item["ac"] = ac
        for ssid, item in items.items():
            item["pending"] = ssid in self._pending
        # active first, then saved networks, then by signal
        return sorted(items.values(), key=lambda it: (
            it["ac"] is None, not it["conns"], -(it["ap"].get_strength() if it["ap"] else 0),
            it["ssid"].lower()))

    def _proxy_info(self):
        """Proxy rules as the Exit group shows it."""
        w, st = self.proxy_watch, self.proxy_state
        active, stopping = bool(w and w.active), self._proxy_busy == "stopping"
        starting = self._proxy_busy == "starting" or bool(w and w.starting)
        pairs = [(r["app"], px.exit_label(st, r["exit"])) for r in st["rules"]]
        pairs.append(("everything else", px.exit_label(st, st["default"])))
        return {"up": (active or starting) and not stopping,
                "on": active and not starting and not stopping, "going": stopping,
                "crashed": bool(w and w.crashed),
                "summary": px.summary(st), "pairs": pairs}

    def _proxy_running(self):
        """sing-box is up, restarting or failed (a failed one may still hold the kill switch)."""
        w = self.proxy_watch
        return w is not None and w.state not in (None, "inactive")

    def _sync_exit(self):
        c = self.client
        conns = [conn for conn in c.get_connections() if conn.get_connection_type() in VPN_TYPES]
        conns.sort(key=lambda conn: conn.get_id().lower())  # fixed order: muscle memory
        acs = [ac for ac in c.get_active_connections() if ac.get_connection_type() in VPN_TYPES]
        up = [ac for ac in acs if ac.get_state() in (AC_STATE.ACTIVATING, AC_STATE.ACTIVATED)]
        going = [ac for ac in acs if ac not in up]
        proxy = self._proxy_info()
        if self._exit_target == "" and not acs and not proxy["up"] and not proxy["going"]:
            self._exit_target = None  # Off has taken effect
        self._exit.update(conns, up[0] if up else None, going, self._exit_target,
                          self._exit_failed, proxy)

    def _sync_connections(self):
        active = {}
        for ac in self.client.get_active_connections():
            devs = ac.get_devices()
            active[ac.get_uuid()] = devs[0].get_iface() if devs else ac_name(ac)
        grouped = {title: [] for title, _ in CONN_GROUPS}
        for conn in self.client.get_connections():
            if hidden_connection(conn):
                continue
            ctype = conn.get_connection_type()
            title = next((t for t, types in CONN_GROUPS if types and ctype in types), "Other")
            grouped[title].append(conn)
        for title, (sec, lst) in self._conn_groups.items():
            conns = sorted(grouped[title], key=lambda x: x.get_id().lower())
            sec.set_visible(bool(conns))
            lst.sync([(x.get_uuid(), (x, active.get(x.get_uuid()))) for x in conns])

    # --- actions ---

    def _set_networking(self, on):
        self.set_status("Enabling networking…" if on else "Disabling networking…")

        def done(c, res):
            try:
                c.dbus_call_finish(res)
                self.set_status(None)
            except GLib.Error as e:
                self._fail("Networking", e)
            self.queue_sync()
        self.client.dbus_call(NM.DBUS_PATH, NM.DBUS_INTERFACE, "Enable",
                              GLib.Variant("(b)", (on,)), None, -1, None, done)

    def _set_wireless(self, on):
        def done(c, res):
            try:
                c.dbus_set_property_finish(res)
            except GLib.Error as e:
                self._fail("Wi-Fi", e)
            self.queue_sync()
        self.client.dbus_set_property(NM.DBUS_PATH, NM.DBUS_INTERFACE, "WirelessEnabled",
                                      GLib.Variant("b", on), -1, None, done)

    def _rescan(self, quiet=False):
        devs = self._devices(NM.DeviceWifi) if self.client else []
        if not devs or not self.client.wireless_get_enabled():
            return
        self._scanning = True
        self._scan_btn.set_sensitive(False)
        self._scan_btn.add_css_class("net-scanning")

        def done(dev, res):
            try:
                dev.request_scan_finish(res)
            except GLib.Error:
                pass  # NM rate-limits scans; the list still follows its own scans
        for dev in devs:
            dev.request_scan_async(None, done)

        def finished():
            self._scanning = False
            self._scan_btn.remove_css_class("net-scanning")
            self.queue_sync()
            return GLib.SOURCE_REMOVE
        GLib.timeout_add_seconds(4, finished)

    def activate(self, conn, device, ap, name, on_activated=None, on_failed=None):
        """Activate a saved profile (conn None: NM picks one for the device)."""
        self.set_status(f"Connecting to {name}…")
        path = ap.get_path() if ap else None

        def done(c, res):
            try:
                ac = c.activate_connection_finish(res)
            except GLib.Error as e:
                self._fail(f"Could not connect to {name}", e)
                if on_failed:
                    on_failed(error_text(e))
                self.queue_sync()
                return
            self._follow(ac, name, on_activated, on_failed)
        self.client.activate_connection_async(conn, device, path, None, done)

    def _follow(self, ac, name, on_activated=None, on_failed=None):
        """Report an activation's outcome on the status line."""
        devices = list(ac.get_devices())
        reasons = []

        def dev_changed(_dev, _new, _old, reason):
            if reason not in (NM.DeviceStateReason.NONE, NM.DeviceStateReason.UNKNOWN):
                reasons.append(reason)
        dev_handlers = [(d, d.connect("state-changed", dev_changed)) for d in devices]

        def finish():
            # handler_disconnect: NM.Device.disconnect() would disconnect the device
            for d, h in dev_handlers:
                d.handler_disconnect(h)
            ac.handler_disconnect(handler)

        def changed(_ac, state, reason):
            if state == AC_STATE.ACTIVATED:
                finish()
                self.set_status(f"Connected to {name}", ok=True)
                if on_activated:
                    on_activated(ac)
            elif state == AC_STATE.DEACTIVATED:
                finish()
                why = device_reason_text(reasons[-1]) if reasons else ac_reason_text(reason)
                self.set_status(f"Could not connect to {name}: {why}", error=True)
                if on_failed:
                    on_failed(why)
            self.queue_sync()
        handler = ac.connect("state-changed", changed)
        if ac.get_state() == AC_STATE.ACTIVATED:
            changed(ac, AC_STATE.ACTIVATED, 0)

    def _add_and_activate(self, conn, device, ap, name, on_failed, persist="volatile",
                          on_activated=None):
        """Create and activate `conn`. A volatile profile is saved to disk
        only once it connects; NM itself deletes it if activation fails,
        so a wrong password never stays saved (even if the popup closes)."""
        self.set_status(f"Connecting to {name}…")
        self._pending[name] = True
        self.queue_sync()

        def saved(rc, res):
            try:
                rc.update2_finish(res)
            except GLib.Error as e:
                self._fail(f"Connected, but saving {name} failed", e)

        def activated(ac):
            self._pending.pop(name, None)
            rc = ac.get_connection()
            if persist == "volatile" and rc:
                rc.update2(None, NM.SettingsUpdate2Flags.TO_DISK, None, None, saved)
            if on_activated:
                on_activated(ac)

        def failed(why):
            self._pending.pop(name, None)
            on_failed(why)

        def done(c, res):
            try:
                ac, _result = c.add_and_activate_connection2_finish(res)
            except GLib.Error as e:
                self._pending.pop(name, None)
                self._fail(f"Could not connect to {name}", e)
                on_failed(error_text(e))
                self.queue_sync()
                return
            self._follow(ac, name, activated, failed)
        opts = GLib.Variant("a{sv}", {"persist": GLib.Variant("s", persist)})
        self.client.add_and_activate_connection2(
            conn, device, ap.get_path() if ap else None, opts, None, done)

    def connect_new(self, row, item, password):
        conn = wifi_connection(item["ssid"], item["kind"], password)
        self._add_and_activate(conn, item["device"], item["ap"], item["ssid"], row.failed,
                               on_activated=lambda _ac: row.reveal(None))

    def connect_enterprise(self, row, item, values, password):
        conn = eap_connection(item["ssid"], values, None if values["ask"] else password)
        self._add_and_activate(conn, item["device"], item["ap"], item["ssid"], row.failed,
                               on_activated=lambda _ac: row.reveal(None))

    def connect_hidden(self, form, ssid, kind, password):
        devs = self._devices(NM.DeviceWifi)
        if not devs:
            form.show_error("No Wi-Fi device")
            return
        form.close()
        self._show_page("main")
        conn = wifi_connection(ssid, kind, password, hidden=True)

        def failed(why):
            form.open()
            form.ssid.set_text(ssid)
            form.show_error(f"Not connected: {why}. The profile was not saved.")
        self._add_and_activate(conn, devs[0], None, ssid, failed)

    def _open_hidden(self):
        self._hotspot.close()
        self._hidden.open()

    def _open_hotspot(self):
        self._hidden.close()
        existing = next((x for x in self.client.get_connections()
                         if x.get_id() == HOTSPOT_ID and is_hotspot(x)), None) if self.client else None
        self._hotspot.open(existing)

    def start_hotspot(self, form, ssid, password, band):
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

        def failed(why):
            form.open()
            form.show_error(f"Hotspot failed: {why}")
        # reuse the "Hotspot" profile like nmcli does, instead of piling up copies
        existing = next((x for x in self.client.get_connections()
                         if x.get_id() == HOTSPOT_ID and is_hotspot(x)), None)
        if existing is None:
            self._add_and_activate(conn, dev, None, ssid, failed, persist="disk")
            return
        conn.get_setting_connection().set_property(NM.SETTING_CONNECTION_UUID, existing.get_uuid())

        def updated(rc, res):
            try:
                rc.update2_finish(res)
            except GLib.Error as e:
                failed(error_text(e))
                return
            self.activate(rc, dev, None, ssid)
        existing.update2(conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
                         NM.SettingsUpdate2Flags.TO_DISK, None, None, updated)

    def select_exit(self, conn):
        """Off (None), a VPN profile or PROXY. Exits are exclusive: the current
        one goes down first, so two never hold routes at once."""
        if conn is None:
            self._exit_off()
        elif conn is PROXY:
            self._start_proxy()
        else:
            self._activate_vpn(conn)

    def _activate_vpn(self, conn):
        name, uuid = conn.get_id(), conn.get_uuid()
        self._exit_target, self._exit_failed = uuid, None
        self._sync_exit()  # show the pick as connecting right away, not after the debounce

        def activated(_ac):
            if self._exit_target == uuid:
                self._exit_target = None

        def failed(_why):
            if self._exit_target == uuid:
                self._exit_target, self._exit_failed = None, uuid
            self.queue_sync()

        def start():
            self.activate(conn, None, None, name, activated, failed)

        def proxy_stopped(err=None):
            if err:
                failed(err)
            else:
                self._take_down_vpns(uuid, name, start, failed)
        if self._proxy_running():
            self._stop_proxy(proxy_stopped)
        else:
            proxy_stopped()

    def _take_down_vpns(self, keep, name, start, failed):
        """Deactivate every VPN but `keep`, wait until NM has removed them,
        then start()."""
        others = [ac for ac in self.client.get_active_connections()
                  if ac.get_connection_type() in VPN_TYPES and ac.get_uuid() != keep]
        if not others:
            start()
            return
        paths = {ac.get_path() for ac in others}
        self.set_status(f"Switching to {name}: disconnecting "
                        f"{', '.join(ac_name(ac) for ac in others)}…")
        state = {"failed": False, "started": False, "handler": 0}

        def gone():
            live = {ac.get_path() for ac in self.client.get_active_connections()}
            return not paths & live

        def removed(*_):
            # runs from the removal signal and from each deactivate reply
            if not state["failed"] and not state["started"] and gone():
                state["started"] = True
                self.client.handler_disconnect(state["handler"])
                start()

        def done(c, res):
            try:
                c.deactivate_connection_finish(res)
            except GLib.Error as e:
                if not state["failed"]:
                    state["failed"] = True
                    c.handler_disconnect(state["handler"])
                    self._fail(f"Not switching to {name}", e)
                    failed(error_text(e))
                return
            removed()
        state["handler"] = self.client.connect("active-connection-removed", removed)
        for ac in others:
            self.client.deactivate_connection_async(ac, None, done)

    def _exit_off(self):
        self._exit_target, self._exit_failed = "", None
        acs = [ac for ac in self.client.get_active_connections()
               if ac.get_connection_type() in VPN_TYPES]

        def failed(*_):
            if self._exit_target == "":
                self._exit_target = None  # still connected: show it again
        for ac in acs:
            self.deactivate(ac, failed)
        if self._proxy_running():
            self._stop_proxy(lambda err: failed() if err else None)
        self._sync_exit()

    # --- Proxy rules ---

    def open_proxy_page(self):
        self._show_page("proxies")

    def _start_proxy(self):
        problem = px.usable_problem(self.proxy_state)
        if problem:
            self.open_proxy_page()
            self._proxy_page.show_msg(f"{problem}, then pick Proxy rules again", error=True)
            return
        if self.proxy_watch is not None and self.proxy_watch.installed is False:
            self.set_status("Proxy rules need setup: pacman -S sing-box, then run install.sh",
                            error=True)
            self.queue_sync()  # the chip goes back to the current exit
            return
        self._exit_target, self._exit_failed = PROXY, None
        self._proxy_busy = "starting"
        self._sync_exit()

        def done(err):
            self._proxy_busy = None
            if self._exit_target == PROXY:
                self._exit_target = None
            if err:
                self._exit_failed = PROXY
                self.set_status(f"Proxy rules did not start: {err}", error=True)
            else:
                self.set_status(f"Proxy rules on: {px.summary(self.proxy_state)}", ok=True)
            self.queue_sync()

        def start():
            self.set_status("Starting proxy rules…")
            px.apply(self.proxy_state, done)

        def failed(_why):
            self._proxy_busy = None
            if self._exit_target == PROXY:
                self._exit_target, self._exit_failed = None, PROXY
            self.queue_sync()
        self._take_down_vpns(None, "Proxy rules", start, failed)

    def _stop_proxy(self, then):
        self._proxy_busy = "stopping"
        self.set_status("Stopping proxy rules…")
        self.queue_sync()

        def done(err):
            self._proxy_busy = None
            if err:
                self.set_status(f"Could not stop proxy rules: {err}", error=True)
            else:
                self.set_status("Proxy rules off", ok=True)
            self.queue_sync()
            then(err)
        px.stop(done)

    def deactivate(self, ac, on_failed=None):
        name = ac_name(ac)
        self.set_status(f"Disconnecting {name}…")

        def done(c, res):
            try:
                c.deactivate_connection_finish(res)
                self.set_status(f"Disconnected {name}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not disconnect {name}", e)
                if on_failed:
                    on_failed()
            self.queue_sync()
        self.client.deactivate_connection_async(ac, None, done)

    def disconnect_device(self, dev):
        self.set_status(f"Disconnecting {dev.get_iface()}…")

        def done(d, res):
            try:
                d.disconnect_finish(res)
                self.set_status(f"Disconnected {d.get_iface()}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not disconnect {d.get_iface()}", e)
            self.queue_sync()
        dev.disconnect_async(None, done)

    def delete(self, conn):
        name = conn.get_id()

        def done(rc, res):
            try:
                rc.delete_finish(res)
                self.set_status(f"Deleted {name}", ok=True)
            except GLib.Error as e:
                self._fail(f"Could not delete {name}", e)
            self.queue_sync()
        conn.delete_async(None, done)

    def open_editor(self, conn):
        """The Edit page for Wi-Fi, Ethernet and WireGuard profiles. Other types
        (plugin VPNs, bridges, PPPoE, …) aren't editable here: no Edit is offered."""
        if conn is None or conn.get_connection_type() not in EDITABLE_TYPES:
            return
        page = self._stack.get_visible_child_name()
        self._editor_back = page if page != "edit" else self._editor_back
        self._editor.open(conn)
        self._stack.set_visible_child_name("edit")
        self.set_status(None)

    def _open_portal(self):
        """Any plain-http page gets redirected to the portal's login; NM's check
        URI is one (connectivity is only PORTAL while checks are enabled)."""
        uri = self.client.connectivity_check_get_uri() if self.client else None
        if not uri:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as e:
            self._fail("Cannot open the login page", e)
            return
        self.quit()

    # --- WireGuard import / export ---

    def _file_dialog(self, title, save_name=None):
        dialog = Gtk.FileDialog(title=title, modal=True)
        folder = WG_DIR if os.path.isdir(WG_DIR) else os.path.expanduser("~")
        dialog.set_initial_folder(Gio.File.new_for_path(folder))
        conf = Gtk.FileFilter(name="WireGuard configs (*.conf)")
        conf.add_pattern("*.conf")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(conf)
        dialog.set_filters(filters)
        if save_name:
            dialog.set_initial_name(save_name)
        return dialog

    def _hidden_while(self, run, finish, on_path):
        """Hide the overlay (it would cover the dialog) while a file dialog runs."""
        win = self.get_active_window()
        if win:
            win.set_visible(False)

        def done(dialog, res):
            if win:
                win.set_visible(True)
            try:
                gfile = finish(dialog, res)
            except GLib.Error:
                return  # dismissed
            if gfile and gfile.get_path():
                on_path(gfile.get_path())
        run(win, done)

    def _import_wireguard(self):
        dialog = self._file_dialog("Import WireGuard config")
        self._hidden_while(lambda w, cb: dialog.open(w, None, cb),
                           lambda d, r: d.open_finish(r), self.import_wireguard)

    def import_wireguard(self, path):
        """Import like `nmcli connection import type wireguard`, but never autoconnect."""
        try:
            conn = NM.conn_wireguard_import(path)
        except GLib.Error as e:
            self._fail(f"Cannot import {os.path.basename(path)}", e)
            return
        name = conn.get_id()
        if any(x.get_id() == name for x in self.client.get_connections()):
            self.set_status(f"A profile named {name} already exists: delete it first", error=True)
            return
        # VPNs are only ever connected by hand: autoconnect=no before the
        # profile exists, and autoconnect blocked while it is being added
        conn.get_setting_connection().set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)
        self.set_status(f"Importing {name}…")

        def done(c, res):
            try:
                rc, _result = c.add_connection2_finish(res)
            except GLib.Error as e:
                self._fail(f"Cannot import {name}", e)
                return
            if rc.get_setting_connection().get_autoconnect():
                rc.get_setting_connection().set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)
                rc.commit_changes_async(True, None, None)
            self.set_status(f"Imported {name} (autoconnect off)", ok=True)
            self.queue_sync()
        self.client.add_connection2(
            conn.to_dbus(NM.ConnectionSerializationFlags.ALL),
            NM.SettingsAddConnection2Flags.TO_DISK | NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT,
            None, True, None, done)

    def export_wireguard(self, conn):
        iface = conn.get_setting_connection().get_interface_name() or conn.get_id()
        dialog = self._file_dialog(f"Export {conn.get_id()}", f"{iface}.conf")
        self._hidden_while(lambda w, cb: dialog.save(w, None, cb),
                           lambda d, r: d.save_finish(r),
                           lambda path: self.write_wireguard(conn, path))

    def write_wireguard(self, conn, path, on_done=None):
        """Fetch the private key and peer PSKs, then write a wg-quick .conf (0600)."""
        name = conn.get_id()

        def done(rc, res):
            try:
                secrets_ = rc.get_secrets_finish(res)
                full = NM.SimpleConnection.new_clone(rc)
                full.update_secrets(NM.SETTING_WIREGUARD_SETTING_NAME, secrets_)
                write_private(path, wireguard_conf(full))
            except (GLib.Error, OSError) as e:
                self._fail(f"Cannot export {name}", e)
            else:
                self.set_status(f"Exported {name} to {path}", ok=True)
            if on_done:
                on_done()
        conn.get_secrets_async(NM.SETTING_WIREGUARD_SETTING_NAME, None, done)


if __name__ == "__main__":
    NetworkPopup().run()
