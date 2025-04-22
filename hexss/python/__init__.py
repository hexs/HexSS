import os
import hexss

from .packages import check_packages, install, install_upgrade


def set_proxy_env():
    if hexss.proxies:
        for proto in ['http', 'https']:
            proxy_url = hexss.proxies.get(proto)
            if proxy_url:
                # Set both lowercase and uppercase environment variables
                os.environ[proto + '_proxy'] = proxy_url
                os.environ[proto.upper() + '_PROXY'] = proxy_url


def write_proxy_to_env():
    set_proxy_env()


def generate_proxy_env_commands():
    if hexss.proxies:
        for proto, url in hexss.proxies.items():
            var = proto.upper() + '_PROXY'
            if hexss.system == 'Windows':
                # PowerShell: set in current session
                print(f'$env:{var} = "{url}"')
            else:
                # POSIX shells
                print(f"export {var}='{url}'")
    else:
        print("No proxies defined.")
