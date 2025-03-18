import os
import sys
import platform
from pathlib import Path
from typing import Optional


def get_venv_dir() -> Optional[Path]:
    """
    Returns the path of the current virtual environment if active.

    Checks the VIRTUAL_ENV environment variable first.
    If not set, falls back to comparing sys.prefix and sys.base_prefix
    (or using sys.real_prefix for legacy virtual environments).

    Returns:
        Optional[Path]: The virtual environment path as a Path object, or None if not detected.
    """
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        return Path(venv)
    if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix:
        return Path(sys.prefix)
    return None


def get_python_path() -> Path:
    """
    Returns the path to the Python executable in the active virtual environment.

    If a virtual environment is active, constructs the executable path based on the OS:
    - Windows: 'Scripts/python.exe'
    - Unix-like: 'bin/python'

    If no virtual environment is detected or the expected executable does not exist,
    returns the current sys.executable as a Path object.

    Returns:
        Path: The Python executable path.
    """
    venv_dir = get_venv_dir()
    if not venv_dir:
        return Path(sys.executable)

    if platform.system() == 'Windows':
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        python_path = venv_dir / "bin" / "python"

    if python_path.exists():
        return python_path
    return Path(sys.executable)


def get_script_dir() -> Path:
    """
    Returns the directory where the current script is located.

    Returns:
        Path: The absolute directory path of the running script.
    """
    try:
        # Resolve the absolute path of the script and return its parent directory.
        return Path(sys.argv[0]).resolve().parent
    except Exception as e:
        raise RuntimeError("Unable to determine the script directory.") from e


def get_current_working_dir() -> Path:
    """
    Returns the current working directory.

    Returns:
        Path: The current working directory.
    """
    try:
        return Path.cwd()
    except Exception as e:
        raise RuntimeError("Unable to retrieve the current working directory.") from e


def ascend_path(path: Path, levels: int = 1) -> Path:
    """
    Ascends the directory tree from a given path by a specified number of levels.

    Args:
        path (Path): The starting path.
        levels (int): The number of levels to ascend. Must be at least 1.

    Returns:
        Path: The resulting path after ascending the specified number of levels.

    Raises:
        ValueError: If levels is less than 1.
    """
    if levels < 1:
        raise ValueError("The levels argument must be at least 1.")

    new_path = path
    for _ in range(levels):
        new_path = new_path.parent
    return new_path


def get_hexss_dir():
    home_dir = Path.home()
    if platform.system() == "Windows":
        hexss_dir = home_dir / 'AppData' / 'Roaming' / 'hexss'
    else:
        hexss_dir = home_dir / '.config' / 'hexss'
    hexss_dir.mkdir(parents=True, exist_ok=True)
    return hexss_dir


if __name__ == "__main__":
    python_path = get_python_path()
    print("Python Exec Path            :", python_path)

    # Script and working directory paths
    script_directory = get_script_dir()
    working_directory = get_current_working_dir()
    print("Script Directory            :", script_directory)
    print("Working Directory           :", working_directory)

    # Example: Ascend 2 levels from the working directory
    ascended_path = ascend_path(working_directory, 2)
    print("Ascended Path (2 levels up) :", ascended_path)
