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
    Load JSON data from a file.

    :param file_path: Path to the .json file.
    :param default: Default dictionary to use if file is missing or empty.
                    File content overrides these defaults.
    :param dump: If True, write the merged data (defaults + file content) back to disk.
    :return: The loaded (and merged) dictionary.
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
    Write JSON data to a file atomically using a temporary file.

    :param file_path: Destination path.
    :param data: The dictionary data to write.
    :param indent: JSON indentation level.
    :return: A copy of the written data as a standard dict.
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
        tmp.replace(path)
    except OSError as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise OSError(f"Error writing to {file_path}: {e.strerror}") from e

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

    :param file_path: Path to the .json file.
    :param new_data: Dictionary of data to merge in.
    :param deep: If True, split keys by `sep`. If str, use that string as separator.
                 If False (default), perform shallow update.
    :param sep: Default separator (default: ".") used if deep=True.
    :param indent: Indentation for the output file.
    :return: The updated dictionary.
    """
    path = Path(file_path)
    if path.suffix.lower() != ".json":
        raise ValueError("File extension must be .json")

    # Load current data
    data = json_load(path, default={})
    _ensure_json_object(data, str(file_path))

    # Determine separator
    active_sep = deep if isinstance(deep, str) else (sep if deep is True else None)
    use_deep = active_sep is not None

    if use_deep and active_sep:
        for k, v in new_data.items():
            if isinstance(k, str) and active_sep in k:
                keys = [p for p in k.split(active_sep) if p != ""]
                if not keys:
                    continue
                _deep_update_path(data, keys, v)
            else:
                data[k] = v
    else:
        data.update(dict(new_data))

    json_dump(path, data, indent=indent)
    return data


def json_remove(
        file_path: Union[str, Path],
        key: str,
        deep: Union[bool, str, None] = False,
        *,
        sep: str = ".",
        indent: int = 4
) -> Dict[str, Any]:
    """
    Remove a key from a JSON file.

    :param file_path: Path to the .json file.
    :param key: The key to remove.
    :param deep: If True, treat `key` as a path separated by `sep`.
                 If str, use that string as separator.
    :param sep: Default separator (default: ".") used if deep=True.
    :return: The updated dictionary.
    """
    path = Path(file_path)
    if path.suffix.lower() != ".json":
        raise ValueError("File extension must be .json")

    # Load current data
    data = json_load(path, default={})
    _ensure_json_object(data, str(file_path))

    # Determine separator
    active_sep = deep if isinstance(deep, str) else (sep if deep is True else None)
    use_deep = active_sep is not None

    if use_deep and active_sep and active_sep in key:
        keys = [p for p in key.split(active_sep) if p != ""]
        if keys:
            target_key = keys[-1]
            parent_keys = keys[:-1]

            # Traverse to parent
            current = data
            path_exists = True
            for k in parent_keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    path_exists = False
                    break

            # Remove if parent exists and is a dict
            if path_exists and isinstance(current, dict):
                current.pop(target_key, None)
    else:
        # Shallow remove
        data.pop(key, None)

    json_dump(path, data, indent=indent)
    return data


def json_rename(
        file_path: Union[str, Path],
        old_key: str,
        new_key: str,
        deep: Union[bool, str, None] = False,
        *,
        sep: str = ".",
        indent: int = 4
) -> Dict[str, Any]:
    """
    Rename a key in a JSON file.

    :param file_path: Path to the .json file.
    :param old_key: The current key (or path) to rename.
    :param new_key: The new key (or path) to assign the value to.
    :param deep: If True, treat keys as paths separated by `sep`.
                 If str, use that string as separator.
    :param sep: Default separator (default: ".") used if deep=True.
    :param indent: Indentation for the output file.
    :return: The updated dictionary.
    """
    path = Path(file_path)
    if path.suffix.lower() != ".json":
        raise ValueError("File extension must be .json")

    data = json_load(path, default={})
    _ensure_json_object(data, str(file_path))

    active_sep = deep if isinstance(deep, str) else (sep if deep is True else None)

    val_found = False
    val = None

    if active_sep and active_sep in old_key:
        keys = [p for p in old_key.split(active_sep) if p]
        if keys:
            parent = data
            target_key = keys[-1]
            # Traverse to parent
            for k in keys[:-1]:
                if isinstance(parent, dict) and k in parent:
                    parent = parent[k]
                else:
                    parent = None
                    break

            # Pop value if exists
            if parent is not None and isinstance(parent, dict) and target_key in parent:
                val = parent.pop(target_key)
                val_found = True
    else:
        # Shallow
        if old_key in data:
            val = data.pop(old_key)
            val_found = True

    if val_found:
        if active_sep and active_sep in new_key:
            keys = [p for p in new_key.split(active_sep) if p]
            if keys:
                _deep_update_path(data, keys, val)
        else:
            data[new_key] = val

        json_dump(path, data, indent=indent)

    return data


if __name__ == '__main__':
    from pprint import pprint
    from hexss.constants import *
    from types import MappingProxyType

    # Example file
    file = Path("config.json")
    json_dump(file, {})  # Reset file

    # 1. Load with default (creates file because dump=True)
    print(f"\n{CYAN}1. Loaded (defaults created):{END}")
    data = json_load(file, default={"theme": "light", "volume": 50}, dump=True)
    pprint(data)

    # 2. Update shallow
    print(f"\n{CYAN}2. After shallow update (volume -> 75):{END}")
    json_update(file, {"volume": 75})
    pprint(json_load(file))

    # 3. Update deeply with dot-notation
    print(f"\n{CYAN}3. After deep update (add ui.colors.background):{END}")
    json_update(file, {"ui.colors.background": "#000000"}, deep=True)
    pprint(json_load(file))

    # 4. Update deeply with custom separator
    print(f"\n{CYAN}4. After deep update with '/' (add network/wifi/ssid):{END}")
    json_update(file, {"network/wifi/ssid": "MyWiFi"}, deep="/")
    pprint(json_load(file))

    # 5. Use a Mapping instead of dict
    print(f"\n{CYAN}5. After mapping update (readonly, ethernet):{END}")
    extra = MappingProxyType({"readonly": True, "network/ethernet/enabled": False})
    json_update(file, extra, deep='/')
    pprint(json_load(file))

    # 1. Rename shallow
    print(f"\n{CYAN}6. Rename 'volume' -> 'audio_level':{END}")
    json_rename(file, "volume", "audio_level")
    pprint(json_load(file))

    # 2. Rename deep (Key change only)
    print(f"\n{CYAN}7. Rename 'network/wifi/ssid' -> 'network/wifi/SSID' (using '/'):{END}")
    json_rename(file, "network/wifi/ssid", "network/wifi/SSID", deep="/")
    pprint(json_load(file))
    #
    # 3. Rename deep (Move/Reparenting)
    print(f"\n{CYAN}8. Move 'ui.colors.background' -> 'theme.bg' (using dot):{END}")
    json_rename(file, "ui.colors.background", "theme.bg", deep=True)
    pprint(json_load(file))

    # 4. Rename with path normalization (Your requested usage)
    print(f"\n{CYAN}9. Rename 'network/wifi' -> 'network/WiFi':{END}")
    json_rename(file, 'network/wifi', 'network/WiFi', deep="/")
    pprint(json_load(file))

    # 6. Remove a simple key
    print(f"\n{CYAN}10. After removing 'audio_level':{END}")
    json_remove(file, "audio_level")
    pprint(json_load(file))

    # 7. Remove a nested key (dot notation)
    print(f"\n{CYAN}11. After removing 'theme.bg':{END}")
    json_remove(file, "theme.bg", deep=True)
    pprint(json_load(file))

    # 8. Remove a nested key (custom separator)
    print(f"\n{CYAN}12. After removing 'network/wifi/ssid':{END}")
    json_remove(file, "network/WiFi/SSID", deep="/")
    pprint(json_load(file))
