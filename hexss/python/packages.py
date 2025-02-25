import subprocess
import sys
from typing import Sequence, List
import hexss
from hexss.constants.terminal_color import *

# Map package aliases to actual package names for installation
PACKAGE_ALIASES = {
    'pygame-gui': 'pygame_gui'
}


def get_installed_packages() -> set[str]:
    """
    Retrieves a set of installed Python packages using pip.
    """
    try:
        return {
            pkg.split('==')[0]
            for pkg in subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], text=True
            ).splitlines()
        }
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error fetching installed packages: {e}{END}")
        return set()


def missing_packages(*packages: str) -> List[str]:
    """
    Identifies missing packages from the list of required packages.
    """
    installed = get_installed_packages()
    return [PACKAGE_ALIASES.get(pkg, pkg) for pkg in packages if PACKAGE_ALIASES.get(pkg, pkg) not in installed]


def generate_install_command(
        packages: Sequence[str], upgrade: bool = False, proxy: str = None
) -> List[str]:
    """
    Generates the pip install command.
    """
    command = [sys.executable, "-m", "pip", "install"]
    if proxy or (hexss.proxies and hexss.proxies.get('http')):  # Add proxy if available
        command += [f"--proxy={proxy or hexss.proxies['http']}"]
    if upgrade:
        command.append("--upgrade")
    command.extend(packages)
    return command


def run_command(command: List[str], verbose: bool = False) -> int:
    """
    Executes a given command in a subprocess.
    """
    try:
        if verbose:
            print(f"{BLUE}Executing: {BOLD}{' '.join(command)}{END}")
            result = subprocess.run(command, check=True)
        else:
            result = subprocess.run(command, capture_output=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"{RED}Command failed with error: {e}{END}")
        return e.returncode


def install(*packages: str, verbose: bool = True) -> None:
    """
    Installs missing packages.
    """
    missing = missing_packages(*packages)
    if not missing:
        if verbose: print(f"{GREEN}All specified packages are already installed.{END}")
        return
    if verbose: print(f"{PINK}Installing missing packages: {UNDERLINED}{' '.join(missing)}{END}")
    command = generate_install_command(missing)
    if run_command(command, verbose=verbose) == 0:
        if verbose: print(f"{GREEN}Missing packages {BOLD}installation complete.{END}")
    else:
        print(f"{RED}Failed to install some packages. Check errors.{END}")


def install_upgrade(*packages: str, verbose: bool = True) -> None:
    """
    Installs or upgrades the specified packages.
    """
    # if verbose: print(f"{PINK}Upgrading pip...{END}")
    # pip_command = generate_install_command(["pip"], upgrade=True)
    # run_command(pip_command, verbose=verbose)
    if verbose: print(f"{PINK}Installing or upgrading specified packages: {UNDERLINED}{' '.join(packages)}{END}")
    command = generate_install_command(packages, upgrade=True)
    if run_command(command, verbose=verbose) == 0:
        if verbose: print(f"{GREEN}Packages {BOLD}installation/upgrade complete.{END}")
    else:
        print(f"{RED}Failed to install/upgrade some packages. Check errors.{END}")


def check_packages(*packages: str, auto_install: bool = False, verbose: bool = True) -> None:
    """
    Checks if the required Python packages are installed, and optionally installs missing packages.
    """
    missing = missing_packages(*packages)
    if not missing:
        if verbose: print(f"{GREEN}All specified packages are already installed.{END}")
        return

    if auto_install:
        print(f"{PINK}Missing packages detected. Attempting to install: {UNDERLINED}{' '.join(missing)}{END}")
        install(*missing, verbose=verbose)
    else:
        try:
            raise ImportError(
                f"{RED.BOLD}The following packages are missing:{END.RED} "
                f"{ORANGE.UNDERLINED}{', '.join(missing)}{END}\n"
                f"{RED}Install them manually or set auto_install=True.{END}"
            )
        except ImportError as e:
            print(e)
            exit()


if __name__ == "__main__":
    # Example
    install("numpy")
    install_upgrade("opencv-python", "Flask")
    check_packages("ultralytics")
