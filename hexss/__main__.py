import argparse
import os

import hexss
from hexss import hexss_dir, json_load, json_update


def show_config(data, keys):
    """Display configuration values based on the keys provided."""
    try:
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                print(f"Key '{'.'.join(keys)}' not found in configuration.")
                return

        if isinstance(data, dict):
            max_key_length = min(max((len(k) for k in data.keys()), default=0) + 1, 15)
            for k, v in data.items():
                print(f"{k:{max_key_length}}: {v}")
        else:
            print(data)
    except Exception as e:
        print(f"Error while displaying configuration: {e}")


def update_config(file_name, keys, new_value):
    """Update a JSON configuration file with a new value for the given keys."""
    try:
        file_path = hexss_dir / 'config' / f'{file_name}.json'
        config_data = json_load(file_path)
        data = config_data.get(file_name, config_data)

        data[keys[-1]] = new_value
        json_update(file_path, {file_name: data})
        print(f"Updated '{'.'.join(keys)}' to '{new_value}'")
    except Exception as e:
        print(f"Error while updating configuration: {e}")


def run():
    """Parse arguments and perform the requested action."""
    parser = argparse.ArgumentParser(description="Manage configuration files or run specific functions.")
    parser.add_argument("action", help="e.g., 'config', 'camera_server', 'file_manager_server'.")
    parser.add_argument("key", nargs="?", help="Configuration key, e.g., 'proxies' or 'proxies.http'.")
    parser.add_argument("value", nargs="?", help="New value for the configuration key (if updating).")

    args = parser.parse_args()

    if args.action == "camera_server":
        from hexss.server import camera_server
        camera_server.run()

    elif args.action == "file_manager_server":
        from hexss.server import file_manager_server
        file_manager_server.run()

    elif args.action == "config":
        if args.key is None:
            for config_file in os.listdir(hexss_dir / "config"):
                print(f"- {config_file.split('.')[0]}")

        elif args.key:
            key_parts = args.key.split(".")
            file_name = key_parts[0]
            keys = key_parts[1:]

            if args.value is None:
                try:
                    config_data = json_load(hexss_dir / 'config' / f'{file_name}.json')
                    config_data = config_data.get(file_name, config_data)
                    show_config(config_data, keys)

                except FileNotFoundError:
                    print(f"Configuration file for '{file_name}' not found.")
                except Exception as e:
                    print(f"Error while loading configuration: {e}")
            else:
                update_config(file_name, keys, args.value)

    elif args.action == "install":
        from hexss.python import install
        install('hexss')

    elif args.action == "upgrade":
        from hexss.python import install_upgrade
        install_upgrade('hexss')

    elif args.action in ["env", "environ"]:
        for key, value in os.environ.items():
            print(f'{key:25}:{value}')

    elif args.action in ["write-proxy-to-env", "write_proxy_to_env"]:
        hexss.python.write_proxy_to_env()

    elif args.action in ["get-constant", "get_constant"]:
        print('hostname         :', hexss.hostname)
        print('username         :', hexss.username)
        print()
        print('proxies          :', hexss.proxies)
        print()
        print('--path--')
        print('hexss dir        :', hexss.hexss_dir)
        print('venv             :', hexss.path.get_venv_dir())
        print("python exec      :", hexss.path.get_python_path())
        print("main python exec :", hexss.path.get_main_python_path())
        print("working dir      :", hexss.path.get_current_working_dir())
        print("script dir       :", hexss.path.get_script_dir())

    else:
        print(f"Error: Unknown action '{args.action}'.")


if __name__ == "__main__":
    run()
