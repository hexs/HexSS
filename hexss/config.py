from hexss import json_load, hexss_dir, json_update


def list_config_files():
    config_path = hexss_dir / 'config'
    return [file.stem for file in config_path.iterdir() if file.is_file() and file.suffix == '.json']


def load_config(json_file_name, default={}):
    config_path = hexss_dir / 'config' / f'{json_file_name}.json'
    config_data = json_load(config_path, default, True)
    return config_data.get(json_file_name, config_data)


def update_config(json_file_name, new_data):
    config_path = hexss_dir / 'config' / f'{json_file_name}.json'
    config_data = json_update(config_path, new_data)
