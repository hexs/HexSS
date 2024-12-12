import os
import socket
from socket import AddressFamily
import subprocess
import platform

from hexss import json_dump
from hexss import json_load


def get_hostname() -> str:
    return socket.gethostname()


def get_username() -> str:
    return os.getlogin()


def get_ipv4() -> str:
    return socket.gethostbyname(socket.gethostname())


def get_ips():
    ipv4 = []
    ipv6 = []
    if platform.system() == "Windows":
        for item in socket.getaddrinfo(socket.gethostname(), None):
            protocol, *_, (ip, *_) = item
            if protocol == AddressFamily.AF_INET:
                ipv4.append(ip)
            elif protocol == AddressFamily.AF_INET6:
                ipv6.append(ip)

    elif platform.system() == "Linux":
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
    else:
        raise OSError("Unsupported operating system")

    return ipv4, ipv6


def get_all_ipv4() -> list:
    return get_ips()[0]


def open_url(url):
    """
    Open a URL in the default web browser.

    :param url: The URL to open
    :return: None

    Example: open_url("http://192.168.225.137:5555")
    """
    if platform.system() == "Windows":
        os.system(f'start "" {url}')
    else:
        raise OSError("Unsupported operating system")


def close_port_(ip, port):
    try:
        result = subprocess.run(
            f'''for /f "tokens=5" %a in ('netstat -ano ^| findstr {ip}:{port}') do taskkill /F /PID %a''',
            shell=True, capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error closing port: {e}")


def is_port_available(ip: str, port: int) -> bool:
    """
    Check if a specific port on a given IP address is available.

    :param ip: IP address as a string
    :param port: Port number as an integer
    :return: True if the port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)  # Set a 2-second timeout
            result = sock.connect_ex((ip, port))
            print(result)
            return result != 0
    except (OSError, ValueError):
        return False


def close_port(ip: str, port: int) -> None:
    """
    Close a specific TCP port on a given IP address.

    :param ip: IP address as a string
    :param port: Port number as an integer
    :return: None

    Example: close_tcp_port("192.168.225.137", 2002)
    """
    try:
        if not isinstance(port, int) or port < 0 or port > 65535:
            raise ValueError("Invalid port number")

        if platform.system() == "Windows":
            command = f'''powershell -Command "Get-NetTCPConnection -LocalAddress {ip} -LocalPort {port} | ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force }}"'''
        elif platform.system() in ["Linux", "Darwin"]:  # Linux or macOS
            command = f"lsof -ti tcp:{port} | xargs kill -9"
        else:
            raise OSError("Unsupported operating system")

        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        if result.returncode == 0:
            print(f"Successfully closed port {port} on {ip}")
        else:
            print(f"Failed to close port {port} on {ip}")
            print(f"Error: {result.stderr}")

    except Exception as e:
        print(f"Error closing port: {e}")


hostname = get_hostname()
username = get_username()
proxies = None

try:
    if platform.system() == "Windows":
        config_dir = f'C:/Users/{username}/AppData/Roaming/hexss'
    else:
        config_dir = f'/home/{username}/hexss'
    os.makedirs(config_dir, exist_ok=True)

    if 'proxies.json' in os.listdir(config_dir):
        proxies = json_load(os.path.join(config_dir, 'proxies.json'))
    else:
        json_dump(os.path.join(config_dir, 'no proxies.json'), {
            "http": "http://<user>:<pass>@150.61.8.70:10080",
            "https": "http://<user>:<pass>@150.61.8.70:10080"
        }, True)
except Exception as e:
    print(f"Error: proxies.json file in {config_dir}")
    print(e)
