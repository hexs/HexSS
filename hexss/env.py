from typing import Optional
import os
import hexss
import winreg, ctypes


def set_persistent_env_var(name: str, value: str, scope: str = "user"):
    """
    name:    environment variable name (e.g. "HTTP_PROXY")
    value:   proxy URL with credentials
    scope:   "user" or "machine" (admin required for machine)
    """
    root = winreg.HKEY_LOCAL_MACHINE if scope == "machine" else winreg.HKEY_CURRENT_USER
    env_key = r"Environment"

    with winreg.OpenKey(root, env_key, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)

    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0,
        "Environment", SMTO_ABORTIFHUNG, 5000, None
    )


def unset_persistent_env_var(name: str, scope: str = "user"):
    set_persistent_env_var(name=name, value='', scope=scope)


def set(var: str, value: str, persistent: bool = False) -> None:
    """
    Set an environment variable.

    :param var: Name of the environment variable.
    :param value: Value to assign.
    """
    os.environ[var] = value
    if persistent:
        set_persistent_env_var(var, value)


def unset(var: str, persistent: bool = False) -> None:
    """
    Unset an environment variable.

    :param var: Name of the environment variable.
    """
    os.environ.pop(var, None)
    if persistent:
        unset_persistent_env_var(var)


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
