"""Proxy rules (per-app routing through sing-box): user-side state, the paste
parser, the root helper call and a watch on gtk-widgets-proxy.service.

Shared by the popup (main.py, proxypage.py), network-agent and network-status.

State lives in ~/.config/gtk-widgets/network-proxy.json (0600): the proxies
with their passwords (the popup's checks need them), the app rules, the default
exit, the kill switch, the last check results and the digest of the request the
helper last applied. The helper gets only the request (never a config or a
path) on stdin and writes the root-only sing-box config itself.
"""

import contextlib
import dataclasses
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from gi.repository import Gio, GLib, GObject

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.network.parse import (
    DIRECT,
    Proxy,
    State,
    parse_proxy_line,
    parse_state,
    parse_window_pids,
)


def _config_home() -> Path:
    if env := os.environ.get("XDG_CONFIG_HOME"):
        return Path(env)
    try:
        return Path("~/.config").expanduser()
    except RuntimeError:  # no home: os.path.expanduser's answer
        return Path("~/.config")


STATE_PATH = _config_home() / "gtk-widgets" / "network-proxy.json"
HELPER = "/usr/lib/gtk-widgets/proxy-helper"
UNIT = "gtk-widgets-proxy.service"
MAX_PROXIES = 32
MAX_ID = 100  # proxy ids are p1 .. p99; MAX_PROXIES keeps them from running out

SD_BUS, SD_PATH = "org.freedesktop.systemd1", "/org/freedesktop/systemd1"
SD_MANAGER, SD_UNIT = (
    "org.freedesktop.systemd1.Manager",
    "org.freedesktop.systemd1.Unit",
)
DBUS_TIMEOUT_MS = 2000
SWAYMSG_TIMEOUT_S = 2
EXIT_DISMISSED = 126  # pkexec: the authorisation dialog was dismissed
EXIT_NOT_FOUND = 127  # pkexec: the helper is missing (or refused)

__all__ = ["DIRECT", "STATE_PATH", "State"]


# --- state ---


def load_state(path: Path | None = None) -> State:
    """The saved state; a missing or unreadable file is an empty one."""
    try:
        raw = (path or STATE_PATH).read_text()
    except OSError, ValueError:
        return State()
    state = parse_state(raw)
    return State() if isinstance(state, ParseError) else state


def save_state(state: State, path: Path | None = None) -> None:
    """Atomic write, 0600 in a 0700 directory: the file holds proxy passwords."""
    path = path or STATE_PATH
    folder = path.parent
    folder.mkdir(mode=0o700, exist_ok=True, parents=True)
    fd, tmp = tempfile.mkstemp(prefix=".network-proxy.", dir=folder)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(dataclasses.asdict(state), f, indent=2, ensure_ascii=False)
            _ = f.write("\n")
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def proxy_by_id(state: State, pid: str) -> Proxy | None:
    return next((p for p in state.proxies if p.id == pid), None)


def next_id(state: State) -> str:
    used = {p.id for p in state.proxies}
    return next(f"p{i}" for i in range(1, MAX_ID) if f"p{i}" not in used)


def exit_name(_state: State, exit_: str) -> str:
    return "direct" if exit_ == DIRECT else exit_


def remove_proxy(state: State, pid: str) -> None:
    """Drop a proxy; its apps and the default fall back to direct."""
    state.proxies = [p for p in state.proxies if p.id != pid]
    state.rules = [r for r in state.rules if r.exit != pid]
    if state.default == pid:
        state.default = DIRECT
    _ = state.checks.pop(pid, None)


class HelperProxy(TypedDict):
    id: str
    host: str
    port: int
    username: str
    password: str
    block_quic: bool


class HelperRule(TypedDict):
    app: str
    exit: str


class HelperRequest(TypedDict):
    """What the helper gets on stdin (polkit/proxy-helper validates it)."""

    proxies: list[HelperProxy]
    rules: list[HelperRule]
    default: str
    kill_switch: bool


def request(state: State) -> HelperRequest:
    """What the helper gets: only the fields it validates, no names or checks."""
    return {
        "proxies": [
            {
                "id": p.id,
                "host": p.host,
                "port": p.port,
                "username": p.username,
                "password": p.password,
                "block_quic": p.block_quic,
            }
            for p in state.proxies
        ],
        "rules": [{"app": r.app, "exit": r.exit} for r in state.rules],
        "default": state.default,
        "kill_switch": state.kill_switch,
    }


def digest(req: HelperRequest) -> str:
    return hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()


def usable_problem(state: State) -> str | None:
    """Why Proxy rules cannot be turned on, or None."""
    if not state.proxies:
        return "Add a proxy first"
    if state.default == DIRECT and not any(r.exit != DIRECT for r in state.rules):
        return "Route an app through a proxy, or pick a proxy for everything else"
    return None


def summary(state: State) -> str:
    """'3 apps via 2 proxies', plus where everything else goes."""
    proxied = [r for r in state.rules if r.exit != DIRECT]
    used = {r.exit for r in proxied}
    apps = len(proxied)
    text = (
        f"{apps} app{'s' * (apps != 1)} via {len(used)} prox{'ies' if len(used) != 1 else 'y'}"
        if apps
        else "no app rules"
    )
    if state.default != DIRECT:
        text += f", everything else via {exit_name(state, state.default)}"
    return text


def exit_label(state: State, exit_: str) -> str:
    name = exit_name(state, exit_)
    check = state.checks.get(exit_)
    country = check.country if check else None
    return f"{name} ({country})" if country else name


# --- pasted proxies ---


def import_lines(state: State, text: str) -> tuple[int, list[tuple[int, str]]]:
    """Add pasted proxies. Returns (added, [(line number, error)]); lines that
    repeat an existing host:port:user replace its password."""
    added = 0
    errors: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        p = parse_proxy_line(line)
        if isinstance(p, ParseError):
            errors.append((n, str(p)))
            continue
        same = next(
            (
                q
                for q in state.proxies
                if (q.host, q.port, q.username) == (p.host, p.port, p.username)
            ),
            None,
        )
        if same:
            same.password = p.password
            continue
        if len(state.proxies) >= MAX_PROXIES:
            errors.append((n, f"at most {MAX_PROXIES} proxies"))
            continue
        p.id = next_id(state)
        state.proxies.append(p)
        added += 1
    return added, errors


# --- running processes (the app picker) ---

_DELETED = " (deleted)"  # /proc/<pid>/exe of a replaced executable


def running_apps(proc: str = "/proc", uid: int | None = None) -> dict[str, str]:
    """{executable name: path} of this user's processes: the names sing-box's
    process_name matches (basename of /proc/<pid>/exe, not comm)."""
    uid = os.getuid() if uid is None else uid
    apps: dict[str, str] = {}
    try:
        pids = [d for d in Path(proc).iterdir() if d.name.isdigit()]
    except OSError:
        return apps
    for pid in pids:
        try:
            if pid.stat().st_uid != uid:
                continue
            path = str((pid / "exe").readlink())
        except OSError:
            continue  # kernel threads, exited or foreign processes
        path = path.removesuffix(_DELETED)
        _ = apps.setdefault(Path(path).name, path)
    return apps


def window_pids() -> set[int]:
    """PIDs owning a Sway window, to list apps with windows first."""
    try:
        out = subprocess.run(
            ["swaymsg", "-t", "get_tree", "-r"],
            capture_output=True,
            timeout=SWAYMSG_TIMEOUT_S,
            check=True,
        ).stdout
    except OSError, subprocess.SubprocessError:
        return set()
    pids = parse_window_pids(out)
    return set() if isinstance(pids, ParseError) else pids


def window_apps(proc: str = "/proc") -> set[str]:
    names: set[str] = set()
    for pid in window_pids():
        with contextlib.suppress(OSError):
            exe = str(Path(f"{proc}/{pid}/exe").readlink())
            names.add(Path(exe).name.removesuffix(_DELETED))
    return names


# --- helper ---


def run_helper(
    args: list[str], stdin_text: str, on_done: Callable[[str | None], None]
) -> None:
    """pkexec the root helper asynchronously; on_done(error or None)."""
    try:
        proc = Gio.Subprocess.new(
            ["pkexec", HELPER, *args],
            Gio.SubprocessFlags.STDIN_PIPE
            | Gio.SubprocessFlags.STDOUT_PIPE
            | Gio.SubprocessFlags.STDERR_PIPE,
        )
    except GLib.Error as e:
        on_done(f"cannot run pkexec: {e.message}")
        return

    def done(p: Gio.Subprocess, res: Gio.AsyncResult) -> None:
        try:
            _ok, _out, err = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            on_done(e.message)
            return
        status = p.get_exit_status()
        if status == 0:
            on_done(None)
        elif status == EXIT_DISMISSED:
            on_done("authorisation was dismissed")
        elif status == EXIT_NOT_FOUND and not Path(HELPER).exists():
            on_done("the proxy helper is not installed: run install.sh")
        else:
            lines = (err or "").strip().splitlines()
            msg = lines[-1] if lines else f"helper failed ({status})"
            on_done(msg.removeprefix("proxy-helper: "))

    proc.communicate_utf8_async(stdin_text, None, done)


def apply(state: State, on_done: Callable[[str | None], None]) -> None:
    """Write the config and (re)start sing-box; on success record the digest."""
    req = request(state)

    def done(err: str | None) -> None:
        if err is None:
            state.applied = digest(req)
            save_state(state)
        on_done(err)

    run_helper(["apply"], json.dumps(req), done)


def stop(on_done: Callable[[str | None], None]) -> None:
    run_helper(["stop"], "", on_done)


def pending_changes(state: State) -> bool:
    return state.applied != digest(request(state))


# --- service ---


class _Unit:
    """systemd's view of the unit: LoadState, ActiveState, SubState."""

    def __init__(self) -> None:
        self.installed: bool | None = None
        self.state: str | None = None
        self.sub_state: str | None = None

    @property
    def active(self) -> bool:
        return self.state in {"active", "reloading"}

    @property
    def starting(self) -> bool:
        return self.state == "activating"

    @property
    def crashed(self) -> bool:
        """Stopped by a failure, not by a stop request (systemd may restart it)."""
        return self.state == "failed" or self.sub_state == "auto-restart"

    def _set(self, load: str | None, active: str | None, sub: str | None) -> bool:
        """Take the three properties; True when anything changed."""
        before = (self.installed, self.state, self.sub_state)
        self.installed = load == "loaded"
        self.state, self.sub_state = active, sub
        return (self.installed, self.state, self.sub_state) != before


class ServiceState(_Unit):
    """One synchronous read of the unit (for --once callers)."""

    def __init__(self) -> None:
        super().__init__()
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            path = _first_string(
                bus.call_sync(
                    SD_BUS,
                    SD_PATH,
                    SD_MANAGER,
                    "LoadUnit",
                    GLib.Variant("(s)", (UNIT,)),
                    GLib.VariantType("(o)"),
                    Gio.DBusCallFlags.NONE,
                    DBUS_TIMEOUT_MS,
                    None,
                )
            )
            reply = bus.call_sync(
                SD_BUS,
                path,
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", (SD_UNIT,)),
                GLib.VariantType("(a{sv})"),
                Gio.DBusCallFlags.NONE,
                DBUS_TIMEOUT_MS,
                None,
            )
        except GLib.Error:
            return
        props = reply.get_child_value(0)

        def prop(name: str) -> str | None:
            return _string(props.lookup_value(name, None))

        _ = self._set(prop("LoadState"), prop("ActiveState"), prop("SubState"))


def _first_string(reply: GLib.Variant) -> str:
    """The string (or object path) a D-Bus reply tuple starts with, "" for
    another type."""
    return _string(reply.get_child_value(0)) or ""


class ServiceWatch(_Unit):
    """Follows gtk-widgets-proxy.service over the system bus.
    on_change(watch) runs on every state change; read .installed, .state,
    .sub_state (systemd's names)."""

    def __init__(self, on_change: Callable[[ServiceWatch], None]) -> None:
        super().__init__()
        self.on_change = on_change
        self.proxy: Gio.DBusProxy | None = None
        Gio.bus_get(Gio.BusType.SYSTEM, None, self._on_bus)

    def _on_bus(self, _src: GObject.Object | None, res: Gio.AsyncResult) -> None:
        try:
            bus = Gio.bus_get_finish(res)
        except GLib.Error:
            return
        # Subscribe: systemd only broadcasts unit property changes while
        # someone is subscribed (unprivileged callers may subscribe)
        bus.call(
            SD_BUS,
            SD_PATH,
            SD_MANAGER,
            "Subscribe",
            None,
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            None,
        )

        def loaded(conn: Gio.DBusConnection, res2: Gio.AsyncResult) -> None:
            try:
                path = _first_string(conn.call_finish(res2))
            except GLib.Error:
                return
            Gio.DBusProxy.new(
                conn,
                Gio.DBusProxyFlags.NONE,
                None,
                SD_BUS,
                path,
                SD_UNIT,
                None,
                self._on_proxy,
            )

        bus.call(
            SD_BUS,
            SD_PATH,
            SD_MANAGER,
            "LoadUnit",
            GLib.Variant("(s)", (UNIT,)),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            loaded,
        )

    def _on_proxy(self, _src: GObject.Object | None, res: Gio.AsyncResult) -> None:
        try:
            proxy = Gio.DBusProxy.new_finish(res)
        except GLib.Error:
            return
        self.proxy = proxy

        def changed(
            _proxy: Gio.DBusProxy, _changed: GLib.Variant, _gone: list[str]
        ) -> None:
            self._read(proxy)

        _ = proxy.connect("g-properties-changed", changed)
        self._read(proxy)

    def _read(self, proxy: Gio.DBusProxy) -> None:
        def prop(name: str) -> str | None:
            return _string(proxy.get_cached_property(name))

        if self._set(prop("LoadState"), prop("ActiveState"), prop("SubState")):
            self.on_change(self)


def _string(variant: GLib.Variant | None) -> str | None:
    """A D-Bus string or object path, or None when it is missing (lookup_value
    returns NULL then, though its stub says Variant) or of another type."""
    # unpack() and isinstance, not get_string(): a variant of another type
    # then reads as None instead of failing
    value: object = variant.unpack() if variant is not None else None
    return value if isinstance(value, str) else None
