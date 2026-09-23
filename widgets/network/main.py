#!/usr/bin/env python3
"""Network popup — GTK4 nm-applet replacement over libnm (NM 1.0 via PyGObject).

One NM.Client drives everything. Every NetworkManager call is async and the
UI follows client signals (plus a slow tick for signal strength and bitrates),
folded into one debounced sync that updates keyed rows in place, so open
password fields, details and confirmations survive updates.

Two pages in a Gtk.Stack: the applet menu (switches, wired, Wi-Fi, VPN) and
the saved-connections list (delete, hidden Wi-Fi, WireGuard import/export).
"""

import os, secrets, socket, subprocess, sys
_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _DIR)

from lib.copy_label import CopyLabel
from lib.widget_base import Gdk, Gtk, WidgetPopup

from gi.repository import Gio, GLib, GObject, Pango

from nmutil import (  # noqa: E402
    HOTSPOT_ID, ICON, NM, VPN_TYPES, ac_reason_text, ap_security, connection_security,
    connection_ssid, device_reason_text, error_text, freq_band, hidden_connection,
    hotspot_connection, ip_lines, is_hotspot, password_problem, relative_time,
    signal_glyph, vpn_place, wifi_connection, wireguard_conf, write_private,
)

SYNC_DELAY_MS = 150    # debounce for bursts of client signals
TICK_S = 3             # refresh for values NM changes without signals we watch
WG_DIR = os.path.expanduser("~/Dropbox/wireguard")
EDITOR = "nm-connection-editor"

AC_STATE = NM.ActiveConnectionState
HIDDEN_SECURITY = [("open", "None"), ("psk", "WPA/WPA2 Personal"), ("sae", "WPA3 Personal")]
CONN_GROUPS = [("Wi-Fi", ("802-11-wireless",)), ("Ethernet", ("802-3-ethernet",)),
               ("WireGuard / VPN", VPN_TYPES), ("Other", None)]


# --- small widgets ---

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


class Details(Gtk.Grid):
    """Name/value pairs of an active connection; values copy on click."""

    def __init__(self):
        super().__init__(column_spacing=12, row_spacing=2)
        self.add_css_class("net-details")
        self._keys = None
        self._values = []

    def update(self, pairs):
        keys = [k for k, _ in pairs]
        if keys != self._keys:
            while child := self.get_first_child():
                self.remove(child)
            self._values = []
            for i, key in enumerate(keys):
                name = label(key, "net-detail-key")
                name.set_valign(Gtk.Align.START)
                self.attach(name, 0, i, 1, 1)
                value = CopyLabel("net-detail-value")
                self.attach(value, 1, i, 1, 1)
                self._values.append(value)
            self._keys = keys
        for value, (_k, text) in zip(self._values, pairs):
            value.set_content(text)


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
        self.device = self.ac = None

    def update(self, dev):
        self.device, self.ac = dev, dev.get_active_connection()
        state = dev.get_state()
        name = self.ac.get_id() if self.ac else "Ethernet"
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
            self.details.update(connection_details(self.app.client, self.ac))
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
        self.error = label("", "net-form-error", ellipsize=False)
        self.error.set_wrap(True)
        self.error.set_visible(False)
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
                self.details.update(connection_details(self.app.client, ac))
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
        else:
            self.app.set_status(f"{item['security']} networks need {EDITOR}: use Advanced…", error=True)

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


class VpnChips(Gtk.Box):
    """VPNs are exclusive, so the section is one radio group: Off plus a chip
    per profile, in a fixed order. A click connects or switches, Off
    disconnects; the label line shows the state and toggles the details."""

    PER_LINE = 6

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.app = app
        line = hbox(6)
        line.add_css_class("net-section-row")
        line.append(label("VPN", "net-section"))
        self.state = label("", "net-vpn-state", hexpand=True, ellipsize=True)
        line.append(self.state)
        self.expand = glyph_button(ICON["expand"], "Details", self._toggle_details)
        line.append(self.expand)
        self.append(line)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                min_children_per_line=self.PER_LINE,
                                max_children_per_line=self.PER_LINE,
                                row_spacing=4, column_spacing=4)
        self.append(self.flow)
        self.details = Details()
        self.details.add_css_class("net-vpn-details")
        self.revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.NONE,
                                     child=self.details, visible=False)
        self.append(self.revealer)
        self._uuids = None
        self._selected = None  # uuid shown as selected by the last update
        self._chips = {}   # uuid (None: Off) -> ToggleButton
        self._handlers = {}

    def _rebuild(self, conns):
        self.flow.remove_all()
        self._chips, self._handlers = {}, {}
        group = None
        for conn in [None] + conns:
            chip = Gtk.ToggleButton(label=conn.get_id() if conn else "Off")
            chip.add_css_class("net-chip")
            if conn is None:
                chip.add_css_class("net-chip-off")
            else:
                chip.set_tooltip_text(vpn_place(conn.get_id()) or conn.get_id())
            if group:
                chip.set_group(group)
            group = group or chip
            uuid = conn.get_uuid() if conn else None
            self._handlers[uuid] = chip.connect("toggled", self._on_toggled, conn)
            self._chips[uuid] = chip
            self.flow.append(chip)
        self._uuids = [c.get_uuid() for c in conns]

    def update(self, conns, active, going, target, failed):
        """conns: profiles in display order; active: the AC shown as selected
        (activating or activated) or None; going: ACs being torn down;
        target: uuid the user just picked ("" for Off); failed: uuid whose
        last try failed."""
        if [c.get_uuid() for c in conns] != self._uuids:
            self._rebuild(conns)
        selected = None if target == "" else target or (active.get_uuid() if active else None)
        activated = active is not None and active.get_state() == AC_STATE.ACTIVATED \
            and active.get_uuid() == selected
        self._selected = selected
        going_uuids = {ac.get_uuid() for ac in going}
        if active is not None and active.get_uuid() != selected:
            going_uuids.add(active.get_uuid())  # still up, but on its way out
        for uuid, chip in self._chips.items():
            chip.handler_block(self._handlers[uuid])
            chip.set_active(uuid == selected)
            chip.handler_unblock(self._handlers[uuid])
            for cls, on in (("net-chip-connecting", uuid == selected and uuid and not activated),
                            ("net-chip-going", uuid in going_uuids and uuid != selected),
                            ("net-chip-failed", bool(uuid) and uuid == failed and uuid != selected)):
                (chip.add_css_class if on else chip.remove_css_class)(cls)
        name = next((c.get_id() for c in conns if c.get_uuid() == selected), None)
        if name is None and (active or going):
            self.state.set_text(f"disconnecting {(active or going[0]).get_id()}…")
        elif name is None:
            self.state.set_text("off")
        elif activated:
            place = vpn_place(name)
            self.state.set_text(f"{ICON['check']} {name}" + (f" · {place}" if place else ""))
        else:
            self.state.set_text(f"connecting {name}…")
        self.state.set_css_classes(["net-vpn-state"] + (["net-vpn-on"] if activated else []))
        self.expand.set_visible(activated)
        if activated and self.revealer.get_visible():
            self.details.update(connection_details(self.app.client, active))
        elif not activated:
            self.revealer.set_visible(False)
            self.revealer.set_reveal_child(False)
        self.expand.set_label(ICON["collapse" if self.revealer.get_visible() else "expand"])

    def _on_toggled(self, chip, conn):
        uuid = conn.get_uuid() if conn else None
        if not chip.get_active() or uuid == self._selected:
            return  # the group untoggles the previous chip; the current one is a no-op
        if conn is None:
            self.app.disconnect_vpns()
        else:
            self.app.activate_vpn(conn)

    def _toggle_details(self):
        show = not self.revealer.get_visible()
        self.revealer.set_visible(show)
        self.revealer.set_reveal_child(show)
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
        actions.append(glyph_button(ICON["edit"], f"Edit in {EDITOR}",
                                    lambda: self.app.edit(self.conn)))
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
        self.error = label("", "net-form-error")
        self.error.set_wrap(True)
        self.error.set_visible(False)
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
        self.error = label("", "net-form-error")
        self.error.set_wrap(True)
        self.error.set_visible(False)
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
        self._vpn_target = None  # uuid of the VPN being switched to, "" while turning off
        self._vpn_failed = None  # uuid of the VPN whose last activation failed
        self._scanning = False

    # --- UI ---

    def build_ui(self):
        self._container = vbox(8, "net-container")
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self._stack.set_vhomogeneous(False)
        self._stack.set_hhomogeneous(True)
        self._stack.add_named(self._build_main(), "main")
        self._stack.add_named(self._build_connections(), "connections")
        self._container.append(self._stack)

        self._status = label("", "net-status")
        self._status.set_wrap(True)
        self._status.set_max_width_chars(48)
        self._status.set_visible(False)
        self._container.append(self._status)

        NM.Client.new_async(None, self._on_client)
        return self._container

    def _build_main(self):
        page = vbox(8)
        header = hbox(6)
        header.append(label("Network", "net-title", hexpand=True))
        header.append(label("Networking", "net-switch-label"))
        self._net_switch = switch(self._set_networking)
        header.append(self._net_switch)
        page.append(header)

        self._offline = vbox(4)
        self._offline.set_halign(Gtk.Align.CENTER)
        self._offline.append(label(ICON["offline"], "net-error-icon", xalign=0.5))
        self._offline_msg = label("", "net-error-msg", xalign=0.5)
        self._offline.append(self._offline_msg)
        self._offline_hint = label("", "net-error-hint", xalign=0.5)
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
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, max_content_height=300)
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

        # VPN
        self._vpn = VpnChips(self)
        self._body.append(self._vpn)

        footer = hbox(4)
        footer.add_css_class("net-footer")
        footer.append(button("Connections", on_click=lambda: self._show_page("connections")))
        spacer = Gtk.Box(hexpand=True)
        footer.append(spacer)
        footer.append(button("Advanced…", tooltip=f"Open {EDITOR}", on_click=lambda: self.edit(None)))
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
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, max_content_height=480)
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
        if keyval == Gdk.KEY_q and isinstance(focus, Gtk.Text):
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
                    "notify::wireless-enabled", "notify::wireless-hardware-enabled"):
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
            self._show_offline("Networking is disabled", "")
        else:
            self._offline.set_visible(False)
            self._body.set_visible(True)
            self._sync_wired()
            self._sync_wifi()
            self._sync_vpn()
        if self._stack.get_visible_child_name() == "connections":
            self._sync_connections()
        return GLib.SOURCE_REMOVE

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

    def _sync_vpn(self):
        c = self.client
        conns = [conn for conn in c.get_connections() if conn.get_connection_type() in VPN_TYPES]
        conns.sort(key=lambda conn: conn.get_id().lower())  # fixed order: muscle memory
        acs = [ac for ac in c.get_active_connections() if ac.get_connection_type() in VPN_TYPES]
        up = [ac for ac in acs if ac.get_state() in (AC_STATE.ACTIVATING, AC_STATE.ACTIVATED)]
        going = [ac for ac in acs if ac not in up]
        if self._vpn_target == "" and not acs:
            self._vpn_target = None  # Off has taken effect
        self._vpn.set_visible(bool(conns))
        self._vpn.update(conns, up[0] if up else None, going, self._vpn_target, self._vpn_failed)

    def _sync_connections(self):
        active = {}
        for ac in self.client.get_active_connections():
            devs = ac.get_devices()
            active[ac.get_uuid()] = devs[0].get_iface() if devs else ac.get_id()
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

    def activate_vpn(self, conn):
        """VPNs are exclusive: take the active one down first (and wait until
        NM has removed it, so two tunnels never hold routes at once)."""
        name, uuid = conn.get_id(), conn.get_uuid()
        self._vpn_target, self._vpn_failed = uuid, None
        self._sync_vpn()  # show the pick as connecting right away, not after the debounce

        def activated(_ac):
            if self._vpn_target == uuid:
                self._vpn_target = None

        def failed(_why):
            if self._vpn_target == uuid:
                self._vpn_target, self._vpn_failed = None, uuid
            self.queue_sync()

        def start():
            self.activate(conn, None, None, name, activated, failed)

        others = [ac for ac in self.client.get_active_connections()
                  if ac.get_connection_type() in VPN_TYPES and ac.get_uuid() != uuid]
        if not others:
            start()
            return
        paths = {ac.get_path() for ac in others}
        self.set_status(f"Switching to {name}: disconnecting "
                        f"{', '.join(ac.get_id() for ac in others)}…")
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

    def disconnect_vpns(self):
        self._vpn_target, self._vpn_failed = "", None
        acs = [ac for ac in self.client.get_active_connections()
               if ac.get_connection_type() in VPN_TYPES]
        def failed():
            if self._vpn_target == "":
                self._vpn_target = None  # still connected: show it again
        for ac in acs:
            self.deactivate(ac, failed)
        self._sync_vpn()

    def deactivate(self, ac, on_failed=None):
        name = ac.get_id()
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

    def edit(self, conn):
        """Hand over to nm-connection-editor (phase 2 replaces it) and close."""
        args = [EDITOR] + ([f"--edit={conn.get_uuid()}"] if conn else [])
        try:
            subprocess.Popen(args, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self._fail(f"Cannot start {EDITOR}", e)
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
