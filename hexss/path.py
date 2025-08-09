import os
import re
import subprocess
import sys
import platform
import ctypes
from pathlib import Path
from typing import Optional, Union

import hexss


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


def get_main_python_path() -> Path:
    """
    Returns the path to the main Python executable.

    This function returns the path to the main Python interpreter executable
    that is running the current script. It is useful in cases where the path
    to the main Python executable is needed, regardless of whether a virtual
    environment is active or not.

    Returns:
        Path: The main Python executable path.
    """
    if hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix:
        # If in a virtual environment, return the base prefix executable
        if platform.system() == 'Windows':
            return Path(sys.base_prefix) / "python.exe"
        else:
            return Path(sys.base_prefix) / "bin" / "python"
    else:
        # If not in a virtual environment, return the current executable
        return Path(sys.executable)


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


def shorten(
        path: Union[Path, str],
        num_leading: int = 3,
        num_trailing: int = 4,
        sep: str = ' ... '
) -> str:
    """
    Shortens a path by keeping the first `num_leading` and last `num_trailing` parts

    Args:
        path: The path to shorten. Can be a Path object or a string.
        num_leading: Number of leading path components to keep.
        num_trailing: Number of trailing path components to keep.
        sep: Separator string to use in place of omitted parts.

    Returns:
        A string representing the shortened path.
    """
    path = Path(path)
    parts = path.parts

    # If not enough parts to shorten, return the original path as string
    if len(parts) <= num_leading + num_trailing:
        return str(path)

    # Leading
    leading = Path(*parts[:num_leading])
    # Trailing
    trailing = Path(*parts[-num_trailing:])

    # Special handling for Windows drive/root
    if leading.drive:
        if num_leading == 1:
            leading_str = leading.drive + leading.root
        else:
            leading_str = leading.drive + leading.root + str(Path(*parts[1:num_leading]))
    else:
        leading_str = str(leading)

    leading_str = leading_str.rstrip("\\/")

    # Compose result
    return f"{leading_str}{sep}{trailing}"


def list_drives():
    system = platform.system()
    if system == 'Windows':
        _DRIVE_TYPES = {
            0: "Unknown",
            1: "No Root Directory",
            2: "Removable",
            3: "Fixed",
            4: "Network",
            5: "CD/DVD",
            6: "RAM Disk"
        }
        drives = []
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            if mask & (1 << i):
                path = f"{letter}:\\"
                dtype = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path))
                drives.append({"path": path, "type": _DRIVE_TYPES.get(dtype, "Unknown")})
        return drives
    elif system == 'Linux':
        ...


def list_network_shares(server: str):
    """Return a list of shared resources from a Windows SMB server using `net view`."""
    result = subprocess.run(
        ['net', 'view', server],
        capture_output=True,
        text=True,
        shell=True
    )

    lines = result.stdout.splitlines()

    # Find header line
    header_index = None
    for i, line in enumerate(lines):
        if re.search(r'Share name', line, re.IGNORECASE):
            header_index = i
            break

    if header_index is None:
        return []

    header_line = lines[header_index]
    dash_index = None
    for i in range(header_index, len(lines)):
        if re.match(r'-+', lines[i]):
            dash_index = i
            break

    if dash_index is None:
        return []

    # Detect column positions dynamically
    columns = re.findall(r'\S+(?: \S+)*', header_line)
    col_positions = []
    last_pos = 0
    for col in columns:
        pos = header_line.index(col, last_pos)
        col_positions.append((col.strip(), pos))
        last_pos = pos + len(col)
    col_positions.append(('__END__', None))  # End position marker

    # Parse rows into dictionaries
    shares = []
    for line in lines[dash_index + 1:]:
        if not line.strip() or "The command completed successfully" in line:
            continue
        row = {}
        for j in range(len(col_positions) - 1):
            col_name, start = col_positions[j]
            _, next_start = col_positions[j + 1]
            value = line[start:next_start].strip() if next_start is not None else line[start:].strip()
            row[col_name] = value
        shares.append(row)

    return shares


def iterdir(p: Path):
    """
    Extended iterdir:
    - Local paths: behaves like Path.iterdir()
    - UNC server paths (\\server): returns available shares as Path objects
    """
    # Normal local path or full UNC path to a share
    if p.exists():
        return p.iterdir()

    # Detect UNC server root (\\server with no share name)
    if str(p).startswith('\\\\'):
        shares = list_network_shares(str(p))
        return [Path(str(p) + '\\' + share['Share name']) for share in shares]

    # Path does not exist
    return []


def last_component(p: Path) -> str:
    if p.name:
        return p.name
    if p.drive and not p.root:  # UNC host root, e.g. //it
        return p.drive
    if p.drive and p.root:
        # print(type(p.drive)) <class 'str'>
        if p.drive.startswith('\\\\'):  # UNC share root, e.g. //it/a
            # Split UNC into //server/share and take the share
            return f'{p.drive}'.split('\\')[-1]
        return p.drive + p.root  # Drive root like C:/
    return str(p)

    # UNC host root
    print(last_component(Path(r'//it')))  # \\it

    # UNC share root
    print(last_component(Path(r'//it/a')))  # a

    # Local drive
    print(last_component(Path(r'C:/')))  # C:\
    print(last_component(Path(r'C:/b')))  # b


if __name__ == "__main__":
    main_python_path = get_main_python_path()
    python_path = get_python_path()
    print("Main Python Exec Path       :", main_python_path)
    print("Python Exec Path            :", python_path)

    # Script and working directory paths
    script_directory = get_script_dir()
    working_directory = get_current_working_dir()
    print("Script Directory            :", script_directory)
    print("Working Directory           :", working_directory)

    # Example: Ascend 2 levels from the working directory
    ascended_path = ascend_path(working_directory, 2)
    print("Ascended Path (2 levels up) :", ascended_path)

    print(sys.base_prefix)

    path = Path(r'C:\Users\<user>\Desktop\folder\img_frame\ok\241209.png')
    print(shorten(path))  # C:\Users\<user> ... folder\img_frame\ok\241209.png
    print(shorten(path, 2, 3))  # C:\Users ... img_frame\ok\241209.png

    for entry in list_drives():
        print(f"{entry['path']} → {entry['type']}")
        for p in Path(entry['path']).iterdir():
            print(p)

    paths = [
        Path(r'\\it-dv-sv'),  # UNC host root
        Path(r'\\it-dv-sv\a'),  # UNC share root
        Path(r'C:\\'),  # Local drive
    ]

    for path in paths:
        print(f"\nListing: {path}")
        for d in iterdir(path):
            print(f"  {d}  [DIR={d.is_dir()}]  [FILE={d.is_file()}]")
            if d.is_dir():
                try:
                    children = [p.name for p in d.iterdir()]
                    print(f"    -> {children}")
                except PermissionError:
                    print("    -> [Permission Denied]")
                except OSError as e:
                    print(f"    -> [Error: {e}]")

