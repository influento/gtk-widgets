"""Minimal SOCKS5 client (RFC 1928 + RFC 1929 auth) for checking proxies.

check() runs a TCP CONNECT to Cloudflare's trace page for latency, exit IP and
country, and a real UDP ASSOCIATE round trip (a DNS query through the relay):
providers often claim UDP support and then drop every datagram. Blocking
sockets with timeouts; callers run it off the GTK main thread.
"""

import ipaddress
import os
import socket
import ssl
import struct
import time

from gtk_widgets.widgets.network.parse import Check

TIMEOUT = 6.0
UDP_TRIES, UDP_WAIT = 3, 1.5
TRACE = ("1.1.1.1", 443, True)  # host, port, TLS: https://1.1.1.1/cdn-cgi/trace
DNS = ("1.1.1.1", 53)
TRACE_MAX = 65536  # bytes of the trace page read at most
RECV = 4096
MAX_FIELD = 255  # a SOCKS5 host name, username or password, in bytes
SOCKS_VERSION = 5
CMD_CONNECT, CMD_UDP_ASSOCIATE = 1, 3
ATYP_IPV4, ATYP_NAME, ATYP_IPV6 = 1, 3, 4
METHOD_NONE, METHOD_LOGIN, METHOD_REFUSED = 0, 2, 0xFF
DNS_ANSWER = 0x80  # the QR bit of a DNS header's flags
COUNTRY_LEN = 2
UNKNOWN_COUNTRY = "XX"
# UDP ASSOCIATE's client address when it isn't known yet: 0.0.0.0
ANY_ADDRESS = str(ipaddress.IPv4Address(0))

REPLIES = {
    1: "general proxy failure",
    2: "not allowed by the proxy's rules",
    3: "network unreachable",
    4: "host unreachable",
    5: "connection refused",
    6: "TTL expired",
    7: "command not supported",
    8: "address type not supported",
}


class Socks5Error(Exception):
    pass


def _recv_exact(sock: socket.socket | ssl.SSLSocket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise Socks5Error("the proxy closed the connection")
        data += chunk
    return data


def _port(data: bytes) -> int:
    port: int
    (port,) = struct.unpack("!H", data)
    return port


def _addr(host: str, port: int) -> bytes:
    """ATYP + address + port for a request or UDP header."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        name = host.encode("idna")
        if len(name) > MAX_FIELD:
            raise Socks5Error("host name too long") from None
        return bytes([ATYP_NAME, len(name)]) + name + struct.pack("!H", port)
    atyp = ATYP_IPV4 if isinstance(ip, ipaddress.IPv4Address) else ATYP_IPV6
    return bytes([atyp]) + ip.packed + struct.pack("!H", port)


def _read_addr(sock: socket.socket) -> tuple[str, int]:
    atyp = _recv_exact(sock, 1)[0]
    if atyp == ATYP_IPV4:
        host = str(ipaddress.IPv4Address(_recv_exact(sock, 4)))
    elif atyp == ATYP_IPV6:
        host = str(ipaddress.IPv6Address(_recv_exact(sock, 16)))
    elif atyp == ATYP_NAME:
        host = _recv_exact(sock, _recv_exact(sock, 1)[0]).decode("idna")
    else:
        raise Socks5Error(f"bad address type {atyp} in the reply")
    return host, _port(_recv_exact(sock, 2))


def _parse_udp(data: bytes) -> tuple[str, int, bytes]:
    """(host, port, payload) of a UDP relay datagram."""
    if len(data) < 4 or data[2] != 0:  # RSV RSV FRAG ATYP
        raise Socks5Error("bad or fragmented UDP reply")
    atyp, i = data[3], 4
    if atyp == ATYP_IPV4:
        host, i = str(ipaddress.IPv4Address(data[i : i + 4])), i + 4
    elif atyp == ATYP_IPV6:
        host, i = str(ipaddress.IPv6Address(data[i : i + 16])), i + 16
    elif atyp == ATYP_NAME:
        n = data[i]
        host, i = data[i + 1 : i + 1 + n].decode("idna", "replace"), i + 1 + n
    else:
        raise Socks5Error("bad address type in the UDP reply")
    return host, _port(data[i : i + 2]), data[i + 2 :]


def _connect(host: str, port: int, timeout: float) -> socket.socket:
    try:
        return socket.create_connection((host, port), timeout=timeout)
    except socket.gaierror:
        raise Socks5Error("proxy host not found") from None
    except ConnectionRefusedError:
        raise Socks5Error("connection refused") from None
    except TimeoutError:
        raise Socks5Error("no answer (timed out)") from None
    except OSError as e:
        raise Socks5Error(e.strerror or str(e)) from None


def _login(sock: socket.socket, username: str, password: str) -> None:
    methods = bytes([METHOD_NONE, METHOD_LOGIN] if username else [METHOD_NONE])
    sock.sendall(bytes([SOCKS_VERSION, len(methods)]) + methods)
    ver, method = _recv_exact(sock, 2)
    if ver != SOCKS_VERSION:
        raise Socks5Error("not a SOCKS5 proxy")
    if method == METHOD_REFUSED:
        raise Socks5Error(
            "the proxy wants a username and password"
            if not username
            else "the proxy refused every login method"
        )
    if method == METHOD_LOGIN:
        if not username:
            raise Socks5Error("the proxy wants a username and password")
        u, p = username.encode(), password.encode()
        sock.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
        if _recv_exact(sock, 2)[1] != 0:
            raise Socks5Error("wrong username or password")
    elif method != METHOD_NONE:
        raise Socks5Error(f"unsupported login method {method}")


def open_session(
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    timeout: float = TIMEOUT,
) -> socket.socket:
    """Connected, authenticated control socket."""
    sock = _connect(host, port, timeout)
    try:
        _login(sock, username, password)
    except TimeoutError:
        sock.close()
        raise Socks5Error("the proxy stopped answering (timed out)") from None
    except BaseException:
        sock.close()
        raise
    return sock


def request(sock: socket.socket, cmd: int, host: str, port: int) -> tuple[str, int]:
    """Send CONNECT (1) or UDP ASSOCIATE (3); returns the bound (host, port)."""
    sock.sendall(bytes([SOCKS_VERSION, cmd, 0]) + _addr(host, port))
    ver, rep, _rsv = _recv_exact(sock, 3)
    if ver != SOCKS_VERSION:
        raise Socks5Error("not a SOCKS5 reply")
    if rep != 0:
        raise Socks5Error(REPLIES.get(rep, f"error {rep}"))
    return _read_addr(sock)


def _trace(sock: socket.socket, host: str, *, tls: bool) -> dict[str, str]:
    """GET /cdn-cgi/trace over the tunnel: {'ip': ..., 'loc': ...}."""
    conn = (
        ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        if tls
        else sock
    )
    conn.sendall(
        f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {host}\r\n"
        "Connection: close\r\nUser-Agent: gtk-widgets\r\n\r\n".encode()
    )
    data = b""
    while len(data) < TRACE_MAX:
        chunk = conn.recv(RECV)
        if not chunk:
            break
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    if not head.startswith((b"HTTP/1.1 200", b"HTTP/1.0 200")):
        raise Socks5Error("the trace page did not load through the proxy")
    fields: dict[str, str] = {}
    for line in body.decode(errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            fields[key] = value
    return fields


def dns_query(qid: int, name: str = "one.one.one.one") -> bytes:
    """A-record query for `name` with id `qid`."""
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + b"\x00\x01\x00\x01"


def _ms_since(start: float) -> int:
    return round((time.monotonic() - start) * 1000)


def _relay(ctrl: socket.socket) -> tuple[str, int]:
    """UDP ASSOCIATE on the control socket: the relay's (host, port)."""
    try:
        relay_host, relay_port = request(ctrl, CMD_UDP_ASSOCIATE, ANY_ADDRESS, 0)
    except Socks5Error as e:
        raise Socks5Error(f"UDP refused: {e}") from None
    except TimeoutError:
        raise Socks5Error("UDP refused: no reply to UDP ASSOCIATE") from None
    if relay_port == 0:
        raise Socks5Error("UDP refused: no relay port")
    # 0.0.0.0 / :: mean "the address you reached me on"
    if ipaddress.ip_address(relay_host).is_unspecified:
        peer: tuple[str, int] = ctrl.getpeername()
        relay_host = peer[0]
    return relay_host, relay_port


def _answered(payload: bytes, qid: int) -> bool:
    return (
        len(payload) >= 4  # a DNS header's id and flags
        and payload[:2] == qid.to_bytes(2, "big")
        and bool(payload[2] & DNS_ANSWER)
    )


def _round_trip(
    udp: socket.socket, packet: bytes, relay: tuple[str, int], qid: int
) -> int:
    start = time.monotonic()
    for _ in range(UDP_TRIES):
        udp.sendto(packet, relay)
        try:
            while True:
                data, _src = udp.recvfrom(RECV)
                _h, _p, payload = _parse_udp(data)
                if _answered(payload, qid):
                    return _ms_since(start)
        except TimeoutError, Socks5Error:
            continue
    raise Socks5Error("UDP accepted, but no reply came back")


def udp_check(
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    *,
    target: tuple[str, int] = DNS,
    timeout: float = TIMEOUT,
) -> int:
    """UDP ASSOCIATE, then a DNS query through the relay. Returns the round
    trip in ms; raises Socks5Error with the reason UDP does not work."""
    ctrl = open_session(host, port, username, password, timeout)
    try:
        relay = _relay(ctrl)
        family = socket.AF_INET6 if ":" in relay[0] else socket.AF_INET
        with socket.socket(family, socket.SOCK_DGRAM) as udp:
            udp.settimeout(UDP_WAIT)
            qid = int.from_bytes(os.urandom(2), "big")
            packet = b"\x00\x00\x00" + _addr(*target) + dns_query(qid)
            return _round_trip(udp, packet, relay, qid)
    finally:
        ctrl.close()


def _country(loc: str) -> str | None:
    """Cloudflare's loc: a two-letter code, XX when it doesn't know."""
    if len(loc) == COUNTRY_LEN and loc.isalpha() and loc != UNKNOWN_COUNTRY:
        return loc
    return None


def _connect_check(
    host: str,
    port: int,
    login: tuple[str, str],
    trace: tuple[str, int, bool],
    timeout: float,
) -> Check:
    """The CONNECT half of check(): latency, exit IP and country."""
    res = Check(checked=int(time.time()))
    try:
        sock = open_session(host, port, *login, timeout)
        try:
            start = time.monotonic()
            request(sock, CMD_CONNECT, trace[0], trace[1])
            fields = _trace(sock, trace[0], tls=trace[2])
            res.latency_ms = _ms_since(start)
        finally:
            sock.close()
    except Socks5Error as e:
        res.error = str(e)
        return res
    except ssl.SSLError as e:
        res.error = f"TLS failed: {e.reason or e}"
        return res
    except TimeoutError:
        res.error = "the proxy stopped answering (timed out)"
        return res
    except OSError as e:
        res.error = e.strerror or str(e)
        return res
    res.ok, res.ip = True, fields.get("ip")
    res.country = _country(fields.get("loc", ""))
    return res


def check(
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    *,
    trace: tuple[str, int, bool] = TRACE,
    dns: tuple[str, int] = DNS,
    timeout: float = TIMEOUT,
    udp: bool = True,
) -> Check:
    """Full check: the CONNECT trace, then (if it worked and udp) the UDP
    round trip."""
    res = _connect_check(host, port, (username, password), trace, timeout)
    if not res.ok or not udp:
        return res
    try:
        res.udp_ms = udp_check(
            host, port, username, password, target=dns, timeout=timeout
        )
        res.udp = True
    except Socks5Error as e:
        res.udp, res.udp_error = False, str(e)
    except OSError as e:
        res.udp, res.udp_error = False, e.strerror or str(e)
    return res


def alive(
    host: str,
    port: int,
    username: str = "",
    password: str = "",
    *,
    target: tuple[str, int, bool] = TRACE,
    timeout: float = TIMEOUT,
) -> tuple[bool, str | None]:
    """Cheap liveness probe: login and CONNECT (no data). (ok, error)."""
    try:
        sock = open_session(host, port, username, password, timeout)
        try:
            request(sock, CMD_CONNECT, target[0], target[1])
        finally:
            sock.close()
    except Socks5Error as e:
        return False, str(e)
    except TimeoutError:
        return False, "the proxy stopped answering (timed out)"
    except OSError as e:
        return False, e.strerror or str(e)
    return True, None
