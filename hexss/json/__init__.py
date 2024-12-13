import os
import json
from typing import Dict, Any, Optional


def json_load(
        file_path: str,
        default: Optional[Dict[str, Any]] = None,
        dump: bool = False
) -> Dict[str, Any]:
    """
    Load JSON data from a file. If the file does not exist or is invalid, return a default value.

    Args:
        file_path (str): Path to the JSON file.
        default (Optional[Dict[str, Any]]): Default data to return/load if the file does not exist.
        dump (bool): Whether to write the default data to the file if it doesn't exist.

    Returns:
        Dict[str, Any]: The loaded JSON data.

    Raises:
        ValueError: If the file does not have a .json extension.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    data = default or {}

    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data.update(json.load(f))
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {str(e)}", e.doc, e.pos) from e

    # Dump default data to file if specified
    if dump:
        json_dump(file_path, data)

    return data


def json_dump(
        file_path: str,
        data: Dict[str, Any],
        indent: int = 4
) -> None:
    """
    Write JSON data to a file.

    Args:
        file_path (str): Path to the JSON file.
        data (Dict[str, Any]): The data to write to the file.
        indent (int): The number of spaces for indentation in the JSON file.

    Raises:
        ValueError: If the file does not have a .json extension.
        OSError: If there is any issue writing to the file.
    """
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    # Create parent directories if they don't exist
    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    # Write data to JSON file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except OSError as e:
        raise OSError(f"Error writing to {file_path}: {str(e)}") from e


def json_update(
        file_path: str,
        new_data: Dict[str, Any],
        indent: int = 4
) -> Dict[str, Any]:
    """
    Update an existing JSON file with new data.

    Args:
        file_path (str): Path to the JSON file.
        new_data (Dict[str, Any]): Data to update in the JSON file.
        indent (int): The number of spaces for indentation in the JSON file.

    Returns:
        Dict[str, Any]: The updated data.

    Raises:
        ValueError: If the file does not have a .json extension.
        json.JSONDecodeError: If the existing file contains invalid JSON.
        OSError: If there is any issue writing to the file.
    """
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    # Load the existing data or initialize with an empty dict
    try:
        data = json_load(file_path, default={})
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {str(e)}", e.doc, e.pos) from e

    # Update the existing data with new values
    data.update(new_data)

    # Write the updated data back to the file
    try:
        json_dump(file_path, data, indent)
    except OSError as e:
        raise OSError(f"Error updating {file_path}: {str(e)}") from e

    return data


if __name__ == '__main__':
    # Example usage:
    default_config = {
        'device': 'PC',
        'model_name': '-',
        'version': '1.0'
    }

    # Load the JSON file and create it with the default config if it doesn't exist
    config = json_load('config.json', default=default_config, dump=True)
    print("Loaded config:", config)

    # Update the JSON file with new data
    updated_config = json_update('config.json', {'device': 'Laptop', 'version': '1.1'})
    print("Updated config:", updated_config)
