import sys
import os
import ctypes


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> None:
    if is_admin():
        return

    # Build args: "python" "<script>" "<args...>" "--elevated"
    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{script}"', *[f'"{a}"' for a in sys.argv[1:]], "--elevated"])

    # Trigger UAC elevation
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if rc <= 32:
        raise RuntimeError(f"Elevation failed (ShellExecuteW rc={rc}).")

    # Important: stop the non-admin parent so you don't see its prints
    sys.exit(0)


if __name__ == "__main__":
    import hexss.server.file_manager_server

    print("is_admin (before):", is_admin())
    relaunch_as_admin()  # will exit here if not admin

    # Only runs in the elevated child:
    print("is_admin (after):", is_admin())
    print("Running with administrator privileges.")
    hexss.server.file_manager_server.run()
