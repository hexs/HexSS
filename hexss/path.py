import os
import sys
from typing import Optional


def get_script_directory() -> str:
    """
    Get the directory of the currently running script.

    Returns:
        str: The absolute path of the directory where the script is located.
    """
    try:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception as e:
        raise RuntimeError("Failed to retrieve the script directory.") from e


def get_working_directory() -> str:
    """
    Get the current working directory.

    Returns:
        str: The current working directory of the Python process.
    """
    try:
        return os.getcwd()
    except Exception as e:
        raise RuntimeError("Failed to retrieve the current working directory.") from e


def move_up(directory_path: str, levels: int = 1) -> Optional[str]:
    """
    Move up the directory tree by a specified number of levels.

    Args:
        directory_path (str): The directory path to start from.
        levels (int): The number of levels to move up. Defaults to 1.

    Returns:
        Optional[str]: The updated directory path after moving up. None if invalid.

    Raises:
        ValueError: If the levels argument is less than 1 or if the directory_path is invalid.
    """
    if levels < 1:
        raise ValueError("The levels argument must be at least 1.")

    try:
        new_path = directory_path
        for _ in range(levels):
            new_path = os.path.dirname(new_path)
            if not new_path:  # Root-level reached
                break
        return new_path
    except Exception as e:
        raise RuntimeError(f"Failed to move up {levels} levels from {directory_path}.") from e


def get_basename(directory_path: str) -> str:
    """
    Get the basename of a directory or file path.

    Args:
        directory_path (str): The input directory or file path.

    Returns:
        str: The basename component of the path.
    """
    try:
        return os.path.basename(directory_path)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve the basename from '{directory_path}'.") from e


def join_paths(*paths: str) -> str:
    """
    Join multiple path components into a single path.

    Args:
        *paths (str): Any number of path components to join.

    Returns:
        str: The joined path.
    """
    try:
        return os.path.join(*paths)
    except Exception as e:
        raise RuntimeError("Failed to join paths.") from e


if __name__ == "__main__":
    # Example Usage:
    print("Script Directory:", get_script_directory())
    print("Working Directory:", get_working_directory())
    print("Parent Directory:", move_up(get_working_directory(), 1))
    print("Basename:", get_basename(get_working_directory()))
    print("Joined Path:", join_paths(get_working_directory(), "example_folder", "example_file.txt"))
