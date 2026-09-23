"""Edit page of the network popup: settings of one saved Wi-Fi, Ethernet or
WireGuard profile (general, Wi-Fi, security, MAC, Ethernet, IPv4/IPv6, routes,
WireGuard interface and peers). Everything else stays in nm-connection-editor.

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

import base64, shutil, socket, subprocess

from lib.widget_base import Gtk, pass_wheel

from gi.repository import GLib

from nmutil import (  # noqa: E402
    EAP_INNER, EAP_METHODS, NM, VPN_TYPES, apply_eap, connection_security, eap_problem,
    eap_values, error_text, freq_band, mac_problem, parse_cidr, parse_ip, password_problem,
    connection_ssid, reapply_refusal_text, ssid_text, wg_key_problem,
)
from ui import button, glyph_button, hbox, label, vbox  # noqa: E402

EDITABLE_TYPES = ("802-11-wireless", "802-3-ethernet", "wireguard")
SECRET_SETTINGS = ("802-11-wireless-security", "802-1x", "wireguard")
FAMILIES = ((socket.AF_INET, "ipv4", "IPv4"), (socket.AF_INET6, "ipv6", "IPv6"))
IP_METHODS = {
    "ipv4": [("auto", "Automatic (DHCP)"), ("manual", "Manual"), ("link-local", "Link-local"),
             ("disabled", "Disabled")],
    "ipv6": [("auto", "Automatic"), ("dhcp", "DHCP only"), ("manual", "Manual"),
             ("link-local", "Link-local"), ("ignore", "Ignore"), ("disabled", "Disabled")],
}
METERED = [(NM.Metered.UNKNOWN, "Automatic"), (NM.Metered.YES, "Yes"), (NM.Metered.NO, "No")]
BANDS = [(None, "Automatic"), ("bg", "2.4 GHz"), ("a", "5 GHz")]
MAC_MODES = [(None, "Default"), ("permanent", "Permanent"), ("random", "Random (new every connect)"),
             ("stable", "Stable (fixed per network)"), ("preserve", "Preserve"), ("custom", "Custom")]
WOL = NM.SettingWiredWakeOnLan
LABEL_CHARS = 15


class FieldError(Exception):
    def __init__(self, key, message):
        super().__init__(message)
        self.key = key


def shown_metered(s_con):
    """Metered value the dropdown shows: the guessed values show as Automatic."""
    cur = s_con.get_metered()
    return cur if cur in (NM.Metered.YES, NM.Metered.NO) else NM.Metered.UNKNOWN


def split_list(text):
    return [x for x in (p.strip() for p in text.replace(";", ",").split(",")) if x]


# --- input widgets (each reports edits through on_change) ---

class Choice(Gtk.DropDown):
    """Dropdown over (value, label) pairs; unknown saved values are kept as extra items."""

    def __init__(self, options, on_change):
        self._values = [v for v, _ in options]
        super().__init__(model=Gtk.StringList.new([t for _, t in options]))
        self.add_css_class("net-choice")
        self.set_hexpand(True)
        self.connect("notify::selected", lambda *_: on_change())

    def set_value(self, value, unknown_label=None):
        if value not in self._values:
            self._values.append(value)
            self.get_model().append(unknown_label or str(value))
        self.set_selected(self._values.index(value))

    def value(self):
        return self._values[self.get_selected()]


def text_entry(on_change, placeholder=""):
    ent = Gtk.Entry(hexpand=True, placeholder_text=placeholder)
    ent.add_css_class("net-entry")
    ent.connect("changed", lambda *_: on_change())
    return ent


class Spin(Gtk.SpinButton):
    """Integer spin button that reports edits as they are typed: value-changed
    alone waits for Enter or focus-out, so value() reads the text."""

    def __init__(self, lo, hi, on_change):
        super().__init__(adjustment=Gtk.Adjustment(lower=lo, upper=hi, step_increment=1,
                                                   page_increment=10), numeric=True)
        self.add_css_class("net-spin")
        pass_wheel(self)  # the page scrolls under the pointer
        self.connect("value-changed", lambda *_: on_change())
        self.connect("changed", lambda *_: on_change())

    def value(self):
        """The typed number clamped to the range, as a commit would make it."""
        try:
            typed = int(self.get_text().strip())
        except ValueError:
            return int(self.get_value())
        adj = self.get_adjustment()
        return int(min(max(typed, adj.get_lower()), adj.get_upper()))


def toggle(on_change):
    sw = Gtk.Switch(valign=Gtk.Align.CENTER)
    sw.add_css_class("net-switch")
    sw.connect("notify::active", lambda *_: on_change())
    return sw


class SecretEntry(Gtk.Box):
    """Hidden entry for a stored secret. It stays empty (and the stored value
    untouched) until Show fetches it or the user types a new one."""

    def __init__(self, page, setting, placeholder="Saved (Show to reveal)"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4, hexpand=True)
        self.page, self.setting, self.placeholder = page, setting, placeholder
        self.entry = Gtk.Entry(visibility=False, hexpand=True, placeholder_text=placeholder,
                               input_purpose=Gtk.InputPurpose.PASSWORD)
        self.entry.add_css_class("net-entry")
        self._handler = self.entry.connect("changed", self._changed)
        self.append(self.entry)
        self.show_btn = button("Show", on_click=self._toggle)
        self.append(self.show_btn)
        self.loaded = self.edited = False

    def _changed(self, *_):
        self.edited = True
        self.page.changed()

    def _toggle(self):
        if self.entry.get_visibility():
            self.entry.set_visibility(False)
            self.show_btn.set_label("Show")
            return

        def show():
            self.entry.set_visibility(True)
            self.show_btn.set_label("Hide")
        if self.loaded or self.edited:
            show()
        else:
            self.page.fetch_secrets(self.setting, show)

    def fill(self, value):
        """Secrets arrived: show the stored value unless the user already typed one."""
        if not self.edited:
            self.entry.handler_block(self._handler)
            self.entry.set_text(value or "")
            self.entry.handler_unblock(self._handler)
            if not value:
                self.entry.set_placeholder_text("Not stored")
        self.loaded = True

    def value(self):
        """The secret to write, or None to leave the stored one alone."""
        return self.entry.get_text() if self.loaded or self.edited else None


class RowList(Gtk.Box):
    """Rows of entries with remove buttons plus an Add button (addresses, routes)."""

    def __init__(self, columns, on_change, add_label="Add"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.columns, self.on_change = columns, on_change  # [(placeholder, width_chars)]
        self.rows = vbox(4)
        self.append(self.rows)
        add = button(add_label, on_click=lambda: (self.add_row(), self.on_change()))
        add.set_halign(Gtk.Align.START)
        self.append(add)

    def add_row(self, values=(), placeholders=()):
        row = hbox(4)
        row.entries = []
        for i, (ph, width) in enumerate(self.columns):
            ent = text_entry(self.on_change, placeholders[i] if i < len(placeholders) else ph)
            ent.set_width_chars(width)
            ent.set_hexpand(i == 0)
            if i < len(values) and values[i] is not None:
                ent.set_text(str(values[i]))
            row.entries.append(ent)
            row.append(ent)

        def remove():
            self.rows.remove(row)
            self.on_change()
        row.append(glyph_button("\U000F0156", "Remove", remove))  # nf-md-close
        self.rows.append(row)
        return row

    def values(self):
        """Non-empty rows as tuples of stripped strings."""
        out = []
        child = self.rows.get_first_child()
        while child:
            vals = tuple(e.get_text().strip() for e in child.entries)
            if any(vals):
                out.append(vals)
            child = child.get_next_sibling()
        return out


class EapForm(Gtk.Box):
    """PEAP/TTLS username + password without a CA certificate. Used inline in
    the Wi-Fi list (new network) and on the edit page (saved profile)."""

    def __init__(self, on_change, password=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.on_change = on_change
        self._inner_method = None
        self.method = Choice(EAP_METHODS, self._method_changed)
        self.inner = Choice([(v, t) for v, t, _ in EAP_INNER["peap"]], on_change)  # rebuilt per method
        self.anonymous = text_entry(on_change, "optional")
        self.identity = text_entry(on_change, "username")
        if password is None:
            password = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True)
            password.add_css_class("net-entry")
            password.connect("changed", lambda *_: on_change())
        self.password = password
        self.ask = Gtk.CheckButton(label="Ask every time")
        self.ask.connect("toggled", lambda *_: self._ask_changed())
        self.domain = text_entry(on_change, "optional, e.g. example.org")
        self.inner_row = field_row("Inner auth", self.inner)
        self.rows = {}
        for key, name, widget in (("method", "EAP method", self.method),
                                  ("anonymous", "Anonymous ID", self.anonymous),
                                  ("identity", "Identity", self.identity),
                                  ("password", "Password", self.password)):
            self.rows[key] = field_row(name, widget)
            self.append(self.rows[key])
        self.append(field_row("", self.ask))
        self.append(self.inner_row)
        self.append(field_row("Domain", self.domain))
        warn = label("No CA certificate: the server's identity is not verified", "net-form-warning")
        warn.set_wrap(True)
        self.append(warn)
        self._set_inner("peap")

    def _set_inner(self, method, value=None):
        if method != self._inner_method:
            new = Choice([(v, t) for v, t, _ in EAP_INNER[method]], self.on_change)
            self.inner_row.replace_widget(self.inner, new)
            self.inner, self._inner_method = new, method
        if value is not None:
            self.inner.set_value(value)

    def _method_changed(self):
        self._set_inner(self.method.value())
        self.on_change()

    def _ask_changed(self):
        self._sync_password()
        self.on_change()

    def _sync_password(self):
        ask = self.ask.get_active()
        self.password.set_sensitive(not ask)
        if isinstance(self.password, SecretEntry):
            self.password.entry.set_placeholder_text(
                "Asked when connecting" if ask else self.password.placeholder)

    def set_values(self, v):
        self.method.set_value(v["method"])
        self._set_inner(v["method"], v["inner"])
        self.anonymous.set_text(v["anonymous"])
        self.identity.set_text(v["identity"])
        self.domain.set_text(v["domain"])
        self.ask.set_active(v["ask"])
        self._sync_password()

    def values(self):
        return {"method": self.method.value(), "inner": self.inner.value(),
                "identity": self.identity.get_text().strip(),
                "anonymous": self.anonymous.get_text().strip(),
                "domain": self.domain.get_text().strip(), "ask": self.ask.get_active()}

    def password_value(self):
        if isinstance(self.password, SecretEntry):
            return self.password.value()
        return self.password.get_text()


class FieldRow(Gtk.Box):
    """Label + widget on one line, an error line under it."""

    def __init__(self, name, widget, hint=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        line = hbox(8)
        key = label(name, "net-edit-key")
        key.set_width_chars(LABEL_CHARS)
        key.set_valign(Gtk.Align.START if isinstance(widget, RowList) else Gtk.Align.CENTER)
        line.append(key)
        line.append(widget)
        self.line, self.widget = line, widget
        self.append(line)
        self.hint = label(hint or "", "net-edit-hint")
        self.hint.set_wrap(True)
        self.hint.set_visible(bool(hint))
        self.append(self.hint)
        self.error = label("", "net-form-error")
        self.error.set_wrap(True)
        self.error.set_visible(False)
        self.append(self.error)

    def replace_widget(self, old, new):
        self.line.insert_child_after(new, old)
        self.line.remove(old)
        self.widget = new

    def show_error(self, text):
        self.error.set_text(text or "")
        self.error.set_visible(bool(text))


def field_row(name, widget, hint=None):
    return FieldRow(name, widget, hint)


def edit_section(title):
    box = vbox(6)
    box.add_css_class("net-edit-section")
    box.append(label(title, "net-section"))
    return box


# --- the page ---

class EditPage(Gtk.Box):
    def __init__(self, app, on_back):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app, self.on_back = app, on_back
        header = hbox(6)
        header.append(glyph_button("\U000F004D", "Back", self._cancel))  # nf-md-arrow_left
        self.title = label("", "net-title", hexpand=True, ellipsize=True)
        header.append(self.title)
        self.append(header)
        self.body = vbox(12)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=True, max_content_height=560)
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
        footer.append(button("Advanced…", tooltip="Open nm-connection-editor for everything else",
                             on_click=lambda: self.app.edit(self.remote)))
        footer.append(Gtk.Box(hexpand=True))
        footer.append(button("Cancel", on_click=self._cancel))
        self.save_btn = button("Save", "net-btn-accent", on_click=self._save)
        footer.append(self.save_btn)
        self.append(footer)
        self.remote = self.base = None
        self._msg_error = False

    # --- open / build ---

    def open(self, remote):
        self.remote = remote
        self.base = NM.SimpleConnection.new_clone(remote)
        self._fetched = set()
        self._secret_fields = []   # (setting, SecretEntry, getter(conn) -> value)
        self._appliers = []        # apply(candidate) raising FieldError
        self._rows = {}            # "setting.property" -> FieldRow (inline errors)
        self._peers = []
        self._loading = True
        while child := self.body.get_first_child():
            self.body.remove(child)
        self.title.set_text(f"Edit {remote.get_id()}")
        self.apply_bar.set_visible(False)
        self._show_msg(None)
        ctype = remote.get_connection_type()
        self.active = next((ac for ac in self.app.client.get_active_connections()
                            if ac.get_uuid() == remote.get_uuid()), None)
        self._build_general(ctype)
        if ctype == "802-11-wireless":
            self._build_wifi()
            self._build_security()
        if ctype in ("802-11-wireless", "802-3-ethernet"):
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

    def _row(self, section, key, name, widget, hint=None):
        row = field_row(name, widget, hint)
        if key:
            self._rows[key] = row
        section.append(row)
        return row

    def _device(self, cls):
        """The profile's device: the active one, else the first managed one of `cls`."""
        if self.active and self.active.get_devices():
            return self.active.get_devices()[0]
        iface = self.base.get_setting_connection().get_interface_name()
        for dev in self.app.client.get_devices():
            if isinstance(dev, cls) and dev.get_managed() and (not iface or dev.get_iface() == iface):
                return dev
        return None

    def _build_general(self, ctype):
        s_con = self.base.get_setting_connection()
        sec = edit_section("General")
        name = text_entry(self.changed)
        name.set_text(s_con.get_id())
        self._row(sec, "connection.id", "Name", name)
        vpn = ctype in VPN_TYPES
        auto = toggle(self.changed)
        auto.set_active(s_con.get_autoconnect())
        auto.set_halign(Gtk.Align.START)
        if not vpn:  # VPNs are only ever connected by hand
            self._row(sec, "connection.autoconnect", "Autoconnect", auto)
        prio = Spin(-999, 999, self.changed)
        prio.set_value(s_con.get_autoconnect_priority())
        prio.set_halign(Gtk.Align.START)
        self._row(sec, "connection.autoconnect-priority", "Priority", prio,
                  None if vpn else "Higher is tried first among autoconnect profiles")
        metered = Choice(METERED, self.changed)
        metered.set_value(shown_metered(s_con))
        self._row(sec, "connection.metered", "Metered", metered)
        self.body.append(sec)
        uuid = s_con.get_uuid()

        def apply(cand):
            c = cand.get_setting_connection()
            new = name.get_text().strip()
            if not new:
                raise FieldError("connection.id", "Enter a name")
            if any(x.get_id() == new and x.get_uuid() != uuid
                   for x in self.app.client.get_connections()):
                raise FieldError("connection.id", f"Another profile is already named {new}")
            c.set_property("id", new)
            if not vpn:
                c.set_property("autoconnect", auto.get_active())
            c.set_property("autoconnect-priority", prio.value())
            if metered.value() != shown_metered(c):  # keep guess-yes/-no unless changed
                c.set_property("metered", metered.value())
        self._appliers.append(apply)

    def _build_wifi(self):
        s_wifi = self.base.get_setting_wireless()
        sec = edit_section("Wi-Fi")
        band = Choice(BANDS, self.changed)
        band.set_value(s_wifi.get_band() or None)
        self._row(sec, "802-11-wireless.band", "Band", band)

        ssid = connection_ssid(self.base)
        cur_bssid = (s_wifi.get_bssid() or "").upper() or None
        options = [(None, "Any")]
        dev = self._device(NM.DeviceWifi)
        if isinstance(dev, NM.DeviceWifi) and ssid:
            aps = [ap for ap in dev.get_access_points() if ssid_text(ap.get_ssid()) == ssid]
            aps.sort(key=lambda ap: -ap.get_strength())
            for ap in aps:
                options.append((ap.get_bssid().upper(), f"{ap.get_bssid()} · {ap.get_strength()}% · "
                                f"{freq_band(ap.get_frequency())}"))
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
        bssid.connect("notify::selected", lambda *_: custom.set_visible(bssid.value() == "custom"))
        self._row(sec, "802-11-wireless.bssid", "BSSID lock", box,
                  "Locking to one access point stops roaming between them")
        mtu = Spin(0, 9000, self.changed)
        mtu.set_value(s_wifi.get_mtu())
        mtu.set_halign(Gtk.Align.START)
        self._row(sec, "802-11-wireless.mtu", "MTU", mtu, "0 = automatic")
        self.body.append(sec)

        def apply(cand):
            w = cand.get_setting_wireless()
            w.set_property("band", band.value())
            value = bssid.value()
            if value == "custom":
                value = custom.get_text().strip()
                if mac_problem(value):
                    raise FieldError("802-11-wireless.bssid", mac_problem(value))
            if (value or None) != ((w.get_bssid() or "").upper() or None):
                w.set_property("bssid", value)
            w.set_property("mtu", mtu.value())
        self._appliers.append(apply)

    def _build_security(self):
        s_wsec = self.base.get_setting_wireless_security()
        sec = edit_section("Security")
        kind = connection_security(self.base)
        km = s_wsec.get_key_mgmt() if s_wsec else None
        self._row(sec, None, "Type", label(kind, "net-edit-value", hexpand=True))
        if km in ("wpa-psk", "sae"):
            pw = SecretEntry(self, "802-11-wireless-security")
            self._row(sec, "802-11-wireless-security.psk", "Password", pw)
            self._secret_fields.append(("802-11-wireless-security", pw,
                                        lambda c: c.get_setting_wireless_security().get_psk()))
            check = "psk" if km == "wpa-psk" else "sae"

            def apply(cand):
                value = pw.value()
                if value is None:
                    return
                problem = password_problem(check, value)
                if problem:
                    raise FieldError("802-11-wireless-security.psk", problem)
                cand.get_setting_wireless_security().set_property("psk", value)
            self._appliers.append(apply)
        elif km == "wpa-eap" and eap_values(self.base.get_setting_802_1x()) is not None:
            pw = SecretEntry(self, "802-1x")
            form = EapForm(self.changed, pw)
            form.set_values(eap_values(self.base.get_setting_802_1x()))
            sec.append(form)
            self._rows["802-1x.identity"] = form.rows["identity"]
            self._secret_fields.append(("802-1x", pw, lambda c: c.get_setting_802_1x().get_password()))
            stored = self.base.get_setting_802_1x().get_password_flags() & NM.SettingSecretFlags.NOT_SAVED == 0

            def apply(cand):
                values, password = form.values(), form.password_value()
                problem = eap_problem(values, password, stored and password is None)
                if problem:
                    raise FieldError("802-1x.identity", problem)
                apply_eap(cand.get_setting_802_1x(), values, password)
            self._appliers.append(apply)
        elif km:
            hint = label("This security type is edited in Advanced…", "net-edit-hint")
            hint.set_wrap(True)
            sec.append(hint)
        self.body.append(sec)

    def _build_mac(self, ctype):
        setting_name = "802-11-wireless" if ctype == "802-11-wireless" else "802-3-ethernet"
        setting = self.base.get_setting_by_name(setting_name)
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
        mode.connect("notify::selected", lambda *_: custom.set_visible(mode.value() == "custom"))
        dev = self._device(NM.DeviceWifi if ctype == "802-11-wireless" else NM.DeviceEthernet)
        hint = None
        if dev is not None:
            perm = dev.get_permanent_hw_address() if hasattr(dev, "get_permanent_hw_address") else None
            hint = f"Device {dev.get_iface()}: {perm or dev.get_hw_address()}"
            if perm and dev.get_hw_address() and dev.get_hw_address().upper() != perm.upper():
                hint += f" (now {dev.get_hw_address()})"
        self._row(sec, f"{setting_name}.cloned-mac-address", "Cloned MAC", box, hint)
        self.body.append(sec)

        def apply(cand):
            value = mode.value()
            if value == "custom":
                value = custom.get_text().strip()
                if mac_problem(value):
                    raise FieldError(f"{setting_name}.cloned-mac-address", mac_problem(value))
            s = cand.get_setting_by_name(setting_name)
            if s is None:
                if value is None:
                    return
                s = NM.SettingWireless.new() if setting_name == "802-11-wireless" else NM.SettingWired.new()
                cand.add_setting(s)
            if (value or None) != s.get_cloned_mac_address():
                s.set_property("cloned-mac-address", value)
        self._appliers.append(apply)

    def _build_ethernet(self):
        s_wired = self.base.get_setting_wired()
        flags = s_wired.get_wake_on_lan() if s_wired else WOL.DEFAULT
        sec = edit_section("Ethernet")
        wol = toggle(self.changed)
        wol.set_active(bool(flags & WOL.MAGIC))
        wol.set_halign(Gtk.Align.START)
        other = flags & ~(WOL.MAGIC | WOL.DEFAULT | WOL.IGNORE)
        hint = "Off: the system default" + (" (other wake flags stay as set)" if other else "")
        self._row(sec, "802-3-ethernet.wake-on-lan", "Wake on LAN", wol, hint)
        self.body.append(sec)

        def apply(cand):
            on = wol.get_active()
            s = cand.get_setting_wired()
            flags = s.get_wake_on_lan() if s else WOL.DEFAULT
            if on == bool(flags & WOL.MAGIC):
                return  # leave the flags exactly as stored
            if s is None:
                s = NM.SettingWired.new()
                cand.add_setting(s)
            new = (flags & ~(WOL.DEFAULT | WOL.IGNORE)) | WOL.MAGIC if on else flags & ~WOL.MAGIC
            s.set_property("wake-on-lan", int(new) or int(WOL.DEFAULT))
        self._appliers.append(apply)

    def _runtime(self, key):
        """Active connection's IP config for placeholders, or None."""
        if not self.active:
            return None
        return self.active.get_ip4_config() if key == "ipv4" else self.active.get_ip6_config()

    def _build_ip(self, family, key, title):
        s_ip = self.base.get_setting_by_name(key)
        if s_ip is None:
            return
        rt = self._runtime(key)
        sec = edit_section(title)
        method = Choice(IP_METHODS[key], self.changed)
        method.set_value(s_ip.get_method())
        self._row(sec, f"{key}.method", "Method", method)
        addrs = RowList([("address/prefix", 20)], self.changed, "Add address")
        orig_addrs = [s_ip.get_address(i) for i in range(s_ip.get_num_addresses())]
        for a in orig_addrs:
            addrs.add_row((f"{a.get_address()}/{a.get_prefix()}",))
        rt_addrs = [f"{a.get_address()}/{a.get_prefix()}" for a in rt.get_addresses()] if rt else []
        if not orig_addrs and rt_addrs:
            addrs.add_row((), (rt_addrs[0],))
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
        ign_row = self._row(sec, f"{key}.ignore-auto-dns", "Ignore auto DNS", ignore_dns)
        rt_dom = ", ".join(rt.get_domains() or []) if rt else ""
        search = text_entry(self.changed, rt_dom or "comma-separated")
        search.set_text(", ".join(s_ip.get_dns_search(i) for i in range(s_ip.get_num_dns_searches())))
        search_row = self._row(sec, f"{key}.dns-search", "Search domains", search)
        self.body.append(sec)

        def sync_visible():
            m = method.value()
            off = m in ("disabled", "ignore")
            manual = m == "manual"
            addr_row.set_visible(manual or (not off and bool(addrs.values())))
            gw_row.set_visible(manual)
            for row in (dns_row, ign_row, search_row):
                row.set_visible(not off)
        sync_visible()
        method.connect("notify::selected", lambda *_: sync_visible())

        def apply(cand):
            s = cand.get_setting_by_name(key)
            s.set_property("method", method.value())
            parsed = []
            for (text,) in addrs.values():
                try:
                    parsed.append(parse_cidr(text, family))
                except ValueError as e:
                    raise FieldError(f"{key}.addresses", str(e)) from None
            # keep the stored address objects (and any attributes) for unchanged rows
            s.clear_addresses()
            for addr, prefix in parsed:
                same = next((a for a in orig_addrs
                             if a.get_address() == addr and a.get_prefix() == prefix), None)
                s.add_address(same or NM.IPAddress.new(family, addr, prefix))
            gateway = gw.get_text().strip()
            if gateway:
                try:
                    parse_ip(gateway, family)
                except ValueError as e:
                    raise FieldError(f"{key}.gateway", str(e)) from None
            s.set_property("gateway", gateway or None)
            servers = split_list(dns.get_text())
            for server in servers:
                if not NM.utils_ipaddr_valid(family, server.split("#")[0]):
                    raise FieldError(f"{key}.dns", f"{server}: not an {title} address")
            if servers != [s.get_dns(i) for i in range(s.get_num_dns())]:
                s.clear_dns()
                for server in servers:
                    s.add_dns(server)
            s.set_property("ignore-auto-dns", ignore_dns.get_active())
            domains = split_list(search.get_text())
            s.clear_dns_searches()
            for d in domains:
                s.add_dns_search(d)
        self._appliers.append(apply)

    def _build_routes(self, ctype):
        sec = edit_section("Routes")
        if ctype == "wireguard":
            note = label("Peer Allowed IPs are the main way to choose what goes through the "
                         "tunnel; routes here are extra.", "net-edit-hint")
            note.set_wrap(True)
            sec.append(note)
        any_family = False
        for family, key, title in FAMILIES:
            s_ip = self.base.get_setting_by_name(key)
            if s_ip is None:
                continue
            any_family = True
            orig = [s_ip.get_route(i) for i in range(s_ip.get_num_routes())]
            routes = RowList([("destination/prefix", 18), ("next hop", 12), ("metric", 6)],
                             self.changed, "Add route")
            for r in orig:
                routes.add_row((f"{r.get_dest()}/{r.get_prefix()}", r.get_next_hop() or "",
                                r.get_metric() if r.get_metric() >= 0 else ""))
            self._row(sec, f"{key}.routes", f"{title} routes", routes)
            ign = toggle(self.changed)
            ign.set_active(s_ip.get_ignore_auto_routes())
            ign.set_halign(Gtk.Align.START)
            self._row(sec, f"{key}.ignore-auto-routes", "Ignore auto routes", ign)
            never = toggle(self.changed)
            never.set_active(s_ip.get_never_default())
            never.set_halign(Gtk.Align.START)
            self._row(sec, f"{key}.never-default", "Only its network", never,
                      f"Use {title} only for resources on this connection's network (never-default)")
            self._appliers.append(self._routes_applier(family, key, routes, orig, ign, never))
        if any_family:
            self.body.append(sec)

    @staticmethod
    def _routes_applier(family, key, routes, orig, ign, never):
        def apply(cand):
            s = cand.get_setting_by_name(key)
            new = []
            for dest, hop, metric in routes.values():
                try:
                    addr, prefix = parse_cidr(dest, family, 32 if family == socket.AF_INET else 128)
                    hop = parse_ip(hop, family) if hop else None
                except ValueError as e:
                    raise FieldError(f"{key}.routes", str(e)) from None
                if metric and not metric.isdigit():
                    raise FieldError(f"{key}.routes", f"{metric}: metric must be a number")
                m = int(metric) if metric else -1
                same = next((r for r in orig if r.get_dest() == addr and r.get_prefix() == prefix
                             and (r.get_next_hop() or None) == hop and r.get_metric() == m), None)
                new.append(same or NM.IPRoute.new(family, addr, prefix, hop, m))
            s.clear_routes()
            for r in new:
                s.add_route(r)
            s.set_property("ignore-auto-routes", ign.get_active())
            s.set_property("never-default", never.get_active())
        return apply

    def _build_wireguard(self):
        s_wg = self.base.get_setting_by_name("wireguard")
        sec = edit_section("WireGuard")
        key = SecretEntry(self, "wireguard")
        self._row(sec, "wireguard.private-key", "Private key", key)
        self._secret_fields.append(("wireguard", key,
                                    lambda c: c.get_setting_by_name("wireguard").get_private_key()))
        pub = label("", "net-edit-value", hexpand=True, ellipsize=True)
        pub.set_selectable(True)
        pub_row = self._row(sec, None, "Public key", pub)
        dev = self.active.get_devices()[0] if self.active and self.active.get_devices() else None
        pub_row.set_visible(False)
        if isinstance(dev, NM.DeviceWireGuard) and dev.get_public_key():
            pub.set_text(base64.b64encode(bytes(dev.get_public_key().get_data())).decode())
            pub_row.set_visible(True)
        self._pub = (pub, pub_row, key)
        self._pub_for = None  # private key the shown public key was derived from
        port = Spin(0, 65535, self.changed)
        port.set_value(s_wg.get_listen_port())
        port.set_halign(Gtk.Align.START)
        self._row(sec, "wireguard.listen-port", "Listen port", port, "0 = random")
        fwmark = text_entry(self.changed, "0 = off")
        fwmark.set_text(f"{s_wg.get_fwmark():#x}" if s_wg.get_fwmark() else "")
        self._row(sec, "wireguard.fwmark", "Firewall mark", fwmark)
        mtu = Spin(0, 9000, self.changed)
        mtu.set_value(s_wg.get_mtu())
        mtu.set_halign(Gtk.Align.START)
        self._row(sec, "wireguard.mtu", "MTU", mtu, "0 = automatic")
        peer_routes = toggle(self.changed)
        peer_routes.set_active(s_wg.get_peer_routes())
        peer_routes.set_halign(Gtk.Align.START)
        self._row(sec, "wireguard.peer-routes", "Peer routes", peer_routes,
                  "Add routes for the peers' Allowed IPs")
        self.body.append(sec)

        def apply(cand):
            s = cand.get_setting_by_name("wireguard")
            value = key.value()
            if value is not None:
                problem = wg_key_problem(value, "Private key") if value else "Enter the private key"
                if problem:
                    raise FieldError("wireguard.private-key", problem)
                s.set_property("private-key", value)
            s.set_property("listen-port", port.value())
            text = fwmark.get_text().strip() or "0"
            try:
                mark = int(text, 0)
            except ValueError:
                raise FieldError("wireguard.fwmark", "A number (decimal or 0x hex)") from None
            if not 0 <= mark <= 0xFFFFFFFF:
                raise FieldError("wireguard.fwmark", "At most 0xffffffff")
            s.set_property("fwmark", mark)
            s.set_property("mtu", mtu.value())
            s.set_property("peer-routes", peer_routes.get_active())
        self._appliers.append(apply)

    def _update_public_key(self):
        """Public key from the private key via `wg pubkey` (shown only when wg exists)."""
        pub, row, key = self._pub
        value = key.value()
        if not value or value == self._pub_for or wg_key_problem(value) or not shutil.which("wg"):
            return
        self._pub_for = value
        try:
            out = subprocess.run(["wg", "pubkey"], input=value, capture_output=True,
                                 text=True, timeout=2, check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return
        pub.set_text(out)
        row.set_visible(bool(out))

    def _build_peers(self):
        s_wg = self.base.get_setting_by_name("wireguard")
        sec = edit_section("Peers")
        self._peer_box = vbox(8)
        sec.append(self._peer_box)
        add = button("Add peer", on_click=lambda: (self._add_peer(None), self.changed()))
        add.set_halign(Gtk.Align.START)
        sec.append(add)
        self._peers_row = self._row(sec, "wireguard.peers", "", Gtk.Box())
        for i in range(s_wg.get_peers_len()):
            self._add_peer(s_wg.get_peer(i))
        self.body.append(sec)

        def apply(cand):
            s = cand.get_setting_by_name("wireguard")
            peers = [p.build() for p in self._peers]
            s.clear_peers()
            for peer in peers:
                s.append_peer(peer)
        self._appliers.append(apply)

    def _add_peer(self, peer):
        editor = PeerEditor(self, peer)
        self._peers.append(editor)
        self._peer_box.append(editor)
        if peer is not None:
            self._secret_fields.append(("wireguard", editor.psk, editor.stored_psk))

    def _rebase_peers(self):
        """Point each peer editor at its saved peer (the candidate lists them in
        editor order), so stored-PSK lookups use the saved public key."""
        s_wg = self.base.get_setting_by_name("wireguard")
        for i, editor in enumerate(self._peers):
            if editor.peer is None:  # a new peer is now stored
                self._secret_fields.append(("wireguard", editor.psk, editor.stored_psk))
            editor.peer = s_wg.get_peer(i)

    def remove_peer(self, editor):
        self._peers.remove(editor)
        self._peer_box.remove(editor)
        self._secret_fields = [f for f in self._secret_fields if f[1] is not editor.psk]
        self.changed()

    # --- secrets ---

    def fetch_secrets(self, setting, then, on_error=None):
        if setting in self._fetched:
            then()
            return
        remote = self.remote

        def done(rc, res):
            try:
                secrets = rc.get_secrets_finish(res)
            except GLib.Error as e:
                self._show_msg(f"Cannot read the secrets: {error_text(e)}", error=True)
                if on_error:
                    on_error(setting, e)
                return
            if rc is not self.remote:
                return  # the page moved on
            if secrets is not None:
                self.base.update_secrets(setting, secrets)
            self._fetched.add(setting)
            for name, entry, getter in self._secret_fields:
                if name == setting:
                    entry.fill(getter(self.base))
            self.changed()
            then()
        remote.get_secrets_async(setting, None, done)

    # --- candidate, validation, save ---

    def candidate(self):
        """(connection built from the fields, [(key, message)])."""
        cand = NM.SimpleConnection.new_clone(self.base)
        errors = []
        for apply in self._appliers:
            try:
                apply(cand)
            except FieldError as e:
                errors.append((e.key, str(e)))
        if not errors:
            try:
                cand.verify()
            except GLib.Error as e:
                key, _, text = e.message.partition(": ")
                errors.append((key, text) if key in self._rows else (None, e.message))
        return cand, errors

    def changed(self):
        if self._loading or self.base is None:
            return
        cand, errors = self.candidate()
        for row in self._rows.values():
            row.show_error(None)
        loose = [msg for key, msg in errors if key not in self._rows]
        for key, msg in errors:
            if key in self._rows:
                self._rows[key].show_error(msg)
        if loose:
            self._show_msg("; ".join(loose), error=True)
        elif self._msg_error:
            self._show_msg(None)  # clear only errors; keep "Saved" and the like
        dirty = not cand.compare(self.base, NM.SettingCompareFlags.EXACT)
        self.save_btn.set_sensitive(dirty and not errors)
        if self.remote.get_connection_type() == "wireguard":
            self._update_public_key()

    def _show_msg(self, text, error=False, ok=False):
        self._msg_error = bool(text) and error
        self.msg.set_text(text or "")
        self.msg.set_visible(bool(text))
        self.msg.set_css_classes(["net-edit-msg"] + (["net-status-err"] if error else [])
                                 + (["net-status-ok"] if ok else []))

    @staticmethod
    def _peer_keys(conn):
        s_wg = conn.get_setting_by_name("wireguard")
        return {s_wg.get_peer(i).get_public_key() for i in range(s_wg.get_peers_len())} if s_wg else set()

    def _missing_secrets(self, cand):
        """Settings whose stored secrets must be fetched before `cand` can be
        sent: none if it carries no secret and keeps the same peers."""
        carried = cand.to_dbus(NM.ConnectionSerializationFlags.ONLY_SECRETS).unpack()
        if not any(carried.values()) and self._peer_keys(cand) == self._peer_keys(self.base):
            return []
        return [name for name in SECRET_SETTINGS
                if self.base.get_setting_by_name(name) is not None and name not in self._fetched]

    def _save(self):
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
        remote, name = self.remote, cand.get_id()
        self.save_btn.set_sensitive(False)
        self.apply_bar.set_visible(False)
        self._show_msg(f"Saving {name}…")

        def done(rc, res):
            try:
                rc.update2_finish(res)
            except GLib.Error as e:
                self._show_msg(f"Not saved: {error_text(e)}", error=True)
                self.changed()
                return
            if rc is not self.remote:
                return
            self.base = cand
            self._rebase_peers()
            self.title.set_text(f"Edit {name}")
            self.active = next((ac for ac in self.app.client.get_active_connections()
                                if ac.get_uuid() == rc.get_uuid()), None)
            devs = self.active.get_devices() if self.active else []
            if devs:
                self._reapply(devs[0], name)
            else:
                self._show_msg(f"Saved {name}", ok=True)
            self.changed()
            self.app.queue_sync()
        remote.update2(cand.to_dbus(NM.ConnectionSerializationFlags.ALL),
                       NM.SettingsUpdate2Flags.TO_DISK, None, None, done)

    def _save_unreadable(self, setting, err):
        """NM answers "no agents" when a required secret is already missing (it
        asks agents instead of returning a partial set): nothing complete is
        stored to lose, so save with what the fields hold. Other errors stop."""
        if err.domain != GLib.quark_to_string(NM.AgentManagerError.quark()):
            self.changed()
            return
        self._fetched.add(setting)
        self._save()

    def _reapply(self, dev, name):
        """Apply the saved profile to the connected device without a disconnect.
        NM refuses changes it cannot make live (SSID, security, band, BSSID,
        MAC, some MTUs): those wait for the user's Reconnect now, since a
        reconnect drops open sessions."""
        remote = self.remote
        self._show_msg(f"Saved {name}; applying…")

        def reapplied(d, res):
            try:
                d.reapply_finish(res)
            except GLib.Error as e:
                if remote is not self.remote:
                    return
                self._show_msg(None)
                self.apply_msg.set_text(f"Saved. Takes effect after reconnecting "
                                        f"({reapply_refusal_text(e)})")
                self.reconnect_btn.set_visible(True)
                self.apply_bar.set_visible(True)
                return
            if remote is self.remote:
                self._show_msg(f"Saved and applied to {name}", ok=True)
            self.app.queue_sync()
        dev.reapply_async(None, 0, 0, None, reapplied)  # None: the saved profile, secrets included

    def _reconnect(self):
        ac, remote = self.active, self.remote
        devs = ac.get_devices() if ac else []
        if not devs:
            return
        dev, name = devs[0], remote.get_id()
        self.reconnect_btn.set_visible(False)
        self.apply_msg.set_text(f"Reconnecting {name}…")

        def reconnected(c, res):
            try:
                c.activate_connection_finish(res)
            except GLib.Error as e:
                self.apply_msg.set_text(f"Reconnecting {name} failed: {error_text(e)}")
                return
            self.apply_msg.set_text(f"Reconnected {name}: the changes are applied")
            self.app.queue_sync()
        self.app.client.activate_connection_async(remote, dev, None, None, reconnected)

    def _cancel(self):
        self.remote = self.base = None
        self.on_back()


class PeerEditor(Gtk.Box):
    """One WireGuard peer. NM.WireGuardPeer is immutable once sealed, so
    build() clones the stored peer (keeping fields not shown) and reseals it."""

    def __init__(self, page, peer):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class("net-row")
        self.page, self.peer = page, peer
        ch = page.changed
        head = hbox(6)
        head.append(label("Peer" if peer else "New peer", "net-row-title", hexpand=True))
        head.append(glyph_button("\U000F0A7A", "Remove peer",  # nf-md-trash_can_outline
                                 lambda: page.remove_peer(self), "net-delete-btn"))
        self.append(head)
        self.pubkey = text_entry(ch, "base64 public key")
        self.endpoint = text_entry(ch, "host:port")
        self.allowed = text_entry(ch, "e.g. 0.0.0.0/0, ::/0")
        self.psk = SecretEntry(page, "wireguard",
                               "Saved (Show to reveal)" if peer else "optional")
        if peer is None:
            self.psk.loaded = True  # nothing stored to fetch
        self.keepalive = Spin(0, 65535, ch)
        self.keepalive.set_halign(Gtk.Align.START)
        self.rows = {}
        for key, name, widget, hint in (
                ("pubkey", "Public key", self.pubkey, None),
                ("endpoint", "Endpoint", self.endpoint, None),
                ("allowed", "Allowed IPs", self.allowed, "Comma-separated; what goes through the tunnel"),
                ("psk", "Preshared key", self.psk, None),
                ("keepalive", "Keepalive (s)", self.keepalive, "0 = off")):
            self.rows[key] = field_row(name, widget, hint)
            self.append(self.rows[key])
        if peer is not None:
            self.pubkey.set_text(peer.get_public_key() or "")
            self.endpoint.set_text(peer.get_endpoint() or "")
            self.allowed.set_text(", ".join(
                x for x in (peer.get_allowed_ip(i, None) for i in range(peer.get_allowed_ips_len())) if x))
            self.keepalive.set_value(peer.get_persistent_keepalive())

    def stored_psk(self, conn):
        s_wg = conn.get_setting_by_name("wireguard")
        key = self.peer.get_public_key()
        for i in range(s_wg.get_peers_len()):
            p = s_wg.get_peer(i)
            if p.get_public_key() == key:
                return p.get_preshared_key()
        return None

    def _error(self, key, text):
        for k, row in self.rows.items():
            row.show_error(text if k == key else None)
        if text:
            raise FieldError("wireguard.peers", "Fix the peer fields above")

    def build(self):
        pubkey = self.pubkey.get_text().strip()
        self._error("pubkey", wg_key_problem(pubkey, "Public key"))
        endpoint = self.endpoint.get_text().strip()
        host, _, port = endpoint.rpartition(":")
        if endpoint and (not host or not port.isdigit() or not 0 < int(port) < 65536):
            self._error("endpoint", "Use host:port ([v6addr]:port for IPv6)")
        allowed = split_list(self.allowed.get_text())
        for ip in allowed:
            fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
            try:
                parse_cidr(ip, fam, 32 if fam == socket.AF_INET else 128)
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
                peer.set_preshared_key(self.peer.get_preshared_key(), True)
        else:
            peer = self.peer.new_clone(True)
        peer.set_public_key(pubkey, True)
        if endpoint:
            peer.set_endpoint(endpoint, True)
        peer.clear_allowed_ips()
        for ip in allowed:
            peer.append_allowed_ip(ip, True)
        if psk is not None:
            peer.set_preshared_key(psk or None, True)
        peer.set_persistent_keepalive(self.keepalive.value())
        peer.seal()
        ok, err = _peer_valid(peer)
        if not ok:
            raise FieldError("wireguard.peers", err)
        return peer


def _peer_valid(peer):
    try:
        peer.is_valid(True, True)
    except GLib.Error as e:
        return False, e.message
    return True, None
