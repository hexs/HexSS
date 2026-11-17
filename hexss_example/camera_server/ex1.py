def start_camera_server():
    from hexss import camera_server

    camera_server.run()
    # camera_server.run(background=True)


def shutdown_camera_server():
    import urllib.request

    try:
        req = urllib.request.Request("http://127.0.0.1:2002/api/shutdown", method='POST')
        urllib.request.urlopen(req, timeout=2)
        print("Camera server shut down successfully, camera is now off.")
    except Exception as e:
        print("No server is running or it has already been shut down.")


if __name__ == '__main__':
    start_camera_server()

    # shutdown_camera_server()
    # or
    # from hexss.network import kill_process_on_port
    # kill_process_on_port(2002)
