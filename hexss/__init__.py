import os
import platform
from .json import json_load, json_dump, json_update
from .network import open_url, get_ipv4, is_port_available, close_port
from .kill import kill
from .string import secure_filename, random_str
from .python import check_packages, install, install_upgrade
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


__version__ = '0.24.0'
hostname = get_hostname()
username = get_username()
hexss_dir = get_hexss_dir()
proxies = get_config('proxies')
system = platform.system()
python_version = platform.python_version()
