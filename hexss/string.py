import random
import unicodedata
import os
import re

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
    Sanitizes a filename for safe use in a filesystem.

    Args:
        filename (str): The original filename.

    Returns:
        str: A sanitized version of the filename.
    """
    if not isinstance(filename, str):
        raise TypeError("Filename must be a string.")

    # Normalize Unicode characters to ASCII equivalent
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

    # Handle Windows reserved device filenames
    if os.name == "nt" and filename.split(".")[0].upper() in _WINDOWS_DEVICE_FILES:
        filename = f"_{filename}"

    # Ensure filename is not empty after sanitization
    if not filename:
        raise ValueError("Invalid filename after sanitization.")

    return filename


def random_str(length=10, ignore_list=[]):
    string = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=length))
    if string in ignore_list:
        string = random_str(length, ignore_list)
    return string
