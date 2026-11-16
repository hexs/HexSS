"""Small, dependency-free network helpers (Windows / Linux / macOS).

Public API
----------
get_primary_ipv4()        -> IP address used for the default route
get_ip_addresses()        -> (ipv4_list, ipv6_list) of this machine
get_local_ipv4_hosts()    -> set of IPv4 addresses plus "localhost"
open_url(url)             -> open a URL in the default browser
is_port_listening(...)    -> True if something accepts connections on host:port
is_port_free(...)         -> True if host:port can be bound right now
find_listening_pids(port) -> PIDs of processes listening on a TCP port
kill_process_on_port(...) -> terminate processes listening on a TCP port
"""
from __future__ import annotations

import ipaddress
import os
import signal
import socket
import struct
import subprocess
import sys
import time
import webbrowser

__all__ = [
    "get_primary_ipv4",
    "get_ip_addresses",
    "get_local_ipv4_hosts",
    "open_url",
    "is_port_listening",
    "is_port_free",
    "find_listening_pids",
    "kill_process_on_port",
]

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _check_port(port: int) -> int:
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError(f"Invalid port {port!r}: must be an integer from 1 to 65535.")
    return port


# --------------------------------------------------------------------------- #
# IP addresses
# --------------------------------------------------------------------------- #
def get_primary_ipv4() -> str:
    """Return the IPv4 address used to reach the outside world (default route).

    A UDP socket is "connected" to a reserved TEST-NET address; no packet is
    sent, the OS just picks the outgoing interface. Falls back to 127.0.0.1
    when the machine has no route.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


# Netlink constants (linux/netlink.h, linux/rtnetlink.h, linux/if_addr.h)
_NLMSG_ERROR = 2
_NLMSG_DONE = 3
_RTM_NEWADDR = 20
_RTM_GETADDR = 22
_NLM_F_REQUEST = 0x01
_NLM_F_DUMP = 0x300  # NLM_F_ROOT | NLM_F_MATCH
_IFA_ADDRESS = 1
_IFA_LOCAL = 2

_NLMSG_HDR = struct.Struct("=IHHII")  # len, type, flags, seq, pid
_IFADDR_MSG = struct.Struct("=BBBBI")  # family, prefixlen, flags, scope, index
_RTATTR = struct.Struct("=HH")  # len, type


def _align4(length: int) -> int:
    return (length + 3) & ~3


def _parse_ifaddr(body: bytes) -> str | None:
    """Extract the address from an RTM_NEWADDR message body."""
    if len(body) < _IFADDR_MSG.size:
        return None
    offset = _IFADDR_MSG.size
    address = local = None
    while offset + _RTATTR.size <= len(body):
        rta_len, rta_type = _RTATTR.unpack_from(body, offset)
        if rta_len < _RTATTR.size:
            break
        data = body[offset + _RTATTR.size: offset + rta_len]
        if rta_type == _IFA_ADDRESS:
            address = data
        elif rta_type == _IFA_LOCAL:
            local = data
        offset += _align4(rta_len)

    raw = local or address  # IFA_LOCAL is the real local address on point-to-point links
    if raw is None or len(raw) not in (4, 16):
        return None
    return str(ipaddress.ip_address(raw))


def _netlink_addresses() -> list[str]:
    """List every interface address on Linux using an rtnetlink dump."""
    payload = _IFADDR_MSG.pack(socket.AF_UNSPEC, 0, 0, 0, 0)
    header = _NLMSG_HDR.pack(
        _NLMSG_HDR.size + len(payload), _RTM_GETADDR, _NLM_F_REQUEST | _NLM_F_DUMP, 1, 0
    )
    found: list[str] = []

    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, socket.NETLINK_ROUTE) as sock:
        sock.settimeout(2.0)
        sock.sendall(header + payload)

        done = False
        while not done:
            data = sock.recv(65536)
            if not data:
                break
            offset = 0
            while offset + _NLMSG_HDR.size <= len(data):
                length, msg_type, *_ = _NLMSG_HDR.unpack_from(data, offset)
                if length < _NLMSG_HDR.size:
                    raise OSError("Malformed netlink message.")
                if msg_type == _NLMSG_DONE:
                    done = True
                    break
                if msg_type == _NLMSG_ERROR:
                    raise OSError("Netlink request failed.")
                if msg_type == _RTM_NEWADDR:
                    body = data[offset + _NLMSG_HDR.size: offset + length]
                    address = _parse_ifaddr(body)
                    if address:
                        found.append(address)
                offset += _align4(length)
    return found


def _resolver_addresses() -> list[str]:
    """Addresses the hostname resolves to (Windows / macOS / Linux fallback)."""
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return [str(info[4][0]).split("%", 1)[0] for info in infos]  # strip IPv6 scope id


def get_ip_addresses(include_loopback: bool = False) -> tuple[list[str], list[str]]:
    """Return ``(ipv4_addresses, ipv6_addresses)`` of this machine.

    The primary IPv4 address (default route) is listed first. Duplicates are
    removed while keeping order. Loopback addresses are omitted unless
    ``include_loopback`` is True.
    """
    raw: list[str] = []
    if IS_LINUX:
        try:
            raw = _netlink_addresses()
        except OSError:  # e.g. restricted sandbox: fall back to the resolver
            raw = _resolver_addresses()
    else:
        raw = _resolver_addresses()

    ipv4: list[str] = []
    ipv6: list[str] = []
    for text in (get_primary_ipv4(), *raw):
        try:
            ip = ipaddress.ip_address(text)
        except ValueError:
            continue
        if ip.is_loopback and not include_loopback:
            continue
        bucket = ipv4 if ip.version == 4 else ipv6
        normalized = str(ip)
        if normalized not in bucket:
            bucket.append(normalized)
    return ipv4, ipv6


def get_local_ipv4_hosts() -> list[str]:
    return sorted({"localhost", socket.gethostname(), *get_ip_addresses(True)[0]})


# --------------------------------------------------------------------------- #
# Browser
# --------------------------------------------------------------------------- #
def open_url(url: str) -> bool:
    """Open ``url`` in the default web browser.

    Returns True if a browser was launched. No shell is involved, so the URL
    cannot be used for command injection.

    Example:
        open_url("http://192.168.1.10:5555")
    """
    return webbrowser.open(url)


# --------------------------------------------------------------------------- #
# Ports
# --------------------------------------------------------------------------- #
def is_port_listening(host: str, port: int, timeout: float = 1.0) -> bool:
    """True if something accepts TCP connections on ``host:port``.

    Use a concrete address (``127.0.0.1`` or a LAN IP), not ``0.0.0.0``.
    """
    _check_port(port)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    """True if ``host:port`` can be bound right now.

    Binding is the only reliable test: a port can be unusable even though
    nothing is accepting connections on it (reserved ranges, TIME_WAIT,
    exclusive binds, ...).
    """
    _check_port(port)
    try:
        family, socktype, proto, _, sockaddr = socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )[0]
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host {host!r}.") from exc

    with socket.socket(family, socktype, proto) as sock:
        if IS_WINDOWS:
            # SO_REUSEADDR on Windows would let us steal a port in use.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(sockaddr)
        except OSError:
            return False
    return True


def _normalize_host(host: str | None) -> str | None:
    """Accept an IP literal or "localhost"; return the canonical IP string."""
    if host is None:
        return None
    if host == "localhost":
        return "127.0.0.1"
    try:
        return str(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        raise ValueError(f"host must be an IP address or 'localhost', got {host!r}.") from None


def _listener_matches(local_address: str, host: str | None) -> bool:
    """Does a listener bound to ``local_address`` occupy ``host``?

    A wildcard listener (0.0.0.0, ::, *) occupies every address, so it matches.
    """
    if host is None or local_address == "*":
        return True
    try:
        addr = ipaddress.ip_address(local_address.strip("[]").split("%", 1)[0])
    except ValueError:
        return False
    return addr.is_unspecified or str(addr) == host


def _list_listeners(port: int) -> list[tuple[int, str]]:
    """Return ``(pid, local_address)`` for every TCP listener on ``port``."""
    if IS_WINDOWS:
        script = (
            f"Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue "
            '| ForEach-Object { "$($_.OwningProcess) $($_.LocalAddress)" }'
        )
        command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    else:
        # -F output: "p<pid>" lines followed by "n<address>:<port>" lines
        command = ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpn"]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except FileNotFoundError as exc:
        raise OSError(f"Required tool not found: {command[0]!r}") from exc

    listeners: list[tuple[int, str]] = []
    if IS_WINDOWS:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit():
                listeners.append((int(parts[0]), parts[1]))
    else:
        pid = None
        for line in result.stdout.splitlines():
            if line.startswith("p") and line[1:].isdigit():
                pid = int(line[1:])
            elif line.startswith("n") and pid is not None:
                listeners.append((pid, line[1:].rsplit(":", 1)[0]))
    return listeners


def find_listening_pids(port: int, host: str | None = None) -> list[int]:
    """PIDs of processes *listening* on TCP ``port`` (clients are ignored).

    If ``host`` is given (an IP or "localhost"), only listeners occupying that
    address are returned: those bound to exactly ``host`` and those bound to a
    wildcard (0.0.0.0 / ::), because a wildcard listener also owns ``host``.

    Raises:
        ValueError: invalid port or host.
        OSError: if the required system tool (PowerShell / lsof) is missing.
    """
    _check_port(port)
    wanted = _normalize_host(host)
    return sorted({pid for pid, addr in _list_listeners(port) if _listener_matches(addr, wanted)})


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate(pid: int, grace_period: float) -> None:
    """Ask nicely (SIGTERM), then force (SIGKILL). On Windows SIGTERM is a hard kill."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if IS_WINDOWS:
        return

    deadline = time.monotonic() + grace_period
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def kill_process_on_port(port: int, host: str | None = None, *, grace_period: float = 3.0) -> list[int]:
    """Terminate the processes listening on TCP ``port``.

    With ``host`` set, only processes occupying that address are terminated, so
    a server on 10.87.1.28:8000 is left alone when you target 127.0.0.1:8000
    (unless it is bound to a wildcard such as 0.0.0.0, which owns both).
    The current process is never touched. Returns the PIDs that were signalled.

    Raises:
        ValueError: invalid port or host.
        OSError: required system tool missing.
        PermissionError: not allowed to terminate a process.

    Example:
        kill_process_on_port(8000, "127.0.0.1")
    """
    protected = {0, os.getpid()} | ({4} if IS_WINDOWS else set())
    pids = [pid for pid in find_listening_pids(port, host) if pid not in protected]
    for pid in pids:
        _terminate(pid, grace_period)
    return pids


if __name__ == "__main__":
    print("Primary IPv4 :", get_primary_ipv4())
    print("IPv4         :", get_ip_addresses(True)[0])
    print("IPv6         :", get_ip_addresses(True)[1])
    print("Local hosts  :", get_local_ipv4_hosts())
