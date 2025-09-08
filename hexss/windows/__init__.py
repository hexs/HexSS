import platform

if platform.system() == "Windows":
    from .admin import is_admin, relaunch_as_admin
    from .wifi import set_wifi, connect_wifi
    from .hotspot import set_hotspot
