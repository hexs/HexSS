import os
from typing import List, Tuple

import hexss
import warnings
from .utils import get_ip_addresses, get_primary_ipv4, is_port_listening, get_local_ipv4_hosts, open_url, \
    kill_process_on_port


def get_ipv4() -> str:
    warnings.warn(
        "get_ipv4() is deprecated. Use get_primary_ipv4() instead.",
        category=DeprecationWarning,
        stacklevel=2
    )
    return get_primary_ipv4()


def get_ips() -> Tuple[List[str], List[str]]:
    warnings.warn(
        "get_ips() is deprecated. Use get_ip_addresses() instead.",
        category=DeprecationWarning,
        stacklevel=2
    )
    return get_ip_addresses(True)


def get_all_ipv4() -> List[str]:
    warnings.warn(
        "get_all_ipv4() is deprecated. Use get_local_ipv4_hosts() instead.",
        category=DeprecationWarning,
        stacklevel=2
    )
    return get_local_ipv4_hosts()


def is_port_available(ip: str, port: int) -> bool:
    warnings.warn(
        "is_port_available() is deprecated. Use is_port_listening() instead.",
        category=DeprecationWarning,
        stacklevel=2
    )
    return is_port_listening(ip, port)


def close_port(ip: str, port: int, verbose: bool = True) -> None:
    warnings.warn(
        "close_port() is deprecated. Use kill_process_on_port() instead.",
        category=DeprecationWarning,
        stacklevel=2
    )
    kill_process_on_port(port, ip)


def scan_wifi():
    if hexss.system == 'Windows':
        try:
            from pywifi import PyWiFi
        except ImportError:
            hexss.check_packages('pywifi', 'comtypes', auto_install=True)
            from pywifi import PyWiFi

        wifi = PyWiFi()
        for i, iface in enumerate(wifi.interfaces()):
            print(f"{i}: {iface.name()}")
            iface.scan()
            results = iface.scan_results()
            for network in results:
                print(f"SSID: {network.ssid}, Signal: {network.signal}, Frequency: {network.freq}")
    else:
        try:
            from wifi import Cell
        except ImportError:
            hexss.check_packages('wifi', auto_install=True)
            from wifi import Cell

        interfaces = os.listdir('/sys/class/net/')
        for i, iface in enumerate(interfaces):
            try:
                print(f"{i}: {iface}")
                networks = Cell.all(iface)
                for network in networks:
                    print(f"SSID: {network.ssid}, Signal: {network.signal}, Frequency: {network.frequency}")
            except Exception as e:
                ...
