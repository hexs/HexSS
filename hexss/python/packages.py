import subprocess
import sys
from typing import List, Union
import hexss
from hexss.constants.terminal_color import *

# Map package aliases to actual package names for installation
PACKAGE_ALIASES = {
    'pygame-gui': 'pygame_gui'
}


def get_installed_packages() -> set:
    """
    Retrieves a set of installed Python packages using pip.

    Returns:
        set: A set of installed package names.
    """
    return {
        pkg.split('==')[0] for pkg in subprocess.check_output(
            [sys.executable, '-m', 'pip', 'freeze'], text=True
        ).splitlines()
    }


def flatten_packages(packages: Union[List[str], str], *args: str) -> List[str]:
    """
    Flattens arguments into a unified list of strings.

    Args:
        packages (Union[List[str], str]): A list of packages or a single package name.
        *args (str): Additional package names.

    Returns:
        List[str]: A combined flattened list of package names.
    """
    if not isinstance(packages, list):
        packages = [packages] if packages else []
    return packages + list(args)


def missing_packages(packages: Union[List[str], str], *args: str) -> List[str]:
    """
    Identifies missing packages from the list of required packages.

    Args:
        packages (List[str]): List of package names to check.
        *args (str): Additional package names to check.

    Returns:
        List[str]: List of missing packages.
    """
    installed = get_installed_packages()
    all_packages = flatten_packages(packages, *args)
    return [PACKAGE_ALIASES.get(pkg, pkg) for pkg in all_packages if PACKAGE_ALIASES.get(pkg, pkg) not in installed]


def generate_install_command(packages: List[str], upgrade: bool = False) -> List[str]:
    """
    Generates the pip install command.

    Args:
        packages (List[str]): List of packages to install.
        upgrade (bool, optional): Whether to include the --upgrade flag. Defaults to False.

    Returns:
        List[str]: The pip install command as a list of arguments.
    """
    command = [sys.executable, '-m', 'pip', 'install']
    if hexss.proxies:  # Add proxy if available
        command += [f"--proxy={hexss.proxies['http']}"]
    if upgrade:
        command.append("--upgrade")
    command += packages
    return command


def install(packages: Union[List[str], str], *args: str) -> None:
    """
    Installs missing packages.

    Args:
        packages (Union[List[str], str]): List of package names to install or a single package name.
        *args (str): Additional package names.

    Raises:
        RuntimeError: If the installation process fails.
    """
    missing = missing_packages(packages, *args)
    if not missing:
        print(f"{GREEN}All specified packages are already {BOLD}installed.{END}")
        return

    print(f"{PINK}Installing missing packages: {UNDERLINED}{' '.join(missing)}{END}")
    command = generate_install_command(missing)
    try:
        subprocess.run(command, check=True)  # Execute the installation command
        print(f"{GREEN}Missing packages {BOLD}installation complete.{END}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Failed to install packages. Error: {e}{END}")
        raise RuntimeError("Package installation failed.") from e


def install_upgrade(packages: Union[List[str], str], *args: str) -> None:
    """
    Installs or upgrades the specified packages.

    Args:
        packages (Union[List[str], str]): List of package names to install or upgrade.
        *args (str): Additional package names.

    Raises:
        RuntimeError: If the upgrading process fails.
    """
    # First, ensure pip is upgraded
    print(f"{PINK}Upgrading pip...{END}")
    pip_command = generate_install_command(['pip'], upgrade=True)
    subprocess.run(pip_command, check=True)

    all_packages = flatten_packages(packages, *args)
    print(f"{PINK}Installing or upgrading specified packages: {UNDERLINED}{' '.join(all_packages)}{END}")
    command = generate_install_command(all_packages, upgrade=True)
    try:
        subprocess.run(command, check=True)  # Execute the upgrade command
        print(f"{GREEN}Packages {BOLD}installation/upgrade complete.{END}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Failed to install/upgrade packages. Error: {e}{END}")
        raise RuntimeError("Package installation/upgrade failed.") from e


def check_packages(packages: Union[List[str], str], *args: str, auto_install: bool = False) -> None:
    """
    Checks if the required Python packages are installed, and optionally installs missing packages.

    Args:
        packages (Union[List[str], str]): List of package names to check or a single package name.
        *args (str): Additional package names.
        auto_install (bool, optional): Whether to install missing packages automatically. Defaults to False.

    Raises:
        ImportError: If some packages are missing and auto_install is False.
    """
    missing = missing_packages(packages, *args)
    if not missing:
        print(f"{GREEN}All specified packages are already installed.{END}")
        return

    if auto_install:
        print(f"{PINK}Missing packages detected. Attempting to install: {UNDERLINED}{' '.join(missing)}{END}")
        install(missing)
    else:
        raise ImportError(
            f"{RED.BOLD}The following packages are missing:{END.RED} "
            f"{ORANGE.UNDERLINED}{', '.join(missing)}{END}\n"
            f"{RED}Install them manually or set auto_install=True.{END}"
        )


if __name__ == "__main__":
    # Example usage

    # install('numpy', 'pandas')
    install_upgrade('setuptools')
    # check_packages('numpy', 'pandas', auto_install=True)
