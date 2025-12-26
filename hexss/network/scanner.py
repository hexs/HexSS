import subprocess
import platform
import concurrent.futures
import ipaddress
import itertools
from typing import List, Iterable, Iterator, Union
from hexss.constants import *


def generate_ip_combinations(structure: List[List[int]]) -> Iterator[str]:
    """
    Generates IP strings from a list of octet lists.
    """
    for parts in itertools.product(*structure):
        yield ".".join(map(str, parts))


def ping_host(ip: str) -> Union[str, None]:
    """
    Pings a single host. Returns the IP if successful, None otherwise.
    """
    system_name = platform.system().lower()
    command = ['ping', ip]
    if system_name == 'windows':
        # -n 1: Try 1 time
        # -w 500: Wait 500ms
        command[1:1] = ['-n', '1', '-w', '500']
        creation_flags = 0x08000000
    else:
        # Linux/Mac settings
        # -c 1: Try 1 time
        # -W 1: Wait 1 second
        command[1:1] = ['-c', '1', '-W', '1']
        creation_flags = 0

    try:
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,  # ปิด Output
            stderr=subprocess.DEVNULL,  # ปิด Error
            stdin=subprocess.DEVNULL,  # ปิด Input (สำคัญสำหรับ Windows thread safety)
            creationflags=creation_flags,
            check=True
        )
        return ip
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None


def scan_network(ip_iterator: Iterable[str], max_threads: int = 50):
    """
    Scans a network using a thread pool.
    On Windows, keep max_threads <= 100 to avoid [WinError 6].
    """
    target_ips = list(ip_iterator)
    total_ips = len(target_ips)

    if total_ips == 0:
        print("[-] No IPs provided to scan.")
        return

    print(f"[*] Prepared to scan {total_ips} addresses.")
    active_hosts = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_ip = {executor.submit(ping_host, ip): ip for ip in target_ips}

            for i, future in enumerate(concurrent.futures.as_completed(future_to_ip)):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        print(end=f"\r[+] Found Active: {result}\n")
                        active_hosts.append(result)
                except Exception as exc:
                    print(end=f"\r[-] Unexpected error scanning {ip}: {exc}\n")

                print(end=f"\r{YELLOW}[*] Progress: {i + 1}/{total_ips} ({((i + 1) / total_ips) * 100:.1f}%){END}")

    except KeyboardInterrupt:
        print(end=f"\r{RED}[!] Scan interrupted by user. Showing partial results...{END}\n")
        executor.shutdown(wait=False, cancel_futures=True)

    print(end="\r--- Scan Complete ---\n")
    print(end=f"\rTotal Active Hosts Found: {len(active_hosts)}\n")

    active_hosts.sort(key=lambda ip: int(ipaddress.IPv4Address(ip)))
    print(active_hosts)


if __name__ == "__main__":
    scan_network(
        generate_ip_combinations([[192], [168], [1, 2, 3], range(1, 255)]),
        max_threads=100
    )
