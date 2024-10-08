import os
import json
from typing import Dict, Any


def json_load(file_path: str, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    data = default if default is not None else {}

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data.update(json.load(f))
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Invalid JSON in {file_path}: {str(e)}", e.doc, e.pos) from e

    return data


def json_dump(file_path: str, data: Dict[str, Any], indent: int = 4) -> None:
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
    except OSError as e:
        raise OSError(f"Error writing to {file_path}: {str(e)}") from e


def json_update(file_path: str, new_data: Dict[str, Any], indent: int = 4) -> Dict[str, Any]:
    if not file_path.lower().endswith('.json'):
        raise ValueError("File extension must be .json")

    try:
        data = json_load(file_path, default={})
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in existing file {file_path}: {str(e)}", e.doc, e.pos) from e

    data.update(new_data)

    try:
        json_dump(file_path, data, indent)
    except OSError as e:
        raise OSError(f"Error updating {file_path}: {str(e)}") from e

    return data


if __name__ == '__main__':
    config = json_load('config.json', default={
        'device': 'PC',
        'model_name': '-',
        '2': '1'
    })
    json_update('config.json', config)
    print(config)
