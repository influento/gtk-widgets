"""Proxy rules (per-app routing through sing-box): user-side state, the paste
parser, the root helper call and a watch on gtk-widgets-proxy.service.

Shared by the popup (main.py, proxypage.py), network-agent and network-status.

State lives in ~/.config/gtk-widgets/network-proxy.json (0600): the proxies
with their passwords (the popup's checks need them), the app rules, the default
exit, the kill switch, the last check results and the digest of the request the
helper last applied. The helper gets only the request (never a config or a
path) on stdin and writes the root-only sing-box config itself.
"""

import hashlib, ipaddress, json, os, re, subprocess, tempfile

from gi.repository import Gio, GLib

STATE_PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                          "gtk-widgets", "network-proxy.json")
HELPER = "/usr/lib/gtk-widgets/proxy-helper"
UNIT = "gtk-widgets-proxy.service"
DIRECT = "direct"
MAX_PROXIES = 32

SD_BUS, SD_PATH = "org.freedesktop.systemd1", "/org/freedesktop/systemd1"
SD_MANAGER, SD_UNIT = "org.freedesktop.systemd1.Manager", "org.freedesktop.systemd1.Unit"


# --- state ---

def empty_state():
    return {"proxies": [], "rules": [], "default": DIRECT, "kill_switch": False,
            "checks": {}, "applied": None}


def load_state(path=None):
    try:
        with open(path or STATE_PATH) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return empty_state()
    state = empty_state()
    if isinstance(data, dict):
        state.update({k: data[k] for k in state if k in data})
    return state


def save_state(state, path=None):
    """Atomic write, 0600 in a 0700 directory: the file holds proxy passwords."""
    path = path or STATE_PATH
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".network-proxy.", dir=folder)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def proxy_by_id(state, pid):
    return next((p for p in state["proxies"] if p["id"] == pid), None)


def next_id(state):
    used = {p["id"] for p in state["proxies"]}
    return next(f"p{i}" for i in range(1, 100) if f"p{i}" not in used)


def exit_name(state, exit_):
    return "direct" if exit_ == DIRECT else exit_


def remove_proxy(state, pid):
    """Drop a proxy; its apps and the default fall back to direct."""
    state["proxies"] = [p for p in state["proxies"] if p["id"] != pid]
    state["rules"] = [r for r in state["rules"] if r["exit"] != pid]
    if state["default"] == pid:
        state["default"] = DIRECT
    state["checks"].pop(pid, None)


def request(state):
    """What the helper gets: only the fields it validates, no names or checks."""
    return {
        "proxies": [{k: p[k] for k in ("id", "host", "port", "username", "password", "block_quic")}
                    for p in state["proxies"]],
        "rules": [{"app": r["app"], "exit": r["exit"]} for r in state["rules"]],
        "default": state["default"],
        "kill_switch": bool(state["kill_switch"]),
    }


def digest(req):
    return hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()


def usable_problem(state):
    """Why Proxy rules cannot be turned on, or None."""
    if not state["proxies"]:
        return "Add a proxy first"
    if state["default"] == DIRECT and not any(r["exit"] != DIRECT for r in state["rules"]):
        return "Route an app through a proxy, or pick a proxy for everything else"
    return None


def summary(state):
    """'3 apps via 2 proxies', plus where everything else goes."""
    proxied = [r for r in state["rules"] if r["exit"] != DIRECT]
    used = {r["exit"] for r in proxied}
    apps = len(proxied)
    text = f"{apps} app{'s' * (apps != 1)} via {len(used)} prox{'ies' if len(used) != 1 else 'y'}" \
        if apps else "no app rules"
    if state["default"] != DIRECT:
        text += f", everything else via {exit_name(state, state['default'])}"
    return text


def rule_lines(state):
    """Tooltip/detail lines: 'firefox → p1 (NL)'."""
    lines = []
    for r in state["rules"]:
        lines.append(f"{r['app']} → {exit_label(state, r['exit'])}")
    lines.append(f"everything else → {exit_label(state, state['default'])}")
    return lines


def exit_label(state, exit_):
    name = exit_name(state, exit_)
    country = (state["checks"].get(exit_) or {}).get("country")
    return f"{name} ({country})" if country else name


# --- pasted proxies ---

HOST_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$")


def _host_port(host, port):
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        host = str(ipaddress.ip_address(host))
    except ValueError:
        if not HOST_RE.match(host) or host.rstrip(".").split(".")[-1].isdigit():
            raise ValueError(f"{host!r} is not a host name or IP address")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError(f"{port!r} is not a port")
    return host, int(port)


def parse_line(line):
    """One proxy: host:port:user:pass (the provider format), host:port,
    user:pass@host:port or socks5://user:pass@host:port. IPv6 in [brackets]."""
    line = line.strip()
    for prefix in ("socks5h://", "socks5://", "socks://"):
        if line.lower().startswith(prefix):
            line = line[len(prefix):]
            break
    user = password = ""
    if "@" in line:
        cred, _, addr = line.rpartition("@")
        user, sep, password = cred.partition(":")
        if not sep:
            raise ValueError("expected user:pass@host:port")
        host, sep, port = addr.rpartition(":")
        if not sep:
            raise ValueError("missing port")
    elif line.startswith("["):
        host, sep, rest = line.partition("]:")
        if not sep:
            raise ValueError("expected [IPv6]:port")
        host += "]"
        port, _, cred = rest.partition(":")
        if cred:
            user, sep, password = cred.partition(":")
            if not sep:
                raise ValueError("expected [IPv6]:port:user:pass")
    else:
        parts = line.split(":", 3)  # the password may contain ':'
        if len(parts) == 2:
            host, port = parts
        elif len(parts) == 4:
            host, port, user, password = parts
        else:
            raise ValueError("expected host:port:user:pass")
    host, port = _host_port(host, port)
    if bool(user) != bool(password):
        raise ValueError("give both a username and a password, or neither")
    for what, value in (("username", user), ("password", password)):
        if len(value.encode()) > 255:
            raise ValueError(f"{what} longer than 255 bytes")
        if re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError(f"control characters in the {what}")
    return {"host": host, "port": port, "username": user, "password": password}


def import_lines(state, text):
    """Add pasted proxies. Returns (added, [(line number, error)]); lines that
    repeat an existing host:port:user replace its password."""
    added, errors = 0, []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            p = parse_line(line)
        except ValueError as e:
            errors.append((n, str(e)))
            continue
        same = next((q for q in state["proxies"] if (q["host"], q["port"], q["username"])
                     == (p["host"], p["port"], p["username"])), None)
        if same:
            same["password"] = p["password"]
            continue
        if len(state["proxies"]) >= MAX_PROXIES:
            errors.append((n, f"at most {MAX_PROXIES} proxies"))
            continue
        pid = next_id(state)
        state["proxies"].append(dict(p, id=pid, block_quic=False))
        added += 1
    return added, errors


# --- running processes (the app picker) ---

def running_apps(proc="/proc", uid=None):
    """{executable name: path} of this user's processes: the names sing-box's
    process_name matches (basename of /proc/<pid>/exe, not comm)."""
    uid = os.getuid() if uid is None else uid
    apps = {}
    try:
        pids = [d for d in os.listdir(proc) if d.isdigit()]
    except OSError:
        return apps
    for pid in pids:
        try:
            if os.stat(os.path.join(proc, pid)).st_uid != uid:
                continue
            path = os.readlink(os.path.join(proc, pid, "exe"))
        except OSError:
            continue  # kernel threads, exited or foreign processes
        path = path.removesuffix(" (deleted)")
        apps.setdefault(os.path.basename(path), path)
    return apps


def window_pids():
    """PIDs owning a Sway window, to list apps with windows first."""
    try:
        out = subprocess.run(["swaymsg", "-t", "get_tree", "-r"], capture_output=True,
                             timeout=2, check=True).stdout
        stack = [json.loads(out)]
    except (OSError, subprocess.SubprocessError, ValueError):
        return set()
    pids = set()
    while stack:
        node = stack.pop()
        if node.get("pid"):
            pids.add(node["pid"])
        stack.extend(node.get("nodes", []) + node.get("floating_nodes", []))
    return pids


def window_apps(proc="/proc"):
    names = set()
    for pid in window_pids():
        try:
            names.add(os.path.basename(os.readlink(f"{proc}/{pid}/exe")).removesuffix(" (deleted)"))
        except OSError:
            pass
    return names


# --- helper ---

def run_helper(args, stdin_text, on_done):
    """pkexec the root helper asynchronously; on_done(error or None)."""
    try:
        proc = Gio.Subprocess.new(["pkexec", HELPER] + args,
                                  Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDOUT_PIPE
                                  | Gio.SubprocessFlags.STDERR_PIPE)
    except GLib.Error as e:
        on_done(f"cannot run pkexec: {e.message}")
        return

    def done(p, res):
        try:
            _ok, _out, err = p.communicate_utf8_finish(res)
        except GLib.Error as e:
            on_done(e.message)
            return
        status = p.get_exit_status()
        if status == 0:
            on_done(None)
        elif status == 126:
            on_done("authorisation was dismissed")
        elif status == 127 and not os.path.exists(HELPER):
            on_done("the proxy helper is not installed: run install.sh")
        else:
            lines = (err or "").strip().splitlines()
            msg = lines[-1] if lines else f"helper failed ({status})"
            on_done(msg.removeprefix("proxy-helper: "))
    proc.communicate_utf8_async(stdin_text, None, done)


def apply(state, on_done):
    """Write the config and (re)start sing-box; on success record the digest."""
    req = request(state)

    def done(err):
        if err is None:
            state["applied"] = digest(req)
            save_state(state)
        on_done(err)
    run_helper(["apply"], json.dumps(req), done)


def stop(on_done):
    run_helper(["stop"], "", on_done)


def pending_changes(state):
    return state.get("applied") != digest(request(state))


# --- service ---

class ServiceState:
    """One synchronous read of the unit (for --once callers)."""

    def __init__(self):
        self.installed = self.state = self.sub_state = None
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            path = bus.call_sync(SD_BUS, SD_PATH, SD_MANAGER, "LoadUnit",
                                 GLib.Variant("(s)", (UNIT,)), GLib.VariantType("(o)"),
                                 Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            props = bus.call_sync(SD_BUS, path, "org.freedesktop.DBus.Properties", "GetAll",
                                  GLib.Variant("(s)", (SD_UNIT,)), GLib.VariantType("(a{sv})"),
                                  Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        except GLib.Error:
            return
        self.installed = props.get("LoadState") == "loaded"
        self.state, self.sub_state = props.get("ActiveState"), props.get("SubState")

    active = property(lambda s: s.state in ("active", "reloading"))
    starting = property(lambda s: s.state == "activating")
    crashed = property(lambda s: s.state == "failed" or s.sub_state == "auto-restart")


class ServiceWatch:
    """Follows gtk-widgets-proxy.service over the system bus.
    on_change(watch) runs on every state change; read .installed, .state,
    .sub_state (systemd's names)."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.installed = self.state = self.sub_state = None
        self.proxy = None
        Gio.bus_get(Gio.BusType.SYSTEM, None, self._on_bus)

    @property
    def active(self):
        return self.state in ("active", "reloading")

    @property
    def starting(self):
        return self.state == "activating"

    @property
    def crashed(self):
        """Stopped by a failure, not by a stop request (systemd may restart it)."""
        return self.state == "failed" or self.sub_state == "auto-restart"

    def _on_bus(self, _src, res):
        try:
            bus = Gio.bus_get_finish(res)
        except GLib.Error:
            return
        # Subscribe: systemd only broadcasts unit property changes while
        # someone is subscribed (unprivileged callers may subscribe)
        bus.call(SD_BUS, SD_PATH, SD_MANAGER, "Subscribe", None, None,
                 Gio.DBusCallFlags.NONE, -1, None, None)

        def loaded(conn, res2):
            try:
                path = conn.call_finish(res2).unpack()[0]
            except GLib.Error:
                return
            Gio.DBusProxy.new(conn, Gio.DBusProxyFlags.NONE, None, SD_BUS, path, SD_UNIT,
                              None, self._on_proxy)
        bus.call(SD_BUS, SD_PATH, SD_MANAGER, "LoadUnit", GLib.Variant("(s)", (UNIT,)),
                 GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, -1, None, loaded)

    def _on_proxy(self, _src, res):
        try:
            self.proxy = Gio.DBusProxy.new_finish(res)
        except GLib.Error:
            return
        self.proxy.connect("g-properties-changed", lambda *_: self._read())
        self._read()

    def _read(self):
        def prop(name):
            v = self.proxy.get_cached_property(name)
            return v.unpack() if v is not None else None
        before = (self.installed, self.state, self.sub_state)
        self.installed = prop("LoadState") == "loaded"
        self.state, self.sub_state = prop("ActiveState"), prop("SubState")
        if (self.installed, self.state, self.sub_state) != before:
            self.on_change(self)
