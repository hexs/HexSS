import subprocess
from typing import Sequence, List, Set, Tuple
from packaging.version import Version, InvalidVersion
from packaging.requirements import Requirement

import hexss
from hexss.constants.terminal_color import *
from hexss.path import get_python_path

# Map package aliases to actual package names for installation
PACKAGE_ALIASES = {
    # 'install_name': 'freeze_name'
    'pygame-gui': 'pygame_gui'
}


def get_installed_packages(python_path=get_python_path()) -> Set[Tuple[str, str]]:
    """
    Retrieves a set of installed Python packages (name and version tuples)
    using pip and importlib.metadata.
    """
    output = subprocess.check_output([
        str(python_path), "-c",
        "import importlib.metadata\n"
        "for dist in importlib.metadata.distributions():\n"
        " print(dist.name, dist.version, sep='==')"
    ], text=True)

    packages: List[Tuple[str, str]] = []
    for line in output.splitlines():
        if '==' in line:
            name, version = line.split('==')
            packages.append((name.strip(), version.strip()))
    return set(packages)


def missing_packages(*packages: str) -> List[str]:
    """
    Identifies missing packages from the list of required packages,
    including support for version specifiers.

    Requirements are parsed using packaging.requirements.Requirement.

    Examples:
        missing_packages('numpy', 'opencv-python')
        missing_packages('numpy==2', 'opencv-python')
        missing_packages('numpy==2.0.0', 'opencv-python')
        missing_packages('numpy>=2.0.0', 'opencv-python')
    """
    # Build a dictionary of installed packages: {package_name_lower: version}
    installed_dict = {name.lower(): version for name, version in get_installed_packages()}

    missing = []
    for req in packages:
        try:
            # Parse requirement string using packaging.requirements.Requirement
            requirement = Requirement(req)
        except Exception:
            # If the requirement cannot be parsed, assume it's missing.
            missing.append(req)
            continue

        pkg_name = requirement.name
        specifier = requirement.specifier
        # Apply alias mapping if needed
        actual_pkg = PACKAGE_ALIASES.get(pkg_name, pkg_name)
        actual_pkg_lower = actual_pkg.lower()

        installed_version = installed_dict.get(actual_pkg_lower)
        # Package is not installed
        if installed_version is None:
            missing.append(req)
            continue

        # If there is a version specifier, check whether the installed version meets the requirement.
        if specifier:
            try:
                if not specifier.contains(Version(installed_version), prereleases=True):
                    missing.append(req)
            except InvalidVersion:
                # If the installed version cannot be parsed, consider the package as missing.
                missing.append(req)
    return missing


def generate_install_command(
        packages: Sequence[str], upgrade: bool = False, proxy: str = None
) -> List[str]:
    """
    Generates the pip install command based on the specified packages.
    """
    command = [str(get_python_path()), "-m", "pip", "install"]
    if proxy or (hexss.proxies and hexss.proxies.get('http')):  # Add proxy if available
        command.append(f"--proxy={proxy or hexss.proxies['http']}")
    if upgrade:
        command.append("--upgrade")
    command.extend(packages)
    return command


def run_command(command: List[str], verbose: bool = False) -> int:
    """
    Executes a given command in a subprocess and returns the exit code.
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
    Checks if the required Python packages are installed (and meet any version constraints).
    Optionally, installs missing packages automatically if auto_install is set to True.
    """
    missing = missing_packages(*packages)
    if not missing:
        # if verbose: print(f"{GREEN}All specified packages are already installed.{END}")
        return

    if auto_install:
        print(f"{PINK}Missing packages detected. Attempting to install: {BOLD}{', '.join(missing)}{END}")
        for package in missing:
            install(package, verbose=verbose)
        # Recursively check packages again
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
