"""Minimal SOCKS5 client (RFC 1928 + RFC 1929 auth) for checking proxies.

check() runs a TCP CONNECT to Cloudflare's trace page for latency, exit IP and
country, and a real UDP ASSOCIATE round trip (a DNS query through the relay):
providers often claim UDP support and then drop every datagram. Blocking
sockets with timeouts; callers run it off the GTK main thread.
"""

import ipaddress, os, socket, ssl, struct, time

TIMEOUT = 6.0
UDP_TRIES, UDP_WAIT = 3, 1.5
TRACE = ("1.1.1.1", 443, True)   # host, port, TLS: https://1.1.1.1/cdn-cgi/trace
DNS = ("1.1.1.1", 53)

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


def _recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise Socks5Error("the proxy closed the connection")
        data += chunk
    return data


def _addr(host, port):
    """ATYP + address + port for a request or UDP header."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        name = host.encode("idna")
        if len(name) > 255:
            raise Socks5Error("host name too long")
        return b"\x03" + bytes([len(name)]) + name + struct.pack("!H", port)
    atyp = b"\x01" if ip.version == 4 else b"\x04"
    return atyp + ip.packed + struct.pack("!H", port)


def _read_addr(sock):
    atyp = _recv_exact(sock, 1)[0]
    if atyp == 1:
        host = str(ipaddress.IPv4Address(_recv_exact(sock, 4)))
    elif atyp == 4:
        host = str(ipaddress.IPv6Address(_recv_exact(sock, 16)))
    elif atyp == 3:
        host = _recv_exact(sock, _recv_exact(sock, 1)[0]).decode("idna")
    else:
        raise Socks5Error(f"bad address type {atyp} in the reply")
    return host, struct.unpack("!H", _recv_exact(sock, 2))[0]


def _parse_udp(data):
    """(host, port, payload) of a UDP relay datagram."""
    if len(data) < 4 or data[2] != 0:
        raise Socks5Error("bad or fragmented UDP reply")
    atyp, i = data[3], 4
    if atyp == 1:
        host, i = str(ipaddress.IPv4Address(data[i:i + 4])), i + 4
    elif atyp == 4:
        host, i = str(ipaddress.IPv6Address(data[i:i + 16])), i + 16
    elif atyp == 3:
        n = data[i]
        host, i = data[i + 1:i + 1 + n].decode("idna", "replace"), i + 1 + n
    else:
        raise Socks5Error("bad address type in the UDP reply")
    port = struct.unpack("!H", data[i:i + 2])[0]
    return host, port, data[i + 2:]


def open_session(host, port, username="", password="", timeout=TIMEOUT):
    """Connected, authenticated control socket."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except socket.gaierror:
        raise Socks5Error("proxy host not found")
    except ConnectionRefusedError:
        raise Socks5Error("connection refused")
    except TimeoutError:
        raise Socks5Error("no answer (timed out)")
    except OSError as e:
        raise Socks5Error(e.strerror or str(e))
    try:
        methods = b"\x00\x02" if username else b"\x00"
        sock.sendall(b"\x05" + bytes([len(methods)]) + methods)
        ver, method = _recv_exact(sock, 2)
        if ver != 5:
            raise Socks5Error("not a SOCKS5 proxy")
        if method == 0xFF:
            raise Socks5Error("the proxy wants a username and password" if not username
                              else "the proxy refused every login method")
        if method == 2:
            if not username:
                raise Socks5Error("the proxy wants a username and password")
            u, p = username.encode(), password.encode()
            sock.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            if _recv_exact(sock, 2)[1] != 0:
                raise Socks5Error("wrong username or password")
        elif method != 0:
            raise Socks5Error(f"unsupported login method {method}")
        return sock
    except TimeoutError:
        sock.close()
        raise Socks5Error("the proxy stopped answering (timed out)")
    except BaseException:
        sock.close()
        raise


def request(sock, cmd, host, port):
    """Send CONNECT (1) or UDP ASSOCIATE (3); returns the bound (host, port)."""
    sock.sendall(b"\x05" + bytes([cmd, 0]) + _addr(host, port))
    ver, rep, _rsv = _recv_exact(sock, 3)
    if ver != 5:
        raise Socks5Error("not a SOCKS5 reply")
    if rep != 0:
        raise Socks5Error(REPLIES.get(rep, f"error {rep}"))
    return _read_addr(sock)


def _trace(sock, host, tls):
    """GET /cdn-cgi/trace over the tunnel: {'ip': ..., 'loc': ...}."""
    if tls:
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    sock.sendall(f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {host}\r\n"
                 "Connection: close\r\nUser-Agent: gtk-widgets\r\n\r\n".encode())
    data = b""
    while len(data) < 65536:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    if not head.startswith(b"HTTP/1.1 200") and not head.startswith(b"HTTP/1.0 200"):
        raise Socks5Error("the trace page did not load through the proxy")
    fields = dict(line.split("=", 1) for line in body.decode(errors="replace").splitlines()
                  if "=" in line)
    return fields


def dns_query(qid, name="one.one.one.one"):
    """A-record query for `name` with id `qid`."""
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + b"\x00\x01\x00\x01"


def udp_check(host, port, username="", password="", target=DNS, timeout=TIMEOUT):
    """UDP ASSOCIATE, then a DNS query through the relay. Returns the round
    trip in ms; raises Socks5Error with the reason UDP does not work."""
    ctrl = open_session(host, port, username, password, timeout)
    try:
        try:
            relay_host, relay_port = request(ctrl, 3, "0.0.0.0", 0)
        except Socks5Error as e:
            raise Socks5Error(f"UDP refused: {e}")
        except TimeoutError:
            raise Socks5Error("UDP refused: no reply to UDP ASSOCIATE")
        if relay_port == 0:
            raise Socks5Error("UDP refused: no relay port")
        # 0.0.0.0 / :: mean "the address you reached me on"
        if ipaddress.ip_address(relay_host).is_unspecified:
            relay_host = ctrl.getpeername()[0]
        family = socket.AF_INET6 if ":" in relay_host else socket.AF_INET
        udp = socket.socket(family, socket.SOCK_DGRAM)
        try:
            udp.settimeout(UDP_WAIT)
            qid = int.from_bytes(os.urandom(2), "big")
            packet = b"\x00\x00\x00" + _addr(*target) + dns_query(qid)
            start = time.monotonic()
            for _ in range(UDP_TRIES):
                udp.sendto(packet, (relay_host, relay_port))
                try:
                    while True:
                        data, _src = udp.recvfrom(4096)
                        _h, _p, payload = _parse_udp(data)
                        if len(payload) >= 4 and payload[:2] == qid.to_bytes(2, "big") \
                                and payload[2] & 0x80:
                            return round((time.monotonic() - start) * 1000)
                except (TimeoutError, Socks5Error):
                    continue
            raise Socks5Error("UDP accepted, but no reply came back")
        finally:
            udp.close()
    finally:
        ctrl.close()


def check(host, port, username="", password="", trace=TRACE, dns=DNS, timeout=TIMEOUT, udp=True):
    """Full check. Returns a dict: ok, error, latency_ms, ip, country, udp
    (True/False/None when not run), udp_ms, udp_error, checked (epoch)."""
    res = {"ok": False, "error": None, "latency_ms": None, "ip": None, "country": None,
           "udp": None, "udp_ms": None, "udp_error": None, "checked": int(time.time())}
    try:
        sock = open_session(host, port, username, password, timeout)
        try:
            start = time.monotonic()
            request(sock, 1, trace[0], trace[1])
            fields = _trace(sock, trace[0], trace[2])
            res["latency_ms"] = round((time.monotonic() - start) * 1000)
        finally:
            sock.close()
        res["ok"], res["ip"] = True, fields.get("ip")
        loc = fields.get("loc", "")
        res["country"] = loc if len(loc) == 2 and loc.isalpha() and loc != "XX" else None
    except (Socks5Error, ssl.SSLError) as e:
        res["error"] = str(e) if isinstance(e, Socks5Error) else f"TLS failed: {e.reason or e}"
        return res
    except TimeoutError:
        res["error"] = "the proxy stopped answering (timed out)"
        return res
    except OSError as e:
        res["error"] = e.strerror or str(e)
        return res
    if udp:
        try:
            res["udp_ms"] = udp_check(host, port, username, password, dns, timeout)
            res["udp"] = True
        except Socks5Error as e:
            res["udp"], res["udp_error"] = False, str(e)
        except OSError as e:
            res["udp"], res["udp_error"] = False, e.strerror or str(e)
    return res


def alive(host, port, username="", password="", target=TRACE, timeout=TIMEOUT):
    """Cheap liveness probe: login and CONNECT (no data). (ok, error)."""
    try:
        sock = open_session(host, port, username, password, timeout)
        try:
            request(sock, 1, target[0], target[1])
        finally:
            sock.close()
    except Socks5Error as e:
        return False, str(e)
    except TimeoutError:
        return False, "the proxy stopped answering (timed out)"
    except OSError as e:
        return False, e.strerror or str(e)
    return True, None
