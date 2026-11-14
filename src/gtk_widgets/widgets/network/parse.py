"""Proxy rules' state file (~/.config/gtk-widgets/network-proxy.json), a
pasted proxy line and sway's tree (the PIDs that own a window): their
models and parsers.

The dataclasses keep the file's key order, so a saved state reads as before.
A field an older file lacks takes its default.
"""

import ipaddress
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from gtk_widgets.lib.parse import (
    ParseError,
    as_array,
    as_bool,
    as_int,
    as_str,
    as_str_or_none,
    is_object,
)

DIRECT = "direct"  # the exit that is no proxy


@dataclass(slots=True)
class Proxy:
    host: str
    port: int
    username: str
    password: str
    id: str = ""
    block_quic: bool = False


@dataclass(slots=True)
class Rule:
    app: str  # basename of the executable (sing-box's process_name)
    exit: str  # a proxy's id or DIRECT


@dataclass(slots=True)
class Check:
    """socks5.check()'s result: udp is None when the UDP check did not run."""

    ok: bool = False
    error: str | None = None
    latency_ms: int | None = None
    ip: str | None = None
    country: str | None = None
    udp: bool | None = None
    udp_ms: int | None = None
    udp_error: str | None = None
    checked: int = 0  # epoch seconds


@dataclass(slots=True)
class State:
    proxies: list[Proxy] = field(default_factory=list[Proxy])
    rules: list[Rule] = field(default_factory=list[Rule])
    default: str = DIRECT
    kill_switch: bool = False
    checks: dict[str, Check] = field(default_factory=dict[str, Check])
    applied: str | None = None  # digest of the request the helper last applied


def _optional[T](
    read: Callable[[object, str], T | ParseError], value: object, path: str
) -> T | ParseError | None:
    return None if value is None else read(value, path)


def _first_error(fields: tuple[object, ...], path: str) -> ParseError:
    return next(
        (f for f in fields if isinstance(f, ParseError)),
        ParseError(f"{path}: unexpected value"),
    )


def parse_state(raw: str) -> State | ParseError:
    try:
        data: object = json.loads(raw)
    except ValueError as e:
        return ParseError(f"not JSON: {e}")
    if not is_object(data):
        return ParseError("not an object")
    proxies = _list(data.get("proxies"), ".proxies", _proxy)
    rules = _list(data.get("rules"), ".rules", _rule)
    checks = _checks(data.get("checks"))
    d = State()
    match (
        proxies,
        rules,
        as_str(data.get("default", d.default), ".default"),
        as_bool(data.get("kill_switch", d.kill_switch), ".kill_switch"),
        checks,
        as_str_or_none(data.get("applied"), ".applied"),
    ):
        case (
            list() as p,
            list() as r,
            str() as default,
            bool() as kill_switch,
            dict() as c,
            (str() | None) as applied,
        ):
            return State(p, r, default, kill_switch, c, applied)
        case fields:
            return _first_error(fields, "")


def _list[T](
    value: object, path: str, read: Callable[[object, str], T | ParseError]
) -> list[T] | ParseError:
    items = as_array(value, path)
    if isinstance(items, ParseError):
        return items
    found: list[T] = []
    for i, item in enumerate(items):
        parsed = read(item, f"{path}[{i}]")
        if isinstance(parsed, ParseError):
            return parsed
        found.append(parsed)
    return found


def _proxy(value: object, path: str) -> Proxy | ParseError:
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    match (
        as_str(value.get("host"), f"{path}.host"),
        as_int(value.get("port"), f"{path}.port"),
        as_str(value.get("username"), f"{path}.username"),
        as_str(value.get("password"), f"{path}.password"),
        as_str(value.get("id"), f"{path}.id"),
        as_bool(value.get("block_quic", False), f"{path}.block_quic"),
    ):
        case (
            str() as host,
            int() as port,
            str() as username,
            str() as password,
            str() as pid,
            bool() as block_quic,
        ):
            return Proxy(host, port, username, password, pid, block_quic)
        case fields:
            return _first_error(fields, path)


def _rule(value: object, path: str) -> Rule | ParseError:
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    match (
        as_str(value.get("app"), f"{path}.app"),
        as_str(value.get("exit"), f"{path}.exit"),
    ):
        case str() as app, str() as exit_:
            return Rule(app, exit_)
        case fields:
            return _first_error(fields, path)


def _checks(value: object) -> dict[str, Check] | ParseError:
    if value is None:
        return {}
    if not is_object(value):
        return ParseError(".checks: not an object")
    found: dict[str, Check] = {}
    for pid, item in value.items():
        if item is None:  # a check that never finished
            continue
        check = _check(item, f".checks.{pid}")
        if isinstance(check, ParseError):
            return check
        found[pid] = check
    return found


def _check(value: object, path: str) -> Check | ParseError:
    if not is_object(value):
        return ParseError(f"{path}: not an object")
    d = Check()
    match (
        as_bool(value.get("ok", d.ok), f"{path}.ok"),
        as_str_or_none(value.get("error"), f"{path}.error"),
        _optional(as_int, value.get("latency_ms"), f"{path}.latency_ms"),
        as_str_or_none(value.get("ip"), f"{path}.ip"),
        as_str_or_none(value.get("country"), f"{path}.country"),
        _optional(as_bool, value.get("udp"), f"{path}.udp"),
        _optional(as_int, value.get("udp_ms"), f"{path}.udp_ms"),
        as_str_or_none(value.get("udp_error"), f"{path}.udp_error"),
        as_int(value.get("checked", d.checked), f"{path}.checked"),
    ):
        case (
            bool() as ok,
            (str() | None) as error,
            (int() | None) as latency_ms,
            (str() | None) as ip,
            (str() | None) as country,
            (bool() | None) as udp,
            (int() | None) as udp_ms,
            (str() | None) as udp_error,
            int() as checked,
        ):
            return Check(
                ok, error, latency_ms, ip, country, udp, udp_ms, udp_error, checked
            )
        case fields:
            return _first_error(fields, path)


def parse_window_pids(raw: bytes) -> set[int] | ParseError:
    """The PIDs of the views in a GET_TREE reply (a node's pid, if any)."""
    try:
        data: object = json.loads(raw)
    except ValueError as e:
        return ParseError(f"not JSON: {e}")
    pids: set[int] = set()
    stack: list[tuple[object, str]] = [(data, "tree")]
    while stack:
        node, path = stack.pop()
        if not is_object(node):
            return ParseError(f"{path}: not an object")
        pid = node.get("pid")
        if type(pid) is int and pid:
            pids.add(pid)
        for key in ("nodes", "floating_nodes"):
            children = as_array(node.get(key), f"{path}.{key}")
            if isinstance(children, ParseError):
                return children
            stack.extend((c, f"{path}.{key}[{i}]") for i, c in enumerate(children))
    return pids


# A host name: dot-separated labels of letters, digits and inner hyphens
_HOST_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SCHEMES = ("socks5h://", "socks5://", "socks://")
_MAX_LOGIN = 255  # bytes of a SOCKS5 username or password
_MAX_PORT = 65535
_PROVIDER_FIELDS = 4  # host:port:user:pass
_PLAIN_FIELDS = 2  # host:port


def _host_port(host: str, port: str) -> tuple[str, int] | ParseError:
    host = host.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        host = str(ipaddress.ip_address(host))
    except ValueError:
        if not _HOST_RE.match(host) or host.rstrip(".").split(".")[-1].isdigit():
            return ParseError(f"{host!r} is not a host name or IP address")
    if not port.isdigit() or not 1 <= int(port) <= _MAX_PORT:
        return ParseError(f"{port!r} is not a port")
    return host, int(port)


def _split_line(line: str) -> tuple[str, str, str, str] | ParseError:
    """(host, port, user, password) of a pasted line, unchecked."""
    user = password = ""
    if "@" in line:
        cred, _, addr = line.rpartition("@")
        user, sep, password = cred.partition(":")
        if not sep:
            return ParseError("expected user:pass@host:port")
        host, sep, port = addr.rpartition(":")
        if not sep:
            return ParseError("missing port")
    elif line.startswith("["):
        host, sep, rest = line.partition("]:")
        if not sep:
            return ParseError("expected [IPv6]:port")
        host += "]"
        port, _, cred = rest.partition(":")
        if cred:
            user, sep, password = cred.partition(":")
            if not sep:
                return ParseError("expected [IPv6]:port:user:pass")
    else:
        parts = line.split(":", 3)  # the password may contain ':'
        if len(parts) == _PLAIN_FIELDS:
            host, port = parts
        elif len(parts) == _PROVIDER_FIELDS:
            host, port, user, password = parts
        else:
            return ParseError("expected host:port:user:pass")
    return host, port, user, password


def parse_proxy_line(line: str) -> Proxy | ParseError:
    """One pasted proxy: host:port:user:pass (the provider format), host:port,
    user:pass@host:port or socks5://user:pass@host:port. IPv6 in [brackets].
    The Proxy has no id yet."""
    line = line.strip()
    for prefix in _SCHEMES:
        if line.lower().startswith(prefix):
            line = line[len(prefix) :]
            break
    split = _split_line(line)
    if isinstance(split, ParseError):
        return split
    host, port, user, password = split
    address = _host_port(host, port)
    if isinstance(address, ParseError):
        return address
    if bool(user) != bool(password):
        return ParseError("give both a username and a password, or neither")
    for what, value in (("username", user), ("password", password)):
        if len(value.encode()) > _MAX_LOGIN:
            return ParseError(f"{what} longer than 255 bytes")
        if _CONTROL_RE.search(value):
            return ParseError(f"control characters in the {what}")
    return Proxy(address[0], address[1], user, password)
