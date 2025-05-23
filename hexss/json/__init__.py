import json
from pathlib import Path
from typing import Dict, Any, Optional, Union


def json_load(
        file_path: Union[str, Path],
        default: Optional[Dict[str, Any]] = None,
        dump: bool = False
) -> Dict[str, Any]:
    """
    Load JSON data from a file. If the file does not exist or contains invalid JSON,
    return a default value.

    Args:
        file_path (Union[str, Path]): Path to the JSON file.
        default (Optional[Dict[str, Any]]): Default data to use if the file doesn't exist.
        dump (bool): Whether to write the default data to the file if it doesn't exist.

    Returns:
        Dict[str, Any]: The loaded JSON data.

    Raises:
        ValueError: If the file does not have a .json extension or the JSON content is not a dict.
    """
    path = Path(file_path)
    if path.suffix.lower() != '.json':
        raise ValueError("File extension must be .json")

    # Make a shallow copy of the default (if provided) to avoid modifying the original.
    data: Dict[str, Any] = default.copy() if default is not None else {}

    if path.exists():
        try:
            with path.open('r', encoding='utf-8') as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"JSON content in {file_path} is not a JSON object (expected dict)."
                )
            data.update(loaded)
        except json.JSONDecodeError as e:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if content == '':
                pass
            else:
                raise json.JSONDecodeError(
                    f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos
                ) from e

    # Dump default data to file if specified
    if dump:
        json_dump(path, data)

    return data


def json_dump(
        file_path: Union[str, Path],
        data: Dict[str, Any],
        indent: int = 4
) -> Dict[str, Any]:
    """
    Write JSON data to a file.

    Args:
        file_path (Union[str, Path]): Path to the JSON file.
        data (Dict[str, Any]): The data to write to the file.
        indent (int): The number of spaces for indentation in the JSON file.

    Raises:
        ValueError: If the file does not have a .json extension.
        OSError: If there is an issue writing to the file.
    """
    path = Path(file_path)
    if path.suffix.lower() != '.json':
        raise ValueError("File extension must be .json")

    # Create parent directories if they don't exist.
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except OSError as e:
        raise OSError(f"Error writing to {file_path}: {e.strerror}") from e
    return data


def json_update(
        file_path: Union[str, Path],
        new_data: Dict[str, Any],
        deep: bool = False,
        indent: int = 4
) -> Dict[str, Any]:
    """
    Update an existing JSON file with new data, supporting dot notation for nested keys.

    Args:
        file_path (Union[str, Path]): Path to the JSON file.
        new_data (Dict[str, Any]): Data to update in the JSON file.
        deep (bool): If True, allows deep updates using dot notation.
        indent (int): The number of spaces for indentation in the JSON file.

    Returns:
        Dict[str, Any]: The updated data.

    Raises:
        ValueError: If the file does not have a .json extension or contains non-dict JSON.
        json.JSONDecodeError: If the existing file contains invalid JSON.
        OSError: If there is an issue writing to the file.
    """

    def deep_update(d: Dict[str, Any], keys: list, value: Any):
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    path = Path(file_path)
    if path.suffix.lower() != '.json':
        raise ValueError("File extension must be .json")

    # Load the existing data or initialize with an empty dict.
    try:
        data = json_load(path, default={})
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in {file_path}: {e.msg}", e.doc, e.pos
        ) from e

    # Update the existing data with new values.
    if deep:
        for k, v in new_data.items():
            if '.' in k:
                keys = k.split('.')
                deep_update(data, keys, v)
            else:
                # Direct key assignment (replace, do NOT merge dicts)
                data[k] = v
    else:
        data.update(new_data)

    # Write the updated data back to the file.
    try:
        json_dump(path, data, indent)
    except OSError as e:
        raise OSError(f"Error updating {file_path}: {e.strerror}") from e

    return data


if __name__ == '__main__':
    # Example usage:
    from pprint import pprint
    from hexss import json_update

    d1 = json_dump('config.json', {
        "device": "Laptop",
        "model_name": "-",
        "version": "1.1"
    })
    print('d1')
    pprint(d1)
    # {
    #     "device": "Laptop",
    #     "model_name": "-",
    #     "version": "1.1"
    # }

    d2 = json_update('config.json', {'data': {'a1': 1, 'a2': 2, 'a3': 3}})
    print('d2')
    pprint(d2)
    # {
    #     "device": "Laptop",
    #     "model_name": "-",
    #     "version": "1.1",
    #     "data": {
    #         "a1": 1,
    #         "a2": 2,
    #         "a3": 3
    #     }
    # }

    d3 = json_update('config.json', {'data': {'a4': 2}})
    print('d3')
    pprint(d3)
    # {
    #     "device": "Laptop",
    #     "model_name": "-",
    #     "version": "1.1",
    #     "data": {
    #         "a4": 2
    #     }
    # }
    #

    d4 = json_update('config.json', {'data.a3': 4}, deep=True)
    print('d4')
    pprint(d4)
    # {
    #     "device": "Laptop",
    #     "model_name": "-",
    #     "version": "1.1",
    #     "data": {
    #         "a4": 2,
    #         "a3": 4
    #     }
    # }
    #

    d5 = json_update('config.json', {'data.a3': {'b1': 3}}, deep=True)
    print('d5')
    pprint(d5)
    # {
    #     "device": "Laptop",
    #     "model_name": "-",
    #     "version": "1.1",
    #     "data": {
    #         "a4": 2,
    #         "a3": {
    #             "b1": 3
    #         }
    #     }
    # }
