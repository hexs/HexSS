from hexss import json_load, hexss_dir


def list_config_files():
    config_path = hexss_dir / 'config'
    return [file.stem for file in config_path.iterdir() if file.is_file() and file.suffix == '.json']


def load_config(file_name):
    config_path = hexss_dir / 'config' / f'{file_name}.json'
    config_data = json_load(config_path, {})
    return config_data.get(file_name, config_data)
