import subprocess
from typing import Sequence, List
import re
from packaging.version import Version, InvalidVersion
from packaging.specifiers import SpecifierSet

import hexss
from hexss.constants.terminal_color import *
from hexss.path import get_python_path

# Map package aliases to actual package names for installation
PACKAGE_ALIASES = {
    # 'install_name': 'freeze_name'
    'pygame-gui': 'pygame_gui'
}


def get_installed_packages(python_path=get_python_path()) -> set[str]:
    """
    Retrieves a set of installed Python packages using pip.
    """
    output = subprocess.check_output([
        str(python_path), "-c",
        "import importlib.metadata\n"
        "for dist in importlib.metadata.distributions():\n"
        " print(dist.name,dist.version,sep='==')"
    ], text=True)

    # Split the output into lines
    lines = output.splitlines()

    # Parse the lines to extract package name and version
    packages = []
    for line in lines:
        if '==' in line:
            name, version = line.split('==')
        else:
            continue
        packages.append((name, version))

    return set(packages)


def missing_packages(*packages: str) -> List[str]:
    """
    Identifies missing packages from the list of required packages,
    including support for version specifiers.

    example:
    'package_name'
    'package_name==1.3'
    'package_name>=1.2,<2.0'
    """
    # Build a dictionary of installed packages: {package_name_lower: version}
    installed_dict = {name.lower(): version for name, version in get_installed_packages()}

    missing = []
    # Regex to capture package name and optional version specifier
    pattern = re.compile(r"^([A-Za-z0-9_\-]+)([<>=!].+)?$")

    for req in packages:
        # Check for alias mapping first.
        # We apply alias mapping to the requirement string if available, but only to the package name part.
        match = pattern.match(req)
        if not match:
            # if the requirement doesn't match our pattern, skip it.
            continue
        pkg_name, version_spec = match.groups()
        # Apply alias if exists (alias should not include version specifiers)
        actual_pkg = PACKAGE_ALIASES.get(pkg_name, pkg_name)
        actual_pkg_lower = actual_pkg.lower()

        # Get installed version if available
        installed_version = installed_dict.get(actual_pkg_lower)

        # If package is not installed, add to missing and continue.
        if installed_version is None:
            missing.append(req)
            continue

        # If a version specifier is provided, check if the installed version satisfies it.
        if version_spec:
            try:
                spec_set = SpecifierSet(version_spec)
                # Compare using packaging.version.Version
                if not spec_set.contains(Version(installed_version), prereleases=True):
                    missing.append(req)
            except InvalidVersion:
                # If version parsing fails, assume the package is missing or invalid.
                missing.append(req)
        # No version specifier provided and package is installed, so it's fine.
    return missing


def generate_install_command(
        packages: Sequence[str], upgrade: bool = False, proxy: str = None
) -> List[str]:
    """
    Generates the pip install command.
    """
    command = [str(get_python_path()), "-m", "pip", "install"]
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
    if verbose: print(f"{YELLOW}Installing: {BOLD}{', '.join(missing)}{END}")
    command = generate_install_command(missing)
    if run_command(command, verbose=verbose) == 0:
        if verbose: print(f"{GREEN.BOLD}{', '.join(packages)}{END} {GREEN}installation complete.{END}")
    else:
        print(f"{RED}Failed to install {BOLD}{', '.join(packages)}{END}. {RED}Check errors.{END}")


def install_upgrade(*packages: str, verbose: bool = True) -> None:
    """
    Installs or upgrades the specified packages.
    """
    # if verbose: print(f"{PINK}Upgrading pip...{END}")
    # pip_command = generate_install_command(["pip"], upgrade=True)
    # run_command(pip_command, verbose=verbose)
    if verbose: print(f"{YELLOW}Installing or upgrading: {BOLD}{' '.join(packages)}{END}")
    command = generate_install_command(packages, upgrade=True)
    if run_command(command, verbose=verbose) == 0:
        if verbose: print(f"{GREEN.BOLD}{', '.join(packages)}{END} {GREEN}installation/upgrade complete.{END}")
    else:
        print(f"{RED}Failed to install/upgrade {BOLD}{', '.join(packages)}{END}. {RED}Check errors.{END}")


def check_packages(*packages: str, auto_install: bool = False, verbose: bool = True) -> None:
    """
    Checks if the required Python packages are installed, and optionally installs missing packages.
    """
    missing = missing_packages(*packages)
    if not missing:
        # if verbose: print(f"{GREEN}All specified packages are already installed.{END}")
        return

    if auto_install:
        print(f"{PINK}Missing packages detected. Attempting to install: {BOLD}{', '.join(missing)}{END}")
        for package in missing:
            install(package, verbose=verbose)
        check_packages(*packages)
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
