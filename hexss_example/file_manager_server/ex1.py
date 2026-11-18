def start_file_manager_server():
    from hexss import file_manager_server

    file_manager_server.run()
    # file_manager_server.run(background=True)


def shutdown_file_manager_server():
    import json
    import urllib.error
    import urllib.request

    host = '127.0.0.1'
    port = 2001

    req = urllib.request.Request(
        f"http://{host}:{port}/api/shutdown",
        method='POST',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.load(r).get('success', False)
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode(errors='replace'))
        return False
    except urllib.error.URLError:
        return False


if __name__ == '__main__':
    start_file_manager_server()

    # shutdown_file_manager_server()
    # # or
    # from hexss.network import kill_process_on_port
    # kill_process_on_port(2001)
