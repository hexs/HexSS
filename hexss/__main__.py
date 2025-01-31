import argparse
import os
from hexss import hexss_dir, json_load, json_update
from hexss.server import camera_server


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
        file_path = os.path.join(hexss_dir, f'{file_name}.json')
        config = json_load(file_path)
        data = config.get(file_name, config)

        # Traverse and update the appropriate key
        for key in keys[:-1]:
            if key not in data:
                data[key] = {}
            data = data[key]

        data[keys[-1]] = new_value
        json_update(file_path, {file_name: data})
        print(f"Updated '{'.'.join(keys)}' to '{new_value}'")
    except Exception as e:
        print(f"Error while updating configuration: {e}")


def main():
    """Parse arguments and perform the requested action."""
    parser = argparse.ArgumentParser(description="Manage configuration files or run specific functions.")
    parser.add_argument("action", help="Specify the action to perform, e.g., 'config', 'camera_server'.")
    parser.add_argument("key", nargs="?", help="Configuration key, e.g., 'proxies' or 'proxies.http'.")
    parser.add_argument("value", nargs="?", help="New value for the configuration key (if updating).")

    args = parser.parse_args()

    if args.action == "camera_server":
        camera_server.run()
        return

    if args.action == "config":
        if args.key:
            key_parts = args.key.split(".")
            file_name = key_parts[0]  # Extract file name (e.g., 'proxies')
            keys = key_parts[1:]  # Extract nested keys (e.g., ['http'])

            if args.value:
                update_config(file_name, keys, args.value)
            else:
                try:
                    config = json_load(os.path.join(hexss_dir, f'{file_name}.json'))
                    data = config.get(file_name, config)
                    show_config(data, keys)
                except FileNotFoundError:
                    print(f"Configuration file for '{file_name}' not found.")
                except Exception as e:
                    print(f"Error while loading configuration: {e}")
        else:
            print("Error: 'key' is required for the 'config' action.")
    else:
        print(f"Error: Unknown action '{args.action}'.")


if __name__ == "__main__":
    main()
