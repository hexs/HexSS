import subprocess
import sys

pkg_name = {
    'pygame-gui': 'pygame_gui'
}


def check_packages(*args):
    text = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
    installed_packages = {package.split('==')[0] for package in text.splitlines()}

    missing_packages = []
    for pkg in args:
        if pkg in pkg_name:
            pkg = pkg_name[pkg]
        if pkg not in installed_packages:
            missing_packages.append(pkg)

    if missing_packages:
        raise ImportError(f"Missing packages; You can install them using `pip install {' '.join(missing_packages)}`")


if __name__ == "__main__":
    check_packages('numpy', 'pandas', 'matplotlib')

    # or

    # try:
    #     check_packages('numpy', 'pandas', 'matplotlib')
    # except subprocess.CalledProcessError as e:
    #     print(f"An error occurred while checking packages: {e}")
    # except ImportError as e:
    #     print(e)
