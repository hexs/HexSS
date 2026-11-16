"""End-to-end test for utils.py.

Usage:
    python example.py [port]        (default port: 8000)

It starts two throw-away HTTP servers on the SAME port but different hosts,
then checks that the port helpers see them and that kill_process_on_port()
can kill only the one on the selected host.
"""
from __future__ import annotations

import subprocess
import sys
import time

from hexss.network import utils as net

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
LOOPBACK = "127.0.0.1"

failures = 0


def check(name: str, condition: bool) -> None:
    global failures
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}")
    if not condition:
        failures += 1


def start_server(host: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", host],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def main() -> int:
    # ---------------------------------------------------------------- IPs
    print("== IP addresses ==")
    ipv4, ipv6 = net.get_ip_addresses()
    print("  primary  :", net.get_primary_ipv4())
    print("  IPv4     :", ipv4)
    print("  IPv6     :", ipv6)
    print("  hosts    :", sorted(net.get_local_ipv4_hosts()))
    check("at least one IPv4 or loopback host", len(net.get_local_ipv4_hosts()) >= 2)

    lan_ip = ipv4[0] if ipv4 else None
    if lan_ip is None:
        print("\nNo non-loopback IPv4 found: cannot test two hosts on one port.")
        return 1

    # ------------------------------------------------------- validation
    print("\n== Validation ==")
    for bad_port in (0, 70000, -1, "80"):
        try:
            net.is_port_free(bad_port)  # type: ignore[arg-type]
            check(f"port {bad_port!r} rejected", False)
        except ValueError:
            check(f"port {bad_port!r} rejected", True)
    try:
        net.find_listening_pids(PORT, "not-an-ip")
        check("bad host rejected", False)
    except ValueError:
        check("bad host rejected", True)

    # ------------------------------------------------------- port state
    print(f"\n== Port {PORT} ==")
    if not net.is_port_free(PORT):
        print(f"  Port {PORT} is already in use; pick another: python example.py 8123")
        return 1
    check("port free before starting", True)

    servers: list[subprocess.Popen] = []
    try:
        local_srv = start_server(LOOPBACK)
        lan_srv = start_server(lan_ip)
        servers += [local_srv, lan_srv]

        check(f"server on {LOOPBACK} is listening",
              wait_until(lambda: net.is_port_listening(LOOPBACK, PORT)))
        check(f"server on {lan_ip} is listening",
              wait_until(lambda: net.is_port_listening(lan_ip, PORT)))
        check(f"{LOOPBACK}:{PORT} no longer bindable", not net.is_port_free(PORT, LOOPBACK))
        check(f"{lan_ip}:{PORT} no longer bindable", not net.is_port_free(PORT, lan_ip))
        check("0.0.0.0 cannot be bound while both run", not net.is_port_free(PORT, "0.0.0.0"))

        # ------------------------------------------------- find / kill
        print("\n== find_listening_pids / kill_process_on_port ==")
        try:
            all_pids = net.find_listening_pids(PORT)
        except OSError as exc:
            print(f"  SKIPPED (system tool missing): {exc}")
            return 1 if failures else 0

        # (On Windows with a venv, python.exe may be a launcher, so PIDs can differ.)
        check("no host filter -> both servers found",
              {local_srv.pid, lan_srv.pid} <= set(all_pids))
        check(f"host={LOOPBACK} -> only the loopback server",
              net.find_listening_pids(PORT, LOOPBACK) == [local_srv.pid])
        check(f"host={lan_ip} -> only the LAN server",
              net.find_listening_pids(PORT, lan_ip) == [lan_srv.pid])

        killed = net.kill_process_on_port(PORT, LOOPBACK, grace_period=0.5)
        local_srv.wait(timeout=5)
        check(f"kill host={LOOPBACK} -> returned its PID", killed == [local_srv.pid])
        check(f"{LOOPBACK} server is gone", not net.is_port_listening(LOOPBACK, PORT))
        check(f"{lan_ip} server still alive", net.is_port_listening(lan_ip, PORT))

        killed = net.kill_process_on_port(PORT, grace_period=0.5)
        lan_srv.wait(timeout=5)
        check("kill without host -> remaining server killed", killed == [lan_srv.pid])
        check("port is free again", wait_until(lambda: net.is_port_free(PORT)))
        check("nothing left to kill", net.kill_process_on_port(PORT) == [])
    finally:
        for proc in servers:  # safety net so no server is left running
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    print(f"\n{'ALL TESTS PASSED' if failures == 0 else f'{failures} TEST(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())