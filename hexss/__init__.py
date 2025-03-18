import os
import platform
from typing import Optional, Dict
from pathlib import Path
from .json import json_load, json_dump, json_update
from .network import open_url, get_ipv4, is_port_available, close_port
from .kill import kill
from .string import secure_filename, random_str
from .python import check_packages, install, install_upgrade
from .path import get_hexss_dir


def get_hostname() -> str:
    return platform.node()


def get_username() -> str:
    for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME'):
        user = os.environ.get(name)
        if user:
            return user
    raise ValueError('No username was specified')


def get_config(file_name):
    config_ = json_load(hexss_dir / '.config' / f'{file_name}.json', {})
    if file_name in config_:
        config = config_[file_name]
    else:
        config = config_

    return config


def initialize_proxies() -> Optional[Dict[str, str]]:
    """
    Initializes proxy configurations.

    This function loads proxy configuration data from a JSON file located in the
    designated directory. It parses the configuration file containing details
    about proxy settings and returns the dictionary containing the relevant
    proxy information. If an error occurs during initialization or loading of
    the configurations, it captures the exception and prints an error message.

    :raises Exception: If there is an error reading or parsing the proxy
        configuration file.

    :return: A dictionary containing the proxy settings for HTTP and HTTPS protocols,
        or None if the proxies configuration cannot be loaded.
    :rtype: Optional[Dict[str, str]]
    """
    try:
        proxies_config = json_load(hexss_dir / '.config' / 'proxies.json', {
            "proxies": None,
            "proxies_example": {
                "http": "http://<user>:<pass>@150.61.8.70:10086",
                "https": "http://<user>:<pass>@150.61.8.70:10086"
            }
        }, True)

        return proxies_config['proxies']

    except Exception as e:
        print(f"Error initializing proxies: {str(e)}")
        return None


__version__ = '0.14.8'
hostname = get_hostname()
username = get_username()
hexss_dir = get_hexss_dir()
proxies = initialize_proxies()
