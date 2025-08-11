import os
import hexss
import ctypes
import platform

if platform.system() == 'Windows':
    import winreg


def set_persistent_env_var(name: str, value: str, scope: str = "user") -> None:
    """
    :param name: Environment variable name (e.g. "HTTP_PROXY")
    :param value: Value to assign
    :param scope: "user" or "machine" ("machine" requires admin rights)
    """
    root = winreg.HKEY_LOCAL_MACHINE if scope == "machine" else winreg.HKEY_CURRENT_USER
    env_key = r"Environment"
    access = winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY

    try:
        with winreg.OpenKey(root, env_key, 0, access) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
    except PermissionError as e:
        raise PermissionError(f"Insufficient privileges to set {scope} environment variable '{name}'") from e

    # Notify system about environment change
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0,
        "Environment", SMTO_ABORTIFHUNG, 5000, None
    )


def unset_persistent_env_var(name: str, scope: str = "user") -> None:
    """
    :param name: Environment variable name
    :param scope: "user" or "machine"
    """
    root = winreg.HKEY_LOCAL_MACHINE if scope == "machine" else winreg.HKEY_CURRENT_USER
    env_key = r"Environment"
    access = winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY

    try:
        with winreg.OpenKey(root, env_key, 0, access) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        # Variable does not exist; nothing to delete
        pass
    except PermissionError as e:
        raise PermissionError(f"Insufficient privileges to unset {scope} environment variable '{name}'") from e

    # Notify system about environment change
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_SETTINGCHANGE, 0,
        "Environment", SMTO_ABORTIFHUNG, 5000, None
    )


def set(var: str, value: str, persistent: bool = False, scope: str = "user") -> None:
    """
    Set an environment variable.

    :param var: Variable name
    :param value: Variable value
    :param persistent: Whether to persist in Windows Registry
    :param scope: Scope for persistent env var ("user" or "machine")
    """
    os.environ[var] = value
    if platform.system() == 'Windows':
        if persistent:
            set_persistent_env_var(var, value, scope=scope)


def unset(var: str, persistent: bool = False, scope: str = "user") -> None:
    """
    Unset an environment variable.

    :param var: Variable name
    :param persistent: Whether to remove from Windows Registry
    :param scope: Scope for persistent env var ("user" or "machine")
    """
    os.environ.pop(var, None)
    if platform.system() == 'Windows':
        if persistent:
            unset_persistent_env_var(var, scope=scope)

def set_proxy(persistent: bool = False, scope: str = "user") -> None:
    """
    Set HTTP and HTTPS proxy environment variables based on hexss.proxies.

    :param persistent: Whether to persist environment variables
    :param scope: Scope for persistent env var ("user" or "machine")
    """
    if hexss.proxies:
        for proto in ['http', 'https']:
            proxy_url = hexss.proxies.get(proto)
            if proxy_url:
                set(f'{proto}_proxy', proxy_url, persistent=persistent, scope=scope)
                set(f'{proto.upper()}_PROXY', proxy_url, persistent=persistent, scope=scope)


def unset_proxy(persistent: bool = False, scope: str = "user") -> None:
    """
    Unset all common HTTP/HTTPS proxy environment variables.

    :param persistent: Whether to remove from Windows Registry
    :param scope: Scope for persistent env var ("user" or "machine")
    """
    for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(var, None)
        if persistent:
            unset_persistent_env_var(var, scope=scope)
