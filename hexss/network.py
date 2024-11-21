import os
import socket
from socket import AddressFamily
import subprocess
import platform
import webbrowser


def get_hostname() -> str:
    return socket.gethostname()


def get_ipv4() -> str:
    return socket.gethostbyname(socket.gethostname())


def get_ips():
    ipv4 = []
    ipv6 = []
    for item in socket.getaddrinfo(socket.gethostname(), None):
        protocol, *_, (ip, *_) = item
        if protocol == AddressFamily.AF_INET:
            ipv4.append(ip)
        elif protocol == AddressFamily.AF_INET6:
            ipv6.append(ip)

    return ipv4, ipv6


def get_all_ipv4() -> list:
    return get_ips()[0]


def open_url_(url):
    os.system(f'start "" {url}')


def open_url(url):
    """
    Open a URL in the default web browser.

    :param url: The URL to open
    :return: None

    Example: open_url("http://192.168.225.137:5555")
    """
    try:
        webbrowser.open(url, new=2)  # new=2 opens in a new tab, if possible
    except Exception as e:
        print(f"Error opening URL: {e}")


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
