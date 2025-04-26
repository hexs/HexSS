import argparse
import os
import importlib

import hexss
from hexss.constants.terminal_color import *
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
                print(f"{k:{max_key_length}}: {BLUE if isinstance(v, (int, float)) else DARK_GREEN}{v}{END}")
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

        # Navigate nested keys and create missing dictionaries
        current = data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        # Set new value
        current[keys[-1]] = new_value

        # Persist changes
        json_update(file_path, {file_name: data})

        # Feedback
        val_color = (
            ORANGE if new_value is None else
            BLUE if isinstance(new_value, (int, float)) else
            DARK_GREEN
        )
        disp_val = new_value if isinstance(new_value, (int, float, type(None))) else f"'{new_value}'"
        print(f"Updated {'.'.join(keys)} to {val_color}{disp_val}{END}")
    except Exception as e:
        print(f"Error while updating configuration: {e}")


def run_config(args):
    """Handler for the 'config' sub-command."""
    key_parts = (args.key or '').split('.')
    file_name, *keys = key_parts

    if  file_name == '':
        return

    cfg_path = hexss_dir / 'config' / f'{file_name}.json'
    try:
        raw = json_load(cfg_path)
        cfg = raw.get(file_name, raw)
    except FileNotFoundError:
        print(f"Configuration file for '{file_name}' not found.")
        return

    if args.value is None:
        show_config(cfg, keys)
    else:
        if args.text:
            new_val = args.value
        else:
            try:
                new_val = eval(args.value)
            except Exception:
                new_val = args.value
        update_config(file_name, keys, new_val)


def print_env():
    """Print all environment variables."""
    for k, v in os.environ.items():
        print(f'{k:25}: {v}')


def main():
    parser = argparse.ArgumentParser(
        prog='hexss',
        usage='hexss [-h]'
    )
    subparsers = parser.add_subparsers(
        title='positional arguments',
        dest='action',
        required=True,
        metavar=''  # hide the choice list placeholder in help
    )

    # config
    cfg = subparsers.add_parser('config', help='set or show configuration')
    cfg.add_argument('key', nargs='?', help="Config key, e.g. 'proxies' or 'proxies.http'")
    cfg.add_argument('value', nargs='?', help='New value for the key')
    cfg.add_argument('-T', '--text', action='store_true', help='Interpret value as text')
    cfg.set_defaults(func=run_config)

    # camera_server
    cs = subparsers.add_parser(
        'camera_server',
        aliases=['camera-server'],
        help='run the camera server'
    )
    cs.set_defaults(func=lambda args: importlib.import_module('hexss.server.camera_server').run())

    # file_manager_server
    fm = subparsers.add_parser(
        'file_manager_server',
        aliases=['file-manager-server'],
        help='run the file manager server'
    )
    fm.set_defaults(func=lambda args: importlib.import_module('hexss.server.file_manager_server').run())

    # install
    inst = subparsers.add_parser('install', help='install hexss')
    inst.set_defaults(func=lambda args: importlib.import_module('hexss.python').install('hexss'))

    # upgrade
    upg = subparsers.add_parser('upgrade', help='upgrade hexss')
    upg.set_defaults(func=lambda args: importlib.import_module('hexss.python').install_upgrade('hexss'))

    # environ
    env = subparsers.add_parser('environ', aliases=['env'], help='show environment variables')
    env.set_defaults(func=lambda args: print_env())

    # set_proxy_env
    wp = subparsers.add_parser('set_proxy_env', help='print commands to set proxy env vars')
    wp.set_defaults(func=lambda args: importlib.import_module('hexss.python').generate_proxy_env_commands())

    # hostname
    hn = subparsers.add_parser('hostname', help='get hostname')
    hn.set_defaults(func=lambda args: print(hexss.hostname))

    # username
    un = subparsers.add_parser('username', help='get username')
    un.set_defaults(func=lambda args: print(hexss.username))

    # proxy
    pr = subparsers.add_parser('proxy', help='get proxy settings')
    pr.set_defaults(func=lambda args: print(hexss.proxies))

    # system
    sy = subparsers.add_parser('system', help='get system')
    sy.set_defaults(func=lambda args: print(hexss.system))

    # constant
    gc = subparsers.add_parser('constant', help='print hexss constants')
    gc.set_defaults(func=lambda args: import_get_constants())

    args = parser.parse_args()
    args.func(args)


def import_get_constants():
    print('hostname         :', hexss.hostname)
    print('username         :', hexss.username)
    print()
    print('proxies          :', hexss.proxies)
    print()
    print('--path--')
    print('hexss dir        :', hexss_dir)
    print('venv             :', hexss.path.get_venv_dir())
    print('python exec      :', hexss.path.get_python_path())
    print('main python exec :', hexss.path.get_main_python_path())
    print('working dir      :', hexss.path.get_current_working_dir())
    print('script dir       :', hexss.path.get_script_dir())


if __name__ == '__main__':
    main()
