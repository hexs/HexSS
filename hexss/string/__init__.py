import os
import platform
import re
import secrets
import string
import unicodedata
from typing import Iterable, Optional

# Regular expression to strip unwanted characters
_FILENAME_ASCII_STRIP_RE = re.compile(r"[^A-Za-z0-9_.-]")

# Reserved filenames on Windows
_WINDOWS_DEVICE_FILES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_ALPHABET = string.ascii_letters + string.digits


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

    # Normalize Unicode characters (e.g., 'é' -> 'e')
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    # Replace path separators with spaces
    for sep in (os.sep, os.path.altsep):
        if sep:
            filename = filename.replace(sep, " ")

    # Remove unwanted characters and collapse whitespace
    filename = _FILENAME_ASCII_STRIP_RE.sub("", "_".join(filename.split()))

    # Strip leading/trailing dots and underscores
    filename = filename.strip("._")

    # Check for reserved Windows device names (if on Windows)
    if platform.system() == "Windows":
        if filename.split(".")[0].upper() in _WINDOWS_DEVICE_FILES:
            filename = f"_{filename}"

    # Ensure filename is not empty after sanitization
    if not filename:
        raise ValueError("Invalid filename after sanitization.")

    return filename


def random_str(length: int = 10, ignore_list: Optional[Iterable[str]] = None) -> str:
    """
    Generate a cryptographically-strong random alphanumeric string.

    Uses `secrets` so the result is safe to use as a token / session key.

    Args:
        length (int): The length of the random string. Defaults to 10.
        ignore_list (Optional[Iterable[str]]): Values to avoid duplicating.

    Returns:
        str: A randomly generated string.

    Raises:
        ValueError: If length is invalid.
        RuntimeError: If a unique string cannot be generated after max attempts.
    """
    if not isinstance(length, int) or length <= 0:
        raise ValueError("Length must be a positive integer.")

    ignore = set(ignore_list) if ignore_list else set()

    for _ in range(10):
        result = ''.join(secrets.choice(_ALPHABET) for _ in range(length))
        if result not in ignore:
            return result
    # Fallback: longer length to escape an unlikely collision streak.
    return random_str(length + 1, ignore)


if __name__ == "__main__":
    print(secure_filename('résumé.pdf'))
    print(random_str(10))
