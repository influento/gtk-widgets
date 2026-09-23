"""libnm helpers shared by the network popup (main.py) and network-agent (agent.py)."""

import os, time, uuid

import gi

gi.require_version("NM", "1.0")
from gi.repository import GLib, NM  # noqa: E402

ApSec = getattr(NM, "80211ApSecurityFlags")
ApFlags = getattr(NM, "80211ApFlags")

VPN_TYPES = ("wireguard", "vpn")
HOTSPOT_ID = "Hotspot"

ICON = {
    "wifi": ["\U000F092F", "\U000F091F", "\U000F0922", "\U000F0925", "\U000F0928"],  # nf-md-wifi_strength_*
    "wired": "\U000F0200",      # nf-md-ethernet
    "vpn": "\U000F0582",        # nf-md-vpn
    "hotspot": "\U000F0AE9",    # nf-md-access_point_network
    "lock": "\U000F033E",       # nf-md-lock
    "check": "\U000F012C",      # nf-md-check
    "saved": "\U000F0193",      # nf-md-content_save
    "expand": "\U000F0142",     # nf-md-chevron_right
    "collapse": "\U000F0140",   # nf-md-chevron_down
    "rescan": "\U000F0450",     # nf-md-refresh
    "back": "\U000F004D",       # nf-md-arrow_left
    "edit": "\U000F03EB",       # nf-md-pencil
    "delete": "\U000F0A7A",     # nf-md-trash_can_outline
    "export": "\U000F0207",     # nf-md-export
    "offline": "\U000F0B5A",    # nf-md-network_off_outline
}

# Device state reasons worth spelling out; the rest fall back to NM's nick.
DEVICE_REASONS = {
    NM.DeviceStateReason.NO_SECRETS: "wrong or missing password",
    NM.DeviceStateReason.SUPPLICANT_DISCONNECT: "authentication failed (wrong password?)",
    NM.DeviceStateReason.SUPPLICANT_TIMEOUT: "the network did not answer (wrong password?)",
    NM.DeviceStateReason.SUPPLICANT_FAILED: "wpa_supplicant failed",
    NM.DeviceStateReason.SUPPLICANT_CONFIG_FAILED: "wpa_supplicant rejected the settings",
    NM.DeviceStateReason.SSID_NOT_FOUND: "network not found",
    NM.DeviceStateReason.IP_CONFIG_UNAVAILABLE: "no IP address (DHCP failed)",
    NM.DeviceStateReason.DHCP_FAILED: "DHCP failed",
    NM.DeviceStateReason.CARRIER: "cable unplugged",
    NM.DeviceStateReason.USER_REQUESTED: "disconnected by user",
    NM.DeviceStateReason.SHARED_START_FAILED: "could not start connection sharing",
    NM.DeviceStateReason.SHARED_FAILED: "connection sharing failed",
}

AC_REASONS = {
    NM.ActiveConnectionStateReason.NO_SECRETS: "wrong or missing secrets",
    NM.ActiveConnectionStateReason.LOGIN_FAILED: "login failed",
    NM.ActiveConnectionStateReason.CONNECT_TIMEOUT: "timed out",
    NM.ActiveConnectionStateReason.USER_DISCONNECTED: "disconnected by user",
    NM.ActiveConnectionStateReason.DEVICE_DISCONNECTED: "device disconnected",
    NM.ActiveConnectionStateReason.CONNECTION_REMOVED: "profile deleted",
    NM.ActiveConnectionStateReason.DEVICE_REALIZE_FAILED: "could not create the interface",
}


# City part of "<country>-<city>" VPN profile names (Mullvad-style location codes)
VPN_CITIES = {
    "ams": "Amsterdam", "buc": "Bucharest", "chi": "Chicago", "dub": "Dubai",
    "hel": "Helsinki", "hkg": "Hong Kong", "leu": "Andorra", "mcm": "Monaco",
    "nyc": "New York", "waw": "Warsaw", "lon": "London", "fra": "Frankfurt",
    "par": "Paris", "sto": "Stockholm", "zrh": "Zurich", "tyo": "Tokyo",
}
# Chișinău shares "chi" with Chicago; the country code disambiguates
VPN_PLACES = {"md-chi": "Chișinău"}


def vpn_place(name):
    """'nl-ams' -> 'Amsterdam'; None when the name is not a location code."""
    if name in VPN_PLACES:
        return VPN_PLACES[name]
    parts = name.split("-")
    return VPN_CITIES.get(parts[1]) if len(parts) == 2 and len(parts[0]) == 2 else None


def kernel_stale():
    """The running kernel's modules are gone (package upgraded, no reboot yet)."""
    return not os.path.isdir(f"/lib/modules/{os.uname().release}")


def error_text(err):
    """Readable message for a libnm GLib.Error, with a hint for missing kernel modules."""
    msg = err.message if isinstance(err, GLib.Error) else str(err)
    if "Operation not supported" in msg and kernel_stale():
        msg += " (kernel updated: reboot to load its modules)"
    return msg


def device_reason_text(reason):
    reason = NM.DeviceStateReason(reason)
    return DEVICE_REASONS.get(reason) or reason.value_nick.replace("-", " ")


def ac_reason_text(reason):
    reason = NM.ActiveConnectionStateReason(reason)
    return AC_REASONS.get(reason) or reason.value_nick.replace("-", " ")


def hidden_connection(conn):
    """Profiles NM does not own (docker bridges, lo): never shown or touched."""
    return (bool(conn.get_flags() & NM.SettingsConnectionFlags.EXTERNAL)
            or conn.get_connection_type() == "loopback")


def ssid_text(ssid):
    """GLib.Bytes SSID -> display string (None for hidden APs)."""
    if ssid is None:
        return None
    data = ssid.get_data()
    return NM.utils_ssid_to_utf8(data) if data else None


def connection_ssid(conn):
    s_wifi = conn.get_setting_wireless()
    return ssid_text(s_wifi.get_ssid()) if s_wifi else None


def is_hotspot(conn):
    s_wifi = conn.get_setting_wireless()
    return bool(s_wifi) and s_wifi.get_mode() == "ap"


def signal_glyph(strength):
    return ICON["wifi"][min(4, (strength + 19) // 20)]


def ap_security(ap):
    """(kind, label) for an access point. kind: open, owe, wep, psk, sae, eap."""
    wpa, rsn = ap.get_wpa_flags(), ap.get_rsn_flags()
    both = wpa | rsn
    if both & (ApSec.KEY_MGMT_802_1X | ApSec.KEY_MGMT_EAP_SUITE_B_192):
        return "eap", "WPA2 Enterprise" if rsn else "WPA Enterprise"
    if rsn & ApSec.KEY_MGMT_SAE:
        if rsn & ApSec.KEY_MGMT_PSK:
            return "psk", "WPA2/WPA3 Personal"
        return "sae", "WPA3 Personal"
    if both & ApSec.KEY_MGMT_PSK:
        return "psk", "WPA2 Personal" if rsn else "WPA Personal"
    if rsn & (ApSec.KEY_MGMT_OWE | ApSec.KEY_MGMT_OWE_TM):
        return "owe", "Enhanced Open (OWE)"
    if ap.get_flags() & ApFlags.PRIVACY:
        return "wep", "WEP"
    return "open", "Open"


KEY_MGMT_LABELS = {
    "none": "WEP", "ieee8021x": "Dynamic WEP (802.1X)", "owe": "Enhanced Open (OWE)",
    "wpa-psk": "WPA/WPA2 Personal", "sae": "WPA3 Personal",
    "wpa-eap": "WPA/WPA2 Enterprise", "wpa-eap-suite-b-192": "WPA3 Enterprise",
}


def connection_security(conn):
    s_wsec = conn.get_setting_wireless_security()
    if not s_wsec:
        return "Open"
    km = s_wsec.get_key_mgmt()
    return KEY_MGMT_LABELS.get(km, km)


def freq_band(mhz):
    """'5 GHz, channel 36' for a frequency in MHz."""
    band = "2.4 GHz" if mhz < 3000 else "5 GHz" if mhz < 5925 else "6 GHz"
    return f"{band}, channel {NM.utils_wifi_freq_to_channel(mhz)}"


def relative_time(ts, now=None):
    if not ts:
        return "never"
    delta = max(0, (now or time.time()) - ts)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    if delta < 30 * 86400:
        return f"{int(delta // 86400)} d ago"
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def ip_lines(ipcfg):
    """(addresses, gateway, dns) of an NM.IPConfig as display strings."""
    if not ipcfg:
        return [], None, []
    addrs = [f"{a.get_address()}/{a.get_prefix()}" for a in ipcfg.get_addresses()]
    return addrs, ipcfg.get_gateway(), list(ipcfg.get_nameservers() or [])


# --- building connections ---

def _base_connection(conn_id, conn_type, autoconnect=True, iface=None):
    conn = NM.SimpleConnection.new()
    s_con = NM.SettingConnection.new()
    s_con.set_property(NM.SETTING_CONNECTION_ID, conn_id)
    s_con.set_property(NM.SETTING_CONNECTION_UUID, str(uuid.uuid4()))
    s_con.set_property(NM.SETTING_CONNECTION_TYPE, conn_type)
    s_con.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, autoconnect)
    if iface:
        s_con.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, iface)
    conn.add_setting(s_con)
    return conn


def wifi_connection(ssid, kind, password=None, hidden=False):
    """Client profile for `ssid`. kind: open, owe, psk, sae. Secrets are
    system-owned (flags 0), as nmcli stores them by default."""
    conn = _base_connection(ssid, "802-11-wireless")
    s_wifi = NM.SettingWireless.new()
    s_wifi.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(ssid.encode()))
    s_wifi.set_property(NM.SETTING_WIRELESS_MODE, "infrastructure")
    if hidden:
        s_wifi.set_property(NM.SETTING_WIRELESS_HIDDEN, True)
    conn.add_setting(s_wifi)
    if kind in ("psk", "sae", "owe"):
        s_wsec = NM.SettingWirelessSecurity.new()
        s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT,
                            {"psk": "wpa-psk"}.get(kind, kind))
        if kind != "owe":
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK_FLAGS,
                                NM.SettingSecretFlags.NONE)
        conn.add_setting(s_wsec)
    return conn


def hotspot_connection(ssid, password, band, iface):
    """Access point with NAT (ipv4.method=shared), never autoconnected.
    band: 'bg' (2.4 GHz) or 'a' (5 GHz). Mirrors `nmcli device wifi hotspot`."""
    conn = _base_connection(HOTSPOT_ID, "802-11-wireless", autoconnect=False, iface=iface)
    s_wifi = NM.SettingWireless.new()
    s_wifi.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(ssid.encode()))
    s_wifi.set_property(NM.SETTING_WIRELESS_MODE, "ap")
    s_wifi.set_property(NM.SETTING_WIRELESS_BAND, band)
    conn.add_setting(s_wifi)
    s_wsec = NM.SettingWirelessSecurity.new()
    s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-psk")
    s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
    s_wsec.add_proto("rsn")
    s_wsec.add_pairwise("ccmp")
    s_wsec.add_group("ccmp")
    # nmcli disables PMF for hotspots: many drivers and clients break with it
    s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PMF,
                        int(NM.SettingWirelessSecurityPmf.DISABLE))
    conn.add_setting(s_wsec)
    s_ip4 = NM.SettingIP4Config.new()
    s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, "shared")
    conn.add_setting(s_ip4)
    s_ip6 = NM.SettingIP6Config.new()
    s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, "ignore")
    conn.add_setting(s_ip6)
    return conn


def password_problem(kind, password):
    """Why `password` can't work for security `kind`, or None."""
    if kind == "psk" and not NM.utils_wpa_psk_valid(password):
        return "WPA passwords are 8-63 characters (or 64 hex digits)"
    if kind == "sae" and not password:
        return "Enter a password"
    return None


# --- WireGuard export ---

def _ip_setting_values(conn):
    addrs, dns = [], []
    for s_ip in (conn.get_setting_ip4_config(), conn.get_setting_ip6_config()):
        if not s_ip:
            continue
        for i in range(s_ip.get_num_addresses()):
            a = s_ip.get_address(i)
            addrs.append(f"{a.get_address()}/{a.get_prefix()}")
        dns += [s_ip.get_dns(i) for i in range(s_ip.get_num_dns())]
        # "~" and "~domain" are NM routing-only domains (the importer adds "~"
        # to send all DNS through the tunnel); wg-quick has no such notion
        dns += [d for d in (s_ip.get_dns_search(i) for i in range(s_ip.get_num_dns_searches()))
                if not d.startswith("~")]
    return addrs, list(dict.fromkeys(dns))


def wireguard_conf(conn):
    """wg-quick .conf text for a WireGuard profile whose secrets have been
    merged in (private key, peer preshared keys). Inverse of the fields
    NM.conn_wireguard_import() reads."""
    s_wg = conn.get_setting_by_name(NM.SETTING_WIREGUARD_SETTING_NAME)
    lines = ["[Interface]"]
    if s_wg.get_private_key():
        lines.append(f"PrivateKey = {s_wg.get_private_key()}")
    addrs, dns = _ip_setting_values(conn)
    if addrs:
        lines.append(f"Address = {', '.join(addrs)}")
    if dns:
        lines.append(f"DNS = {', '.join(dns)}")
    if s_wg.get_listen_port():
        lines.append(f"ListenPort = {s_wg.get_listen_port()}")
    if s_wg.get_mtu():
        lines.append(f"MTU = {s_wg.get_mtu()}")
    if s_wg.get_fwmark():
        lines.append(f"FwMark = {s_wg.get_fwmark():#x}")
    for i in range(s_wg.get_peers_len()):
        peer = s_wg.get_peer(i)
        lines += ["", "[Peer]", f"PublicKey = {peer.get_public_key()}"]
        if peer.get_preshared_key():
            lines.append(f"PresharedKey = {peer.get_preshared_key()}")
        allowed = [peer.get_allowed_ip(j, None) for j in range(peer.get_allowed_ips_len())]
        allowed = [a for a in allowed if a]
        if allowed:
            lines.append(f"AllowedIPs = {', '.join(allowed)}")
        if peer.get_endpoint():
            lines.append(f"Endpoint = {peer.get_endpoint()}")
        if peer.get_persistent_keepalive():
            lines.append(f"PersistentKeepalive = {peer.get_persistent_keepalive()}")
    return "\n".join(lines) + "\n"


def write_private(path, text):
    """Write `text` to `path` readable by the owner only (mode 0600)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o600)  # an existing file keeps its old mode otherwise
        f.write(text)
