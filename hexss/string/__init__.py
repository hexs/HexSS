import random
import unicodedata
import os
import re
from typing import List

# Regular expression to strip unwanted characters
_FILENAME_ASCII_STRIP_RE = re.compile(r"[^A-Za-z0-9_.-]")
# Reserved filenames on Windows
_WINDOWS_DEVICE_FILES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def secure_filename(filename: str) -> str:
    """
    Sanitize a filename to make it safe for use in a filesystem.

    Args:
        filename (str): The original filename.

    Returns:
        str: A sanitized version of the filename.

    Raises:
        TypeError: If the filename is not a string.
        ValueError: If the filename is empty after sanitization.
    """
    if not isinstance(filename, str):
        raise TypeError("Filename must be a string.")

    # Normalize Unicode characters to their ASCII equivalent
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # Replace path separators with spaces
    for sep in (os.sep, os.path.altsep):
        if sep:
            filename = filename.replace(sep, " ")

    # Remove unwanted characters using regex and collapse whitespace
    filename = _FILENAME_ASCII_STRIP_RE.sub("", "_".join(filename.split()))

    # Strip leading/trailing dots and underscores
    filename = filename.strip("._")

    # Check for reserved Windows device names (if on Windows)
    if os.name == "nt" and filename.split(".")[0].upper() in _WINDOWS_DEVICE_FILES:
        filename = f"_{filename}"

    # Ensure filename is not empty after sanitization
    if not filename:
        raise ValueError("Invalid filename after sanitization.")

    return filename


def random_str(length: int = 10, ignore_list: List[str] = None) -> str:
    """
    Generate a random alphanumeric string of a specified length.

    Args:
        length (int): The length of the random string. Defaults to 10.
        ignore_list (List[str]): A list of strings to avoid duplication. Defaults to None.

    Returns:
        str: A randomly generated string.
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("Length must be a positive integer.")

    if ignore_list is None:
        ignore_list = []

    for _ in range(10):
        result = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=length))
        if result not in ignore_list:
            return result
    else:
        return random_str(length + 1, ignore_list)
