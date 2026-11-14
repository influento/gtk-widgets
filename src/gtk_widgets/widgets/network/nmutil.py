"""libnm helpers shared by the network popup (main.py) and network-agent (agent.py)."""

import base64
import binascii
import os
import re
import socket
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

from gi.repository import NM, GLib

# libnm's NM80211ApSecurityFlags and NM80211ApFlags: Python can't name those
# classes (a digit first), so the stubs give the flags as plain GFlags
SEC_KEY_MGMT_PSK = 0x100
SEC_KEY_MGMT_802_1X = 0x200
SEC_KEY_MGMT_SAE = 0x400
SEC_KEY_MGMT_OWE = 0x800
SEC_KEY_MGMT_OWE_TM = 0x1000
SEC_KEY_MGMT_EAP_SUITE_B_192 = 0x2000
AP_FLAGS_PRIVACY = 0x1

VPN_TYPES = ("wireguard", "vpn")
HOTSPOT_ID = "Hotspot"

ICON = {
    "wifi": "\U000f05a9",  # nf-md-wifi: one glyph at any strength, colour marks a weak signal
    "wired": "\U000f0200",  # nf-md-ethernet
    "vpn": "\U000f0582",  # nf-md-vpn
    "hotspot": "\U000f0002",  # nf-md-access_point_network
    "lock": "\U000f033e",  # nf-md-lock
    "check": "\U000f012c",  # nf-md-check
    "cross": "\U000f0156",  # nf-md-close
    "proxy": "\U000f048d",  # nf-md-server_network
    "settings": "\U000f0493",  # nf-md-cog
    "saved": "\U000f0193",  # nf-md-content_save
    "expand": "\U000f0142",  # nf-md-chevron_right
    "collapse": "\U000f0140",  # nf-md-chevron_down
    "rescan": "\U000f0450",  # nf-md-refresh
    "back": "\U000f004d",  # nf-md-arrow_left
    "edit": "\U000f03eb",  # nf-md-pencil
    "delete": "\U000f0a7a",  # nf-md-trash_can_outline
    "export": "\U000f0207",  # nf-md-export
    "offline": "\U000f0c9c",  # nf-md-network_off_outline
    "portal": "\U000f0342",  # nf-md-login
    "limited": "\U000f0a8e",  # nf-md-web_off
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
    "ams": "Amsterdam",
    "buc": "Bucharest",
    "chi": "Chicago",
    "dub": "Dubai",
    "hel": "Helsinki",
    "hkg": "Hong Kong",
    "leu": "Andorra",
    "mcm": "Monaco",
    "nyc": "New York",
    "waw": "Warsaw",
    "lon": "London",
    "fra": "Frankfurt",
    "par": "Paris",
    "sto": "Stockholm",
    "zrh": "Zurich",
    "tyo": "Tokyo",
}
# Chișinău shares "chi" with Chicago; the country code disambiguates
VPN_PLACES = {"md-chi": "Chișinău"}
COUNTRY_CODE_LEN = 2


# NM's connectivity check results that mean "connected, but no working internet".
# UNKNOWN (checks disabled or not run yet) and FULL are not problems.
CONNECTIVITY_PROBLEMS = {
    NM.ConnectivityState.PORTAL: (
        "portal",
        "Captive portal: sign in to reach the internet",
    ),
    NM.ConnectivityState.LIMITED: ("limited", "Limited: connected, but no internet"),
    NM.ConnectivityState.NONE: ("none", "No internet access"),
}


def nullable[T](value: T) -> T | None:
    """value as what libnm may return: the stubs drop the nullable mark of
    getters such as get_primary_connection() and get_connection()."""
    return value


def vpn_place(name: str) -> str | None:
    """'nl-ams' -> 'Amsterdam'; None when the name is not a location code."""
    if name in VPN_PLACES:
        return VPN_PLACES[name]
    match name.split("-"):
        case [country, city] if len(country) == COUNTRY_CODE_LEN:
            return VPN_CITIES.get(city)
        case _:
            return None


def kernel_stale() -> bool:
    """The running kernel's modules are gone (package upgraded, no reboot yet)."""
    return not Path(f"/lib/modules/{os.uname().release}").is_dir()


def error_text(err: BaseException) -> str:
    """Readable message for a libnm GLib.Error, with a hint for missing kernel modules."""
    msg = err.message if isinstance(err, GLib.Error) else str(err)
    if "Operation not supported" in msg and kernel_stale():
        msg += " (kernel updated: reboot to load its modules)"
    return msg


def reapply_refusal_text(err: GLib.Error) -> str:
    """Why NM refused a reapply, shortened to the setting that cannot change live."""
    m = re.search(r"reapply (?:any )?changes to '([^']+)'", err.message or "")
    return f"{m.group(1)} cannot change while connected" if m else error_text(err)


def device_reason_text(reason: int) -> str:
    known = NM.DeviceStateReason(reason)
    return DEVICE_REASONS.get(known) or known.value_nick.replace("-", " ")


def ac_reason_text(reason: int) -> str:
    known = NM.ActiveConnectionStateReason(reason)
    return AC_REASONS.get(known) or known.value_nick.replace("-", " ")


def failure_text(
    reason: int, devices: Sequence[NM.Device], conn: NM.Connection | None
) -> str:
    """device_reason_text for a failed activation of `conn` (a clone taken when it
    started: NM deletes a volatile profile on failure). NM reports a Wi-Fi association
    timeout as ssid-not-found even while a matching access point is in the scan list:
    then it ignored the auth frames (a router that only a restart fixed)."""
    if (
        reason == NM.DeviceStateReason.SSID_NOT_FOUND
        and conn is not None
        and any(
            ap.connection_valid(conn)
            for d in devices
            if isinstance(d, NM.DeviceWifi)
            for ap in d.get_access_points()
        )
    ):
        return "the router did not answer (restart it?)"
    return device_reason_text(reason)


def hidden_connection(conn: NM.RemoteConnection) -> bool:
    """Profiles NM does not own (docker bridges, lo): never shown or touched."""
    return (
        bool(conn.get_flags() & NM.SettingsConnectionFlags.EXTERNAL)
        or conn.get_connection_type() == "loopback"
    )


def ssid_text(ssid: GLib.Bytes | None) -> str | None:
    """GLib.Bytes SSID -> display string (None for hidden APs)."""
    if ssid is None:
        return None
    data = ssid.get_data()
    return NM.utils_ssid_to_utf8(data) if data else None


def connection_ssid(conn: NM.Connection) -> str | None:
    s_wifi = conn.get_setting_wireless()
    return ssid_text(s_wifi.get_ssid()) if s_wifi else None


def is_hotspot(conn: NM.Connection) -> bool:
    s_wifi = conn.get_setting_wireless()
    return bool(s_wifi) and s_wifi.get_mode() == "ap"


def is_vpn(ac: NM.ActiveConnection) -> bool:
    return ac.get_connection_type() in VPN_TYPES or ac.get_vpn()


def link_connection(client: NM.Client) -> NM.ActiveConnection | None:
    """The activated connection carrying traffic below any VPN: the primary one,
    or while a VPN is primary, the first other one (Wi-Fi and wired first)."""
    primary = nullable(client.get_primary_connection())
    if primary is not None and not is_vpn(primary):
        return primary
    acs: list[NM.ActiveConnection] = []
    for ac in client.get_active_connections():
        conn = nullable(ac.get_connection())
        if (
            ac.get_state() != NM.ActiveConnectionState.ACTIVATED
            or is_vpn(ac)
            or ac.get_connection_type() == "loopback"
            or (conn is not None and hidden_connection(conn))
        ):
            continue
        acs.append(ac)
    acs.sort(key=_not_wifi_or_wired)
    return acs[0] if acs else None


def _not_wifi_or_wired(ac: NM.ActiveConnection) -> bool:
    return ac.get_connection_type() not in {"802-11-wireless", "802-3-ethernet"}


def connectivity_problem(client: NM.Client) -> tuple[str, str] | None:
    """(kind, text) when NM's connectivity check found a problem, else None."""
    return CONNECTIVITY_PROBLEMS.get(client.get_connectivity())


WEAK, VERY_WEAK = 30, 5  # nm-applet's lowest two signal thresholds


def signal_class(strength: int | None) -> str | None:
    """ "weak" (6-30%), "very-weak" (0-5%) or None (stronger, or unknown): the
    bar and the popup colour the one Wi-Fi glyph by it. NM's percentage comes
    from the last scan and jumps by 20 points, so level glyphs said little."""
    if strength is None or strength > WEAK:
        return None
    return "very-weak" if strength <= VERY_WEAK else "weak"


def ap_security(ap: NM.AccessPoint) -> tuple[str, str]:
    """(kind, label) for an access point. kind: open, owe, wep, psk, sae, eap."""
    wpa, rsn = int(ap.get_wpa_flags()), int(ap.get_rsn_flags())
    both = wpa | rsn
    if both & (SEC_KEY_MGMT_802_1X | SEC_KEY_MGMT_EAP_SUITE_B_192):
        return "eap", "WPA2 Enterprise" if rsn else "WPA Enterprise"
    if rsn & SEC_KEY_MGMT_SAE:
        if rsn & SEC_KEY_MGMT_PSK:
            return "psk", "WPA2/WPA3 Personal"
        return "sae", "WPA3 Personal"
    if both & SEC_KEY_MGMT_PSK:
        return "psk", "WPA2 Personal" if rsn else "WPA Personal"
    if rsn & (SEC_KEY_MGMT_OWE | SEC_KEY_MGMT_OWE_TM):
        return "owe", "Enhanced Open (OWE)"
    if int(ap.get_flags()) & AP_FLAGS_PRIVACY:
        return "wep", "WEP"
    return "open", "Open"


KEY_MGMT_LABELS = {
    "none": "WEP",
    "ieee8021x": "Dynamic WEP (802.1X)",
    "owe": "Enhanced Open (OWE)",
    "wpa-psk": "WPA/WPA2 Personal",
    "sae": "WPA3 Personal",
    "wpa-eap": "WPA/WPA2 Enterprise",
    "wpa-eap-suite-b-192": "WPA3 Enterprise",
}


def connection_security(conn: NM.Connection) -> str:
    s_wsec = conn.get_setting_wireless_security()
    if not s_wsec:
        return "Open"
    km = s_wsec.get_key_mgmt()
    return KEY_MGMT_LABELS.get(km, km)


BAND_5GHZ_MHZ, BAND_6GHZ_MHZ = 3000, 5925  # where the 5 and 6 GHz bands start
MINUTE, HOUR, DAY = 60, 3600, 86400
RECENT_DAYS = 30  # older times show as a date


def freq_band(mhz: int) -> str:
    """'5 GHz, channel 36' for a frequency in MHz."""
    band = (
        "2.4 GHz"
        if mhz < BAND_5GHZ_MHZ
        else "5 GHz"
        if mhz < BAND_6GHZ_MHZ
        else "6 GHz"
    )
    return f"{band}, channel {NM.utils_wifi_freq_to_channel(mhz)}"


def relative_time(ts: float, now: float | None = None) -> str:
    if not ts:
        return "never"
    delta = max(0, (now or time.time()) - ts)
    if delta < MINUTE:
        return "just now"
    if delta < HOUR:
        return f"{int(delta // MINUTE)} min ago"
    if delta < DAY:
        return f"{int(delta // HOUR)} h ago"
    if delta < RECENT_DAYS * DAY:
        return f"{int(delta // DAY)} d ago"
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def ip_lines(ipcfg: NM.IPConfig | None) -> tuple[list[str], str | None, list[str]]:
    """(addresses, gateway, dns) of an NM.IPConfig as display strings."""
    if not ipcfg:
        return [], None, []
    addrs = [f"{a.get_address()}/{a.get_prefix()}" for a in ipcfg.get_addresses()]
    return addrs, ipcfg.get_gateway(), list(ipcfg.get_nameservers() or [])


# --- building connections ---


def _base_connection(
    conn_id: str,
    conn_type: str,
    *,
    autoconnect: bool = True,
    iface: str | None = None,
) -> NM.Connection:
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


def wifi_connection(
    ssid: str, kind: str, password: str | None = None, *, hidden: bool = False
) -> NM.Connection:
    """Client profile for `ssid`. kind: open, owe, psk, sae. Secrets are
    system-owned (flags 0), as nmcli stores them by default."""
    conn = _base_connection(ssid, "802-11-wireless")
    s_wifi = NM.SettingWireless.new()
    s_wifi.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(ssid.encode()))
    s_wifi.set_property(NM.SETTING_WIRELESS_MODE, "infrastructure")
    if hidden:
        s_wifi.set_property(NM.SETTING_WIRELESS_HIDDEN, hidden)
    conn.add_setting(s_wifi)
    if kind in {"psk", "sae", "owe"}:
        s_wsec = NM.SettingWirelessSecurity.new()
        s_wsec.set_property(
            NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, {"psk": "wpa-psk"}.get(kind, kind)
        )
        if kind != "owe":
            s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            s_wsec.set_property(
                NM.SETTING_WIRELESS_SECURITY_PSK_FLAGS, NM.SettingSecretFlags.NONE
            )
        conn.add_setting(s_wsec)
    return conn


def hotspot_connection(
    ssid: str, password: str, band: str, iface: str | None
) -> NM.Connection:
    """Access point with NAT (ipv4.method=shared), never autoconnected.
    band: 'bg' (2.4 GHz) or 'a' (5 GHz). Mirrors `nmcli device wifi hotspot`."""
    conn = _base_connection(
        HOTSPOT_ID, "802-11-wireless", autoconnect=False, iface=iface
    )
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
    s_wsec.set_property(
        NM.SETTING_WIRELESS_SECURITY_PMF, int(NM.SettingWirelessSecurityPmf.DISABLE)
    )
    conn.add_setting(s_wsec)
    s_ip4 = NM.SettingIP4Config.new()
    s_ip4.set_property(NM.SETTING_IP_CONFIG_METHOD, "shared")
    conn.add_setting(s_ip4)
    s_ip6 = NM.SettingIP6Config.new()
    s_ip6.set_property(NM.SETTING_IP_CONFIG_METHOD, "ignore")
    conn.add_setting(s_ip6)
    return conn


# --- Enterprise (802.1X) without certificates: PEAP / TTLS, username + password ---

EAP_METHODS = [("peap", "PEAP"), ("ttls", "TTLS")]
# inner authentication per method: (value, label, 802-1x property that holds it)
EAP_INNER = {
    "peap": [
        ("mschapv2", "MSCHAPv2", "phase2-auth"),
        ("gtc", "GTC", "phase2-auth"),
        ("md5", "MD5", "phase2-auth"),
    ],
    "ttls": [
        ("pap", "PAP", "phase2-auth"),
        ("mschap", "MSCHAP", "phase2-auth"),
        ("mschapv2", "MSCHAPv2", "phase2-auth"),
        ("chap", "CHAP", "phase2-auth"),
        ("gtc", "GTC", "phase2-autheap"),
    ],
}
_EAP_CERTS = (
    "ca-cert",
    "ca-path",
    "client-cert",
    "phase2-ca-cert",
    "phase2-ca-path",
    "phase2-client-cert",
    "private-key",
    "phase2-private-key",
)


class EapValues(TypedDict):
    """A PEAP/TTLS password setting as the Enterprise form edits it."""

    method: str
    inner: str
    identity: str
    anonymous: str
    domain: str
    ask: bool  # "Ask every time": the password is not saved


def eap_values(s_8021x: NM.Setting8021x | None) -> EapValues | None:
    """{method, inner, identity, anonymous, domain, ask} of a PEAP/TTLS
    password setting without certificates, or None when it is anything else
    (TLS, several methods, certificate files: not supported here)."""
    if s_8021x is None:
        return None
    eap = [s_8021x.get_eap_method(i) for i in range(s_8021x.get_num_eap_methods())]
    if len(eap) != 1 or eap[0] not in EAP_INNER:
        return None
    if s_8021x.get_system_ca_certs() or any(_is_set(s_8021x, p) for p in _EAP_CERTS):
        return None
    auth, autheap = s_8021x.get_phase2_auth(), s_8021x.get_phase2_autheap()
    inner = None
    for value, _label, prop in EAP_INNER[eap[0]]:
        if (prop == "phase2-auth" and auth == value and not autheap) or (
            prop == "phase2-autheap" and autheap == value and not auth
        ):
            inner = value
    if inner is None and (auth or autheap):
        return None  # an inner method this form doesn't offer
    return {
        "method": eap[0],
        "inner": inner or EAP_INNER[eap[0]][0][0],
        "identity": s_8021x.get_identity() or "",
        "anonymous": s_8021x.get_anonymous_identity() or "",
        "domain": s_8021x.get_domain_suffix_match() or "",
        "ask": bool(s_8021x.get_password_flags() & NM.SettingSecretFlags.NOT_SAVED),
    }


def _is_set(setting: NM.Setting, prop: str) -> bool:
    value: object = setting.get_property(prop)
    return bool(value)


def apply_eap(
    s_8021x: NM.Setting8021x, values: EapValues, password: str | None = None
) -> None:
    """Write eap_values()-shaped `values` into an 802-1x setting. `password`
    None leaves the stored one alone; "Ask every time" drops it (NOT_SAVED)."""
    inner = next(e for e in EAP_INNER[values["method"]] if e[0] == values["inner"])
    s_8021x.set_property("eap", [values["method"]])
    s_8021x.set_property("identity", values["identity"])
    s_8021x.set_property("anonymous-identity", values["anonymous"] or None)
    s_8021x.set_property("domain-suffix-match", values["domain"] or None)
    s_8021x.set_property("phase2-auth", inner[0] if inner[2] == "phase2-auth" else None)
    s_8021x.set_property(
        "phase2-autheap", inner[0] if inner[2] == "phase2-autheap" else None
    )
    flags = s_8021x.get_password_flags()
    if values["ask"]:
        s_8021x.set_property("password-flags", flags | NM.SettingSecretFlags.NOT_SAVED)
        s_8021x.set_property("password", None)
    else:
        s_8021x.set_property("password-flags", flags & ~NM.SettingSecretFlags.NOT_SAVED)
        if password is not None:
            s_8021x.set_property("password", password)


def eap_problem(
    values: EapValues, password: str | None, *, password_known: bool
) -> str | None:
    """Why these Enterprise fields can't work, or None. password_known: a
    password is stored already (editing) and the field was left alone."""
    if not values["identity"].strip():
        return "Enter the username (identity)"
    if not values["ask"] and not password and not password_known:
        return "Enter the password, or choose Ask every time"
    return None


def eap_connection(ssid: str, values: EapValues, password: str | None) -> NM.Connection:
    """New WPA/WPA2 Enterprise client profile (PEAP/TTLS, no CA certificate)."""
    conn = wifi_connection(ssid, "open")
    s_wsec = NM.SettingWirelessSecurity.new()
    s_wsec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, "wpa-eap")
    conn.add_setting(s_wsec)
    s_8021x = NM.Setting8021x.new()
    apply_eap(s_8021x, values, password)
    conn.add_setting(s_8021x)
    return conn


# --- field checks for the editor ---


WG_KEY_BYTES = 32
MAC_BYTES = 6


def wg_key_problem(key: str, what: str = "Key") -> str | None:
    """WireGuard keys are 32 bytes of base64."""
    try:
        raw = base64.b64decode(key, validate=True)
    except binascii.Error, ValueError:
        raw = b""
    return (
        None
        if len(raw) == WG_KEY_BYTES
        else f"{what} must be 32 bytes of base64 (44 characters)"
    )


def mac_problem(mac: str) -> str | None:
    return (
        None
        if NM.utils_hwaddr_valid(mac, MAC_BYTES)
        else "Not a MAC address (aa:bb:cc:dd:ee:ff)"
    )


def parse_ip(text: str, family: int) -> str:
    """'addr' -> addr, or raise ValueError. family: socket.AF_INET / AF_INET6."""
    text = text.strip()
    if not NM.utils_ipaddr_valid(family, text):
        raise ValueError(
            f"{text or 'empty'}: not an IPv{4 if family == socket.AF_INET else 6} address"
        )
    return text


def parse_cidr(
    text: str, family: int, default_prefix: int | None = None
) -> tuple[str, int]:
    """'addr/prefix' -> (addr, prefix), or raise ValueError."""
    addr, _, prefix = text.strip().partition("/")
    addr = parse_ip(addr, family)
    top = IPV4_BITS if family == socket.AF_INET else IPV6_BITS
    if not prefix and default_prefix is not None:
        return addr, default_prefix
    if not prefix.isdigit() or not 0 <= int(prefix) <= top:
        raise ValueError(f"{text.strip()}: needs /prefix (0-{top})")
    return addr, int(prefix)


IPV4_BITS, IPV6_BITS = 32, 128


def password_problem(kind: str, password: str) -> str | None:
    """Why `password` can't work for security `kind`, or None."""
    if kind == "psk" and not NM.utils_wpa_psk_valid(password):
        return "WPA passwords are 8-63 characters (or 64 hex digits)"
    if kind == "sae" and not password:
        return "Enter a password"
    return None


# --- WireGuard export ---


def _ip_setting_values(conn: NM.Connection) -> tuple[list[str], list[str]]:
    addrs: list[str] = []
    dns: list[str] = []
    settings: tuple[NM.SettingIPConfig | None, ...] = (
        conn.get_setting_ip4_config(),
        conn.get_setting_ip6_config(),
    )
    for s_ip in settings:
        if not s_ip:
            continue
        for i in range(s_ip.get_num_addresses()):
            a = s_ip.get_address(i)
            addrs.append(f"{a.get_address()}/{a.get_prefix()}")
        dns += [s_ip.get_dns(i) for i in range(s_ip.get_num_dns())]
        # "~" and "~domain" are NM routing-only domains (the importer adds "~"
        # to send all DNS through the tunnel); wg-quick has no such notion
        dns += [
            d
            for d in (
                s_ip.get_dns_search(i) for i in range(s_ip.get_num_dns_searches())
            )
            if not d.startswith("~")
        ]
    return addrs, list(dict.fromkeys(dns))


def wireguard_conf(conn: NM.Connection) -> str:
    """wg-quick .conf text for a WireGuard profile whose secrets have been
    merged in (private key, peer preshared keys). Inverse of the fields
    NM.conn_wireguard_import() reads."""
    s_wg = conn.get_setting_by_name(NM.SETTING_WIREGUARD_SETTING_NAME)
    if not isinstance(s_wg, NM.SettingWireGuard):
        raise TypeError("wireguard_conf() needs a WireGuard profile")
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
        allowed = [
            peer.get_allowed_ip(j, None) for j in range(peer.get_allowed_ips_len())
        ]
        allowed = [a for a in allowed if a]
        if allowed:
            lines.append(f"AllowedIPs = {', '.join(allowed)}")
        if peer.get_endpoint():
            lines.append(f"Endpoint = {peer.get_endpoint()}")
        if peer.get_persistent_keepalive():
            lines.append(f"PersistentKeepalive = {peer.get_persistent_keepalive()}")
    return "\n".join(lines) + "\n"


def write_private(path: str, text: str) -> None:
    """Write `text` to `path` readable by the owner only (mode 0600)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o600)  # an existing file keeps its old mode otherwise
        _ = f.write(text)
