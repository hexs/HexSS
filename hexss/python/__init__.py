import os
import hexss

from .packages import check_packages, install, install_upgrade


def write_proxy_to_env():
    if hexss.proxies:  # Add proxy if available
        if hexss.proxies.get("http"):
            os.environ['HTTP_PROXY'] = hexss.proxies["http"]
        if hexss.proxies.get("https"):
            os.environ['HTTPS_PROXY'] = hexss.proxies["https"]
