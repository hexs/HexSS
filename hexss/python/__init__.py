import subprocess
import sys

import hexss.network
from hexss.constants.cml import *

pkg_name = {
    'pygame-gui': 'pygame_gui'
}


def check_packages(*args, install=False):
    text = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    installed_packages = {package.split('==')[0] for package in text.splitlines()}

    missing_packages = []
    for pkg in args:
        if pkg in pkg_name:
            pkg = pkg_name[pkg]
        if pkg not in installed_packages:
            missing_packages.append(pkg)

    if missing_packages:
        command = [sys.executable, '-m', 'pip', 'install']
        if hexss.network.proxies:
            command.append(f"--proxy {hexss.network.proxies['http']}")
        command.extend(missing_packages)

        if install:
            print(f"{PINK}Installing missing packages:{ENDC} {UNDERLINE}{' '.join(command)}{ENDC}")
            subprocess.run(f"{' '.join(command)}")
            check_packages(*args)

            raise Warning(f"{GREEN}Missing packages installation complete{ENDC}, {YELLOW}Run again!{ENDC}")
        else:
            raise ImportError(
                f"Missing packages; You can install them using `pip install {' '.join(command)}`")


if __name__ == "__main__":
    check_packages('numpy', 'pandas', 'matplotlib')

    # or

    # try:
    #     check_packages('numpy', 'pandas', 'matplotlib')
    # except subprocess.CalledProcessError as e:
    #     print(f"An error occurred while checking packages: {e}")
    # except ImportError as e:
    #     print(e)
