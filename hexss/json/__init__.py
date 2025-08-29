import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, Mapping


def _ensure_json_object(obj: Any, where: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"JSON content in {where} is not a JSON object (expected dict).")
    return obj


def json_load(
        file_path: Union[str, Path],
        default: Optional[Mapping[str, Any]] = None,
        dump: bool = False
) -> Dict[str, Any]:
    """
    Load JSON data from a file. If the file does not exist or contains invalid/empty JSON,
    return a copy of `default` (or {}) and optionally write it to disk when `dump=True`.
    """
    path = Path(file_path)
    if path.suffix.lower() != '.json':
        raise ValueError("File extension must be .json")

    if default is not None and not isinstance(default, Mapping):
        raise ValueError("`default` must be a mapping (dict-like) if provided.")

    data: Dict[str, Any] = dict(default or {})

    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                content = f.read()
                if content.strip() == "":
                    loaded = {}
                else:
                    loaded = json.loads(content)
            _ensure_json_object(loaded, str(file_path))
            data.update(loaded)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos
            ) from e

    if dump:
        json_dump(path, data)

    return data


def json_dump(
        file_path: Union[str, Path],
        data: Mapping[str, Any],
        indent: int = 4
) -> Dict[str, Any]:
    """
    Write JSON data to a file (atomically).
    """
    path = Path(file_path)
    if path.suffix.lower() != ".json":
        raise ValueError("File extension must be .json")

    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
        tmp.replace(path)  # atomic on POSIX/NTFS
    except OSError as e:
        # Best effort cleanup
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise OSError(f"Error writing to {file_path}: {e.strerror}") from e

    # Return a plain dict (not just Mapping)
    return dict(data)


def _deep_update_path(d: Dict[str, Any], keys: list, value: Any) -> None:
    cur = d
    for key in keys[:-1]:
        if key not in cur or not isinstance(cur[key], dict):
            cur[key] = {}
        cur = cur[key]
    cur[keys[-1]] = value


def json_update(
        file_path: Union[str, Path],
        new_data: Mapping[str, Any],
        deep: Union[bool, str, None] = False,
        *,
        sep: str = ".",
        indent: int = 4
) -> Dict[str, Any]:
    """
    Update an existing JSON file with new data.

    Deep update options:
      - deep=False (default): shallow `dict.update`
      - deep=True: treat string keys containing `sep` (default ".") as paths (e.g. "a.b.c")
      - deep='<custom separator>': use that separator (e.g. "/" -> "a/b/c")

    Notes:
      - For deep updates, keys without the separator are assigned directly (no merge).
      - If the existing file contains non-dict JSON, this raises.
    """
    path = Path(file_path)
    if path.suffix.lower() != ".json":
        raise ValueError("File extension must be .json")

    # Load current data ({} if not present/empty)
    data = json_load(path, default={})

    # Validate existing json is a dict (json_load already guarantees)
    _ensure_json_object(data, str(file_path))

    # Decide separator behavior
    if isinstance(deep, str):
        active_sep = deep
        use_deep = True
    elif deep is True:
        active_sep = sep
        use_deep = True
    else:
        active_sep = None
        use_deep = False

    # Apply updates
    if use_deep:
        for k, v in new_data.items():
            if isinstance(k, str) and active_sep and active_sep in k:
                keys = [p for p in k.split(active_sep) if p != ""]
                if not keys:
                    continue  # ignore empty path like "" or leading/trailing separators only
                _deep_update_path(data, keys, v)
            else:
                data[k] = v  # replace; do not attempt dict-merge
    else:
        data.update(dict(new_data))

    json_dump(path, data, indent=indent)
    return data


if __name__ == '__main__':
    from pprint import pprint
    from hexss.constants import *

    # Example usage:
    from pathlib import Path
    from hexss import json_dump, json_update

    # Example file
    file = Path("config.json")
    json_dump(file, {})  # reset

    # 1. Load with default (file may not exist yet)
    print(f"\n{CYAN}Loaded:{END}")
    data = json_load(file, default={"theme": "light", "volume": 50}, dump=True)
    pprint(data)
    # {'theme': 'light', 'volume': 50}

    # 2. Update shallow (simple dict.update)
    print(f"\n{CYAN}After shallow update:{END}")
    json_update(file, {"volume": 75})
    pprint(json_load(file))
    # {'theme': 'light', 'volume': 75}

    # 3. Update deeply with dot-notation
    print(f"\n{CYAN}After deep update:{END}")
    json_update(file, {"ui.colors.background": "#000000"}, deep=True)
    pprint(json_load(file))
    # {'theme': 'light', 'ui': {'colors': {'background': '#000000'}}, 'volume': 75}

    # 4. Update deeply with custom separator
    print(f"\n{CYAN}After deep update with '/':{END}")
    json_update(file, {"network/wifi/ssid": "MyWiFi"}, deep="/")
    pprint(json_load(file))
    # {'network': {'wifi': {'ssid': 'MyWiFi'}},
    #  'theme': 'light',
    #  'ui': {'colors': {'background': '#000000'}},
    #  'volume': 75}

    # 5. Use a Mapping instead of dict (works because input type is Mapping)
    print(f"\n{CYAN}After mapping update:{END}")
    from types import MappingProxyType

    extra = MappingProxyType({"readonly": True, "network/ethernet/enabled": False})
    json_update(file, extra, deep='/')
    pprint(json_load(file))
    # {'network': {'ethernet': {'enabled': False}, 'wifi': {'ssid': 'MyWiFi'}},
    #  'readonly': True,
    #  'theme': 'light',
    #  'ui': {'colors': {'background': '#000000'}},
    #  'volume': 75}
