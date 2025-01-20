import os
import socket
from socket import AddressFamily
import subprocess
import platform
from typing import List, Tuple, Dict, Optional
from hexss import json_load, json_dump


def get_hexss_dir():
    if platform.system() == "Windows":
        hexss_dir = os.path.join(f'C:/Users/{username}/AppData/Roaming/hexss')
    else:
        hexss_dir = os.path.join(f'/home/{username}/hexss')
    os.makedirs(hexss_dir, exist_ok=True)
    return hexss_dir


def get_hostname() -> str:
    """Retrieve the hostname of the current machine."""
    return socket.gethostname()


def get_username() -> str:
    """Retrieve the username of the currently logged-in user."""
    return os.getlogin()


def get_ipv4() -> str:
    """Retrieve the primary IPv4 address of the system."""
    return socket.gethostbyname(socket.gethostname())


def get_ips() -> Tuple[List[str], List[str]]:
    """
    Retrieve all IPv4 and IPv6 addresses of the machine.

    Returns:
        Tuple[List[str], List[str]]: A tuple containing two lists: IPv4 addresses and IPv6 addresses.

    Raises:
        OSError: If the operating system is unsupported.
    """
    ipv4, ipv6 = [], []
    if platform.system() == "Windows":
        for info in socket.getaddrinfo(socket.gethostname(), None):
            protocol, *_, (ip, *_) = info
            if protocol == AddressFamily.AF_INET:
                ipv4.append(ip)
            elif protocol == AddressFamily.AF_INET6:
                ipv6.append(ip)
    elif platform.system() == "Linux":
        ipv4, ipv6 = _get_ips_linux()
    else:
        raise OSError("Unsupported operating system.")
    return ipv4, ipv6


def _get_ips_linux() -> Tuple[List[str], List[str]]:
    """
    Helper function to retrieve IPs on Linux using netlink sockets.

    Returns:
        Tuple[List[str], List[str]]: A tuple containing IPv4 and IPv6 addresses.
    """
    ipv4, ipv6 = [], []
    RTM_NEWADDR = 20
    RTM_GETADDR = 22
    NLM_F_REQUEST = 0x01
    NLM_F_ROOT = 0x100
    s = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW)
    req = (
        # nlmsghdr
            int.to_bytes(0, 4, 'little', signed=False) +  # nlmsg_len
            int.to_bytes(RTM_GETADDR, 2, 'little', signed=False) +  # nlmsg_type
            int.to_bytes(NLM_F_REQUEST | NLM_F_ROOT, 2, 'little', signed=False) +  # nlmsg_flags
            int.to_bytes(0, 2, 'little', signed=False) +  # nlmsg_seq
            int.to_bytes(0, 2, 'little', signed=False) +  # nlmsg_pid
            # ifinfomsg
            b'\0' * 8
    )
    req = int.to_bytes(len(req), 4, 'little') + req[4:]
    s.sendall(req)
    full_resp = s.recv(4096)
    while full_resp:
        resp = full_resp
        # nlmsghdr
        nlmsg_len = int.from_bytes(resp[0:4], 'little', signed=False)
        nlmsg_type = int.from_bytes(resp[4:6], 'little', signed=False)
        assert not nlmsg_len % 4, nlmsg_len
        resp = resp[16:nlmsg_len]
        full_resp = full_resp[nlmsg_len:]
        if nlmsg_type == 3:  # NLMSG_DONE
            assert not full_resp, full_resp
            break
        if not full_resp:
            full_resp = s.recv(4096)
        assert nlmsg_type == RTM_NEWADDR, (nlmsg_type, resp[:32])
        # ifaddrmsg
        ifa_family = int.from_bytes(resp[0:1], 'little', signed=False)
        ifa_index = int.from_bytes(resp[4:8], 'little', signed=False)
        resp = resp[8:]
        while resp:
            # rtattr
            rta_len = int.from_bytes(resp[0:2], 'little', signed=False)
            rta_type = int.from_bytes(resp[2:4], 'little', signed=False)
            data = resp[4:rta_len]

            if rta_type == 1:  # IFLA_ADDRESS
                if ifa_family == socket.AF_INET:
                    ip = '.'.join('%d' % c for c in data)
                    ipv4.append(ip)
                if ifa_family == socket.AF_INET6:
                    ip = ':'.join(('%02x%02x' % (chunk[0], chunk[1]) if chunk != b'\0\0' else '') for chunk in
                                  [data[0:2], data[2:4], data[4:6], data[6:8], data[8:10], data[10:12], data[12:14],
                                   data[14:16]])
                    ipv6.append(ip)
            if rta_type == 3:  # IFLA_IFNAME
                name = data.rstrip(b'\0').decode()
                # print(ifa_index, name)

            # need to round up to multiple of 4
            if rta_len % 4:
                rta_len += 4 - rta_len % 4
            resp = resp[rta_len:]
    s.close()

    return ipv4, ipv6


def get_all_ipv4() -> List[str]:
    """
    Retrieve all IPv4 addresses of the machine.

    Returns:
        List[str]: A list of all IPv4 addresses.
    """
    return get_ips()[0]


def open_url(url: str) -> None:
    """
    Open a given URL in the default web browser.

    Args:
        url (str): The URL to open.

    Raises:
        OSError: If the operating system is unsupported.

    Example:
        open_url("http://192.168.225.137:5555")
    """
    if platform.system() == "Windows":
        os.system(f'start "" "{url}"')
    elif platform.system() == "Linux":
        os.system(f'xdg-open "{url}"')
    elif platform.system() == "Darwin":  # macOS
        os.system(f'open "{url}"')
    else:
        raise OSError("Unsupported operating system.")


def is_port_available(ip: str, port: int) -> bool:
    """
    Check if a specific port on a given IP address is available.

    Args:
        ip (str): IP address to check.
        port (int): Port number to check.

    Returns:
        bool: True if the port is available, False otherwise.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)  # 1-second timeout
            return sock.connect_ex((ip, port)) != 0
    except socket.error:
        return False


def close_port(ip: str, port: int) -> None:
    """
    Close a specific TCP port on the given IP address.

    Args:
        ip (str): IP address as a string.
        port (int): Port number.

    Raises:
        ValueError: If the port number is invalid.
        OSError: If the operating system is unsupported.

    Example:
        close_port("192.168.225.137", 2002)
    """
    if not (0 < port <= 65535):
        raise ValueError("Invalid port number. Must be between 1 and 65535.")

    if platform.system() == "Windows":
        command = f'''powershell -Command "Get-NetTCPConnection -LocalAddress {ip} -LocalPort {port} | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force }}"'''
    elif platform.system() == "Linux":
        command = f"lsof -ti tcp:{port} | xargs kill -9"
    elif platform.system() == "Darwin":  # macOS
        command = f"lsof -ti tcp:{port} | xargs kill -9"
    else:
        raise OSError("Unsupported operating system.")

    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Successfully closed port {port} on {ip}")
    else:
        print(f"Failed to close port {port} on {ip}. Error: {result.stderr}")


def initialize_proxies() -> Optional[Dict[str, str]]:
    """
    Initialize and retrieve the proxies configuration.

    Returns:
        Optional[Dict[str, str]]: The proxies dictionary if "use_proxy" is True, otherwise None.

    Notes:
        - The proxies are loaded from `proxies.json` located in the `hexss_dir` directory.
    """
    try:
        proxies_config = json_load(os.path.join(hexss_dir, "proxies.json"), {
            "use_proxy": False,
            "proxies": {
                "http": "http://<user>:<pass>@150.61.8.70:10086",
                "https": "http://<user>:<pass>@150.61.8.70:10086"
            }
        }, True)
        if proxies_config.get('use_proxy', False):
            return proxies_config['proxies']
        return None

    except Exception as e:
        print(f"Error initializing proxies: {str(e)}")
        return None


# Initialize global variables
hostname = get_hostname()
username = get_username()
hexss_dir = get_hexss_dir()
proxies = initialize_proxies()
