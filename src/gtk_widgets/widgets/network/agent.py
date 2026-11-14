#!/usr/bin/env python3
"""network-agent — long-running NetworkManager companion to the network popup.

- Notifications (notify-send) when a connection comes up, drops or fails, when
  a VPN goes up or down, and when NM's connectivity check finds a captive
  portal. Only transitions seen while running are reported.
- Proxy rules: notifies when sing-box (gtk-widgets-proxy.service) starts,
  stops or dies, and when a proxy in use stops answering or answers again.
- Secret agent: NetworkManager asks it for missing secrets (a changed Wi-Fi
  password, a password needed at connect time, a WireGuard private key) and it
  asks the user with a layer-shell prompt. Secrets are returned, never stored
  here: NM keeps system-owned secrets (flags 0) in the profile itself, the way
  nmcli does by default.

Runs as a single instance (GApplication id); start it from the compositor.
"""

import contextlib
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import override

from gi.repository import NM, Gio, GLib, GObject

from gtk_widgets.lib.theme import render_css
from gtk_widgets.lib.ui.background import in_background
from gtk_widgets.lib.ui.copy_label import copyable
from gtk_widgets.lib.ui.widget_base import (
    BASE_CSS,
    Gdk,
    Gtk,
    install_css,
    load_css,
    popup_window,
    show_popup,
)
from gtk_widgets.widgets.network import proxy as px
from gtk_widgets.widgets.network import socks5
from gtk_widgets.widgets.network.nmutil import (
    ICON,
    VPN_TYPES,
    ac_reason_text,
    connection_ssid,
    failure_text,
    hidden_connection,
    is_hotspot,
    link_connection,
    nullable,
)
from gtk_widgets.widgets.network.parse import Proxy

STYLE_CSS = Path(__file__).resolve().parent / "style.css"

APP_ID = "dev.dotfiles.network-agent"
AC_STATE = NM.ActiveConnectionState
GetFlags = NM.SecretAgentGetSecretsFlags
MARGIN_TOP = 40
PROXY_PROBE_S = 60  # liveness probe of the proxies in use while Proxy rules is on
PROXY_FIRST_PROBE_S = 5  # the first probe after Proxy rules comes on
PROXY_FAILS = 2  # consecutive failed probes before "not answering"

# NM's secret agent callbacks. Their stubs end in the vfunc's user_data, but
# PyGObject binds that to the callback, which takes only these arguments.
type SecretsReply = Callable[
    [NM.SecretAgentOld, NM.Connection, GLib.Variant | None, GLib.Error | None], None
]
type SecretsDone = Callable[[NM.SecretAgentOld, NM.Connection, GLib.Error | None], None]
type Fields = list[tuple[str, str]]  # [(secret key, label)]


def notify(
    summary: str,
    body: str = "",
    icon: str = "network-wireless",
    urgency: str = "normal",
) -> None:
    with contextlib.suppress(OSError):
        _ = subprocess.Popen(
            ["notify-send", "-a", "Network", "-u", urgency, "-i", icon, summary, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def agent_error(code: int, message: str) -> GLib.Error:
    domain = GLib.quark_to_string(NM.SecretAgentError.quark())
    return GLib.Error(message, domain, code)


# --- notifications ---


@dataclass(slots=True)
class _Watched:
    """An active connection being followed."""

    up: bool
    devices: list[NM.Device]
    # a clone: NM deletes a volatile profile when its activation fails
    conn: NM.Connection | None
    done: bool = False
    reason: int | None = None  # the last device state reason worth reporting
    handlers: list[tuple[NM.Device, int]] = field(
        default_factory=list[tuple[NM.Device, int]]
    )
    ac_handler: int = 0


def _describe(ac: NM.ActiveConnection) -> tuple[str, str, str]:
    """(kind, display name, icon)"""
    ctype, conn = ac.get_connection_type(), nullable(ac.get_connection())
    if ctype in VPN_TYPES or ac.get_vpn():
        return "vpn", ac.get_id(), "network-vpn"
    if ctype == "802-11-wireless":
        name = (connection_ssid(conn) if conn else None) or ac.get_id()
        if conn and is_hotspot(conn):
            return "hotspot", name, "network-wireless-hotspot"
        return "wifi", name, "network-wireless"
    if ctype == "802-3-ethernet":
        return "wired", ac.get_id(), "network-wired"
    return "other", ac.get_id(), "network-wired"


class Notifier:
    """Follows every active connection and reports its transitions."""

    def __init__(self, client: NM.Client) -> None:
        self.client = client
        self._watched: dict[str, _Watched] = {}  # by the AC's object path
        _ = client.connect("active-connection-added", self._added)
        _ = client.connect("active-connection-removed", self._removed)
        for ac in client.get_active_connections():
            self._watch(ac, initial=True)
        self._portal = client.get_connectivity() == NM.ConnectivityState.PORTAL
        _ = client.connect("notify::connectivity", self._connectivity_changed)

    def _connectivity_changed(
        self, client: NM.Client, _pspec: GObject.ParamSpec
    ) -> None:
        portal = client.get_connectivity() == NM.ConnectivityState.PORTAL
        if portal and not self._portal:
            link = link_connection(client)
            name = _describe(link)[1] if link else "This network"
            notify(
                "Sign in to the network",
                f"{name} has a captive portal: open the network popup to sign in",
                "network-wireless",
            )
        self._portal = portal

    def _added(self, _client: NM.Client, ac: NM.ActiveConnection) -> None:
        self._watch(ac, initial=False)

    def _watch(self, ac: NM.ActiveConnection, *, initial: bool) -> None:
        conn = nullable(ac.get_connection())
        if conn is not None and hidden_connection(conn):
            return
        if ac.get_connection_type() == "loopback" or ac.get_path() in self._watched:
            return
        info = _Watched(
            up=ac.get_state() == AC_STATE.ACTIVATED if initial else False,
            devices=list(ac.get_devices()),
            conn=NM.SimpleConnection.new_clone(conn) if conn is not None else None,
        )

        def dev_changed(_dev: NM.Device, _new: int, _old: int, reason: int) -> None:
            if reason not in {
                NM.DeviceStateReason.NONE,
                NM.DeviceStateReason.UNKNOWN,
            }:
                info.reason = reason

        def changed(ac: NM.ActiveConnection, state: int, reason: int) -> None:
            self._changed(ac, state, reason, info)

        info.handlers = [
            (d, d.connect("state-changed", dev_changed)) for d in info.devices
        ]
        info.ac_handler = ac.connect("state-changed", changed)
        self._watched[ac.get_path()] = info
        if not initial and ac.get_state() == AC_STATE.ACTIVATED:
            self._changed(ac, AC_STATE.ACTIVATED, 0, info)

    def _changed(
        self, ac: NM.ActiveConnection, state: int, reason: int, info: _Watched
    ) -> None:
        if info.done:
            return
        kind, name, icon = _describe(ac)
        if state == AC_STATE.ACTIVATED and not info.up:
            info.up = True
            if kind == "vpn":
                notify("VPN connected", name, icon)
            elif kind == "hotspot":
                notify("Hotspot started", name, icon)
            else:
                notify(f"Connected to {name}", "", icon)
        elif state == AC_STATE.DEACTIVATED:
            self._finish(ac, info, reason)

    def _removed(self, _client: NM.Client, ac: NM.ActiveConnection) -> None:
        info = self._watched.get(ac.get_path())
        if info and not info.done:
            self._finish(ac, info, None)

    def _finish(
        self, ac: NM.ActiveConnection, info: _Watched, reason: int | None
    ) -> None:
        info.done = True
        # handler_disconnect: NM.Device.disconnect() would disconnect the device
        for d, h in info.handlers:
            d.handler_disconnect(h)
        ac.handler_disconnect(info.ac_handler)
        _ = self._watched.pop(ac.get_path(), None)
        kind, name, _icon = _describe(ac)
        user = reason == NM.ActiveConnectionStateReason.USER_DISCONNECTED
        if info.reason is not None and not user:
            why = failure_text(info.reason, info.devices, info.conn)
        else:
            why = ac_reason_text(reason) if reason is not None else ""
        if info.up:
            if kind == "vpn":
                notify(
                    "VPN disconnected",
                    f"{name}" + ("" if user or not why else f": {why}"),
                    "network-vpn-disconnected",
                )
            elif kind == "hotspot":
                notify("Hotspot stopped", name, "network-wireless-hotspot")
            else:
                notify(
                    f"Disconnected from {name}", "" if user else why, "network-offline"
                )
        elif not user:
            notify(f"Could not connect to {name}", why, "network-error", "critical")


# --- Proxy rules ---


def _print_bug(text: str) -> None:
    print(f"network-agent: {text}", file=sys.stderr)


class ProxyMonitor:
    """Follows gtk-widgets-proxy.service and probes the proxies in use."""

    def __init__(self) -> None:
        self._was: str | None = None  # "up" / "down" / "crashed" as last seen
        self._fails: dict[str, int] = {}  # proxy id -> consecutive failed probes
        self._down: set[str] = set()  # proxy ids reported as not answering
        self._probing = False
        self.watch = px.ServiceWatch(self._changed)
        _ = GLib.timeout_add_seconds(PROXY_PROBE_S, self._probe)

    def _changed(self, w: px.ServiceWatch) -> None:
        now = (
            "up"
            if w.active
            else "crashed"
            if w.crashed
            else "down"
            if w.state == "inactive"
            else None
        )  # activating/deactivating: wait for where it lands
        if now is None or now == self._was:
            return
        was, self._was = self._was, now
        if was is None:
            return  # the state at startup is not a transition
        st = px.load_state()
        if now == "up":
            notify(
                "Proxy rules back on" if was == "crashed" else "Proxy rules on",
                px.summary(st),
                "network-vpn",
            )
            self._fails.clear()
            self._down.clear()
            _ = GLib.timeout_add_seconds(PROXY_FIRST_PROBE_S, self._probe_once)
        elif now == "crashed":
            restarting = w.sub_state == "auto-restart"
            body = "sing-box exited" + (
                "; restarting" if restarting else f" (journalctl -u {px.UNIT})"
            )
            body += (
                ". Kill switch: internet is blocked until you pick another exit"
                if st.kill_switch
                else ". Proxied apps are unprotected until it is back"
            )
            notify("Proxy rules stopped", body, "network-error", "critical")
        elif was == "up":
            notify("Proxy rules off", "", "network-vpn-disconnected")

    def _probe_once(self) -> bool:
        _ = self._probe()
        return GLib.SOURCE_REMOVE

    def _probe(self) -> bool:
        if self._was == "up" and not self._probing:
            st = px.load_state()
            used = {r.exit for r in st.rules} | {st.default}
            proxies = [p for p in st.proxies if p.id in used]
            if proxies:
                self._probing = True

                def probe_all() -> None:
                    self._probe_all(proxies)

                in_background(probe_all, _print_bug)
        return GLib.SOURCE_CONTINUE

    def _probe_all(self, proxies: list[Proxy]) -> None:
        results = [
            (p.id, socks5.alive(p.host, p.port, p.username, p.password))
            for p in proxies
        ]
        _ = GLib.idle_add(self._probed, results)

    def _probed(self, results: list[tuple[str, tuple[bool, str | None]]]) -> bool:
        self._probing = False
        if self._was != "up":
            return GLib.SOURCE_REMOVE
        st = px.load_state()
        for pid, (ok, err) in results:
            apps = [r.app for r in st.rules if r.exit == pid]
            if st.default == pid:
                apps.append("everything else")
            if ok:
                _ = self._fails.pop(pid, None)
                if pid in self._down:
                    self._down.discard(pid)
                    notify(f"Proxy {pid} answers again", ", ".join(apps), "network-vpn")
                continue
            self._fails[pid] = self._fails.get(pid, 0) + 1
            if self._fails[pid] >= PROXY_FAILS and pid not in self._down:
                self._down.add(pid)
                notify(
                    f"Proxy {pid} is not answering",
                    f"{err}. No connection for: {', '.join(apps)}",
                    "network-error",
                    "critical",
                )
        return GLib.SOURCE_REMOVE


# --- secret agent ---


def _wireless_fields(s_wsec: NM.SettingWirelessSecurity | None) -> Fields | None:
    if s_wsec is None:
        return None
    match s_wsec.get_key_mgmt():
        case "wpa-psk" | "sae":
            return [(NM.SETTING_WIRELESS_SECURITY_PSK, "Password")]
        case "none":
            return [(f"wep-key{s_wsec.get_wep_tx_keyidx()}", "WEP key")]
        case "ieee8021x" if s_wsec.get_auth_alg() == "leap":
            return [(NM.SETTING_WIRELESS_SECURITY_LEAP_PASSWORD, "Password")]
        case _:
            return None


def prompt_fields(
    connection: NM.Connection, setting_name: str, hints: Sequence[str]
) -> Fields | None:
    """The secrets to ask for, or None if this agent can't serve them."""
    if setting_name == NM.SETTING_WIRELESS_SECURITY_SETTING_NAME:
        return _wireless_fields(nullable(connection.get_setting_wireless_security()))
    if setting_name == NM.SETTING_802_1X_SETTING_NAME:
        return [(NM.SETTING_802_1X_PASSWORD, "Password")]
    if setting_name == NM.SETTING_WIREGUARD_SETTING_NAME and (
        not hints or NM.SETTING_WIREGUARD_PRIVATE_KEY in hints
    ):
        return [(NM.SETTING_WIREGUARD_PRIVATE_KEY, "Private key")]
    return None


@dataclass(slots=True, frozen=True)
class Request:
    agent: NM.SecretAgentOld
    connection: NM.Connection
    path: str
    setting_name: str
    fields: Fields
    flags: int  # NM.SecretAgentGetSecretsFlags
    callback: SecretsReply

    def matches(self, path: str, setting_name: str) -> bool:
        return self.path == path and self.setting_name == setting_name

    def reply(self, values: dict[str, str]) -> None:
        secrets = GLib.Variant(
            "a{sa{sv}}",
            {self.setting_name: {k: GLib.Variant("s", v) for k, v in values.items()}},
        )
        self.callback(self.agent, self.connection, secrets, None)

    def fail(self, code: int, message: str) -> None:
        self.callback(self.agent, self.connection, None, agent_error(code, message))


class PromptAgent(NM.SecretAgentOld):
    """Forwards NM's secret requests to the application's prompt queue."""

    def __init__(self, app: NetworkAgent) -> None:
        super().__init__(identifier=APP_ID, auto_register=True)
        self.app = app

    # The vfuncs also receive the callback's user_data; the callback binds it
    # itself. Callable[..., None]: the stubs' callback types list it too.
    @override
    def do_get_secrets(
        self,
        connection: NM.Connection,
        path: str,
        setting_name: str,
        hints: Sequence[str],
        flags: int | str | tuple[str, ...],
        callback: Callable[..., None],
        _data: int | None,
    ) -> None:
        if not isinstance(flags, int):  # the stub's type also takes flag names
            raise TypeError(f"get_secrets flags: {flags!r}")
        fields = prompt_fields(connection, setting_name, hints)
        reply: SecretsReply = callback
        req = Request(self, connection, path, setting_name, fields or [], flags, reply)
        if not fields:
            req.fail(
                NM.SecretAgentError.NOSECRETS,
                f"network-agent cannot provide {setting_name} secrets",
            )
        elif not flags & GetFlags.ALLOW_INTERACTION:
            # nothing stored here; NM already has what the profile keeps
            req.fail(NM.SecretAgentError.NOSECRETS, "no stored secrets")
        else:
            self.app.enqueue(req)

    @override
    def do_cancel_get_secrets(self, path: str, setting_name: str) -> None:
        self.app.cancel(path, setting_name)

    @override
    def do_save_secrets(
        self,
        connection: NM.Connection,
        path: str,
        callback: Callable[..., None],
        _data: int | None,
    ) -> None:
        done: SecretsDone = callback
        done(self, connection, None)  # agent-owned secrets are not kept

    @override
    def do_delete_secrets(
        self,
        connection: NM.Connection,
        path: str,
        callback: Callable[..., None],
        _data: int | None,
    ) -> None:
        done: SecretsDone = callback
        done(self, connection, None)


class Prompt:
    """Layer-shell password prompt for one request."""

    def __init__(self, app: NetworkAgent, req: Request) -> None:
        self.app, self.req = app, req
        conn = req.connection
        wifi = req.setting_name in {
            NM.SETTING_WIRELESS_SECURITY_SETTING_NAME,
            NM.SETTING_802_1X_SETTING_NAME,
        }
        name = (connection_ssid(conn) if wifi else None) or conn.get_id()
        if req.setting_name == NM.SETTING_WIREGUARD_SETTING_NAME:
            title, glyph = "WireGuard key required", ICON["vpn"]
        elif wifi:
            title, glyph = "Wi-Fi password required", ICON["wifi"]
        else:
            title, glyph = "Password required", ICON["lock"]
        what = {NM.SETTING_WIREGUARD_SETTING_NAME: "its private key"}.get(
            req.setting_name, "a password"
        )
        text = f"{name} needs {what} to connect."
        if req.flags & GetFlags.REQUEST_NEW:
            text = f"{name} rejected the saved secret. Enter {what} again."

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("net-prompt")
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Label(label=glyph)
        icon.add_css_class("net-row-icon")
        head.append(icon)
        t = Gtk.Label(label=title, xalign=0, hexpand=True)
        t.add_css_class("net-title")
        head.append(t)
        box.append(head)
        msg = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=44)
        msg.add_css_class("net-prompt-text")
        box.append(msg)

        self.entries: dict[str, Gtk.PasswordEntry] = {}
        for key, label_text in req.fields:
            ent = Gtk.PasswordEntry(show_peek_icon=True, hexpand=True)
            ent.set_property("placeholder-text", label_text)
            ent.add_css_class("net-entry")
            _ = ent.connect("activate", self._activated)
            box.append(ent)
            self.entries[key] = ent
        self.error = copyable(Gtk.Label(xalign=0, wrap=True, visible=False))
        self.error.add_css_class("net-form-error")
        box.append(self.error)

        buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4, halign=Gtk.Align.END
        )
        cancel = Gtk.Button(label="Cancel")
        cancel.add_css_class("net-btn")
        _ = cancel.connect("clicked", self._cancel_clicked)
        buttons.append(cancel)
        ok = Gtk.Button(label="Connect")
        ok.add_css_class("net-btn-accent")
        _ = ok.connect("clicked", self._ok_clicked)
        buttons.append(ok)
        box.append(buttons)

        self.win, overlay = popup_window(app, self._dismiss, self._on_key)
        show_popup(self.win, overlay, box, MARGIN_TOP)
        _ = next(iter(self.entries.values())).grab_focus()

    def _dismiss(self) -> None:
        self.app.answer(self, None)

    def _activated(self, _ent: Gtk.PasswordEntry) -> None:
        self._submit()

    def _cancel_clicked(self, _btn: Gtk.Button) -> None:
        self._dismiss()

    def _ok_clicked(self, _btn: Gtk.Button) -> None:
        self._submit()

    def _on_key(
        self,
        _ctrl: Gtk.EventControllerKey,
        keyval: int,
        _code: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._dismiss()
            return True
        return False

    def _submit(self) -> None:
        values = {k: e.get_text() for k, e in self.entries.items()}
        if not all(values.values()):
            self._show_error("Enter a value")
            return
        s_wsec = nullable(self.req.connection.get_setting_wireless_security())
        psk = values.get(NM.SETTING_WIRELESS_SECURITY_PSK)
        if (
            psk is not None
            and s_wsec
            and s_wsec.get_key_mgmt() == "wpa-psk"
            and not NM.utils_wpa_psk_valid(psk)
        ):
            self._show_error("WPA passwords are 8-63 characters (or 64 hex digits)")
            return
        self.app.answer(self, values)

    def _show_error(self, text: str) -> None:
        self.error.set_text(text)
        self.error.set_visible(True)

    def close(self) -> None:
        self.win.destroy()


class NetworkAgent(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.client: NM.Client | None = None
        self.agent: PromptAgent | None = None
        self.notifier: Notifier | None = None
        self.proxy_monitor: ProxyMonitor | None = None
        self._queue: list[Request] = []
        self._prompt: Prompt | None = None

    @override
    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.hold()  # no window between prompts
        install_css(render_css(BASE_CSS) + load_css(STYLE_CSS))
        _ = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._quit)
        _ = GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._quit)
        NM.Client.new_async(None, self._on_client)
        self.agent = PromptAgent(self)
        self.agent.init_async(GLib.PRIORITY_DEFAULT, None, self._on_agent)
        self.proxy_monitor = ProxyMonitor()

    @override
    def do_activate(self) -> None:
        pass  # a second launch just finds this instance running

    def _quit(self) -> bool:
        self.quit()
        return GLib.SOURCE_REMOVE

    def _on_client(self, _src: GObject.Object | None, res: Gio.AsyncResult) -> None:
        try:
            self.client = NM.Client.new_finish(res)
        except GLib.Error as e:
            print(
                f"network-agent: NetworkManager unavailable: {e.message}",
                file=sys.stderr,
            )
            return
        self.notifier = Notifier(self.client)

    @staticmethod
    def _on_agent(agent: Gio.AsyncInitable, res: Gio.AsyncResult) -> None:
        try:
            _ = agent.init_finish(res)
        except GLib.Error as e:
            # auto_register retries whenever NetworkManager (re)appears
            print(
                f"network-agent: secret agent not registered yet: {e.message}",
                file=sys.stderr,
            )

    # --- prompt queue: one prompt at a time ---

    def enqueue(self, req: Request) -> None:
        self._queue.append(req)
        self._next()

    def _next(self) -> None:
        if self._prompt is None and self._queue:
            self._prompt = Prompt(self, self._queue.pop(0))

    def answer(self, prompt: Prompt, values: dict[str, str] | None) -> None:
        if prompt is not self._prompt:
            return
        self._prompt = None
        prompt.close()
        if values is None:
            prompt.req.fail(NM.SecretAgentError.USERCANCELED, "canceled by the user")
        else:
            prompt.req.reply(values)
        self._next()

    def cancel(self, path: str, setting_name: str) -> None:
        """NM withdrew a request: its callback must still get AGENT_CANCELED."""
        if self._prompt and self._prompt.req.matches(path, setting_name):
            prompt, self._prompt = self._prompt, None
            prompt.close()
            prompt.req.fail(
                NM.SecretAgentError.AGENTCANCELED, "canceled by NetworkManager"
            )
            self._next()
            return
        for req in [r for r in self._queue if r.matches(path, setting_name)]:
            self._queue.remove(req)
            req.fail(NM.SecretAgentError.AGENTCANCELED, "canceled by NetworkManager")

    @override
    def do_shutdown(self) -> None:
        if self._prompt:
            self._prompt.req.fail(NM.SecretAgentError.AGENTCANCELED, "agent exiting")
            self._prompt.close()
            self._prompt = None
        for req in self._queue:
            req.fail(NM.SecretAgentError.AGENTCANCELED, "agent exiting")
        self._queue.clear()
        Gtk.Application.do_shutdown(self)


def main() -> int:
    return NetworkAgent().run()
