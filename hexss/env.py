from typing import Optional
import os
import hexss


def set(var: str, value: str) -> None:
    """
    Set an environment variable.

    :param var: Name of the environment variable.
    :param value: Value to assign.
    """
    os.environ[var] = value


def unset(var: str) -> None:
    """
    Unset an environment variable.

    :param var: Name of the environment variable.
    """
    os.environ.pop(var, None)


def set_proxy() -> None:
    """
    Set HTTP and HTTPS proxy environment variables based on hexss.proxies.
    """
    if hexss.proxies:
        for proto in ['http', 'https']:
            proxy_url = hexss.proxies.get(proto)
            if proxy_url:
                set(f'{proto}_proxy', proxy_url)
                set(f'{proto.upper()}_PROXY', proxy_url)


def unset_proxy() -> None:
    """
    Unset all common HTTP/HTTPS proxy environment variables.
    """
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(var, None)


def generate_proxy_env_commands() -> Optional[str]:
    """
    Generates and prints commands to set and reset proxy environment variables
    for different operating systems (Windows and POSIX).
    """
    if hexss.proxies:
        print('# To SET proxy variables:')
        for proto, url in hexss.proxies.items():
            var = proto.upper() + '_PROXY'
            if hexss.system == 'Windows':
                # PowerShell syntax
                print(f'$env:{var} = "{url}"')
            else:
                # POSIX shells
                print(f"export {var}='{url}'")

        print('\n# To UNSET proxy variables:')
        if hexss.system == 'Windows':
            print('$env:HTTP_PROXY = $null')
            print('$env:HTTPS_PROXY = $null')
        else:
            print('unset HTTP_PROXY')
            print('unset HTTPS_PROXY')
    else:
        print("No proxies defined.")
