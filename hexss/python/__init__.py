import subprocess
import sys
import os

import hexss
from hexss.constants.terminal_color import *

# Map package aliases to actual package names for installation
PACKAGE_ALIASES = {
    'pygame-gui': 'pygame_gui'
}


def check_packages(*packages, install=False):
    """
    Check if the required Python packages are installed, and optionally install missing packages.

    Args:
        *packages (str): The names of the packages to check.
        install (bool): Whether to install missing packages automatically (default: False).

    """
    if hexss.proxies:  # Add proxy if available
        os.environ['HTTP_PROXY'] = hexss.proxies["http"]
        os.environ['HTTPS_PROXY'] = hexss.proxies["https"]

    try:
        # Get a list of installed packages using pip
        installed_packages = {
            pkg.split('==')[0] for pkg in subprocess.check_output(
                [sys.executable, '-m', 'pip', 'freeze'], text=True
            ).splitlines()
        }

        # Check for missing packages
        missing_packages = [
            PACKAGE_ALIASES.get(pkg, pkg) for pkg in packages if PACKAGE_ALIASES.get(pkg, pkg) not in installed_packages
        ]

        if missing_packages:
            # Prepare the pip install command
            command = [sys.executable, '-m', 'pip', 'install']
            if hexss.proxies:  # Add proxy if available
                command += [f"--proxy {hexss.proxies['http']}"]
            if install in ['-U', '--upgrade']:
                command += ["--upgrade"]
            command += missing_packages

            if install:
                print(f"{PINK}Installing missing packages: {UNDERLINED}{' '.join(missing_packages)}{END}")
                subprocess.run(' '.join(command), check=True)  # Run the installation command
                check_packages(*packages)  # Recheck packages after installation

                print(Warning(f"{GREEN}Missing packages {BOLD}installation complete.{END}"))
            else:
                raise ImportError(
                    f"{RED.BOLD}Missing packages.{END.RED} Install them using:{END}\n"
                    f"{ORANGE.UNDERLINED}{' '.join(command)}{END}"
                )

    except Exception as e:
        print(e)
        exit()


if __name__ == "__main__":
    # Example usage of the function
    check_packages('numpy', 'pandas', 'matplotlib')
