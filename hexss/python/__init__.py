import subprocess
import sys

import hexss.network
from hexss.constants.cml import *

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

    Raises:
        ImportError: If required packages are missing and `install` is False.
        Warning: If missing packages were successfully installed, prompting user to re-run the script.
    """
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
            if hexss.network.proxies:  # Add proxy if available
                command += [f"--proxy={hexss.network.proxies['http']}"]
            command += missing_packages

            if install:
                print(f"{PINK}Installing missing packages:{ENDC} {UNDERLINE}{' '.join(missing_packages)}{ENDC}")
                subprocess.run(command, check=True)  # Run the installation command
                check_packages(*packages)  # Recheck packages after installation

                raise Warning(f"{GREEN}Missing packages installation complete.{ENDC} {YELLOW}Please run again!{ENDC}")
            else:
                raise ImportError(
                    f"Missing packages. Install them using: `pip install {' '.join(missing_packages)}`"
                )

    except subprocess.CalledProcessError as e:
        print(f"Error during package check or installation: {e}")
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")


if __name__ == "__main__":
    # Example usage of the function
    check_packages('numpy', 'pandas', 'matplotlib')

    # or

    try:
        check_packages('numpy', 'pandas', 'matplotlib')
    except ImportError as e:
        print(e)
    except Warning as w:
        print(w)
