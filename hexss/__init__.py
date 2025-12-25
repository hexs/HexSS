import os
import platform
import sys
from .json import json_load, json_dump, json_update
from .network import open_url, get_ipv4, is_port_available, close_port
from .kill import kill
from .string import secure_filename, random_str
from .python import check_packages, install, upgrade
from .path import get_hexss_dir
from . import env
from .pyconfig import Config


def get_hostname() -> str:
    return platform.node()


def get_username() -> str:
    for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME'):
        user = os.environ.get(name)
        if user:
            return user
    import pwd
    return pwd.getpwuid(os.getuid())[0]


def get_config(file_name):
    config_ = json_load(hexss_dir / 'config' / f'{file_name}.json', {})
    if file_name in config_:
        config = config_[file_name]
    else:
        config = config_

    return config


__version__ = '0.29.3'
hostname = get_hostname()
username = get_username()
hexss_dir = get_hexss_dir()
proxies = get_config('proxies')
system = platform.system()  # Get the system name (e.g., 'Linux', 'Windows', 'Darwin' for macOS)
python_version = platform.python_version()
is_64bits = sys.maxsize > 2 ** 32
machine = platform.machine()  # Get the machine type (e.g., 'x86_64', 'AMD64', 'arm64')
processor = platform.processor()  # Get the processor information (e.g., 'x86_64', 'arm')
architecture: tuple[str, str] = platform.architecture()  # (bits, linkage)
# bits: This string indicates the bit architecture of the executable, such as '32bit' or '64bit'.
# linkage: This string describes the linkage format used, for example, 'ELF' on Linux, 'WindowsPE' on Windows.
# (e.g., ('64bit', 'WindowsPE'), ('64bit', 'ELF'))
