import os
import sys
from typing import Optional
from pathlib import Path
import platform


def get_virtualenv_path() -> Optional[Path]:
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


def get_virtualenv_python_path() -> Path:
    """
    Returns the path to the Python executable in the active virtual environment.

    If a virtual environment is detected, constructs the path based on the operating
    system (using 'Scripts' on Windows and 'bin' on other systems). If the expected
    executable does not exist or no virtual environment is active, returns sys.executable
    as a Path object.

    Returns:
        Path: The path to the Python executable.
    """
    venv_path = get_virtualenv_path()
    if not venv_path:
        return Path(sys.executable)

    if platform.system() == 'Windows':
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"

    if python_path.exists():
        return python_path
    return Path(sys.executable)


def get_script_directory() -> Path:
    """
    Get the directory of the currently running script.

    Returns:
        Path: The absolute path of the directory where the script is located.
    """
    try:
        # Resolve the absolute path of the script and return its parent directory.
        return Path(sys.argv[0]).resolve().parent
    except Exception as e:
        raise RuntimeError("Failed to retrieve the script directory.") from e


def get_working_directory() -> Path:
    """
    Get the current working directory.

    Returns:
        Path: The current working directory of the Python process.
    """
    try:
        return Path.cwd()
    except Exception as e:
        raise RuntimeError("Failed to retrieve the current working directory.") from e


def move_up(directory_path: Path, levels: int = 1) -> Path:
    """
    Move up the directory tree by a specified number of levels.

    Args:
        directory_path (Path): The starting directory path.
        levels (int): The number of levels to move up. Defaults to 1.

    Returns:
        Path: The updated directory path after moving up.

    Raises:
        ValueError: If levels is less than 1.
    """
    if levels < 1:
        raise ValueError("The levels argument must be at least 1.")

    new_path = directory_path
    for _ in range(levels):
        new_path = new_path.parent
    return new_path


def get_basename(directory_path: Path) -> str:
    """
    Get the basename of a directory or file path.

    Args:
        directory_path (Path): The input directory or file path.

    Returns:
        str: The final component (basename) of the path.
    """
    try:
        return directory_path.name
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve the basename from '{directory_path}'.") from e


if __name__ == "__main__":
    # Virtual environment related paths
    venv_path = get_virtualenv_path()
    python_path = get_virtualenv_python_path()
    print("Virtual Environment Path         :", venv_path)
    print("Python Executable Path           :", python_path)

    # Script and working directory paths
    script_dir = get_script_directory()
    work_dir = get_working_directory()
    print("Script Directory                 :", script_dir)
    print("Working Directory                :", work_dir)
    print("Basename of Working Dir          :", get_basename(work_dir))

    # Example: Move up 2 levels from the working directory
    print("Working Directory - 2 levels up  :", move_up(work_dir, 2))
