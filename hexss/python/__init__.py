import os
import hexss

from .packages import check_packages, install, install_upgrade


def set_proxy_env():
    """
    Sets the HTTP and HTTPS proxy environment variables
    based on the proxies defined in hexss.proxies.
    """
    if hexss.proxies:
        for proto in ['http', 'https']:
            proxy_url = hexss.proxies.get(proto)
            if proxy_url:
                # Set both lowercase and uppercase environment variables
                os.environ[f'{proto}_proxy'] = proxy_url
                os.environ[f'{proto.upper()}_PROXY'] = proxy_url
    else:
        print("No proxies defined in hexss.proxies.")


def reset_proxy_env():
    """
    Resets (removes) the HTTP and HTTPS proxy environment variables.
    """
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(var, None)


def write_proxy_to_env():
    set_proxy_env()


def generate_proxy_env_commands():
    """
    Generates and prints commands to set and reset proxy environment variables
    for different operating systems (Windows and POSIX).
    """
    if hexss.proxies:
        print('Use the following commands to set proxy environment variables:')
        for proto, url in hexss.proxies.items():
            var = proto.upper() + '_PROXY'
            if hexss.system == 'Windows':
                # PowerShell: set in current session
                print(f'$env:{var} = "{url}"')
            else:
                # POSIX shells
                print(f"export {var}='{url}'")

        print('\nAnd use the following commands to reset proxy environment variables:')
        if hexss.system == 'Windows':
            print('$env:HTTP_PROXY = $null')
            print('$env:HTTPS_PROXY = $null')
        else:
            print('unset HTTP_PROXY')
            print('unset HTTPS_PROXY')
    else:
        print("No proxies defined.")
