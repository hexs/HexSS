from hexss import json_load, get_ipv4
from hexss.threading import Multithread
from hexss.control_robot import app


def run():
    config = json_load('control_robot_server_config.json', {
        "ipv4": '0.0.0.0',
        "port": 2005,
    }, True)

    data = {
        'config': config,
        'play': True
    }

    m = Multithread()
    m.add_func(app.run, args=(data,))

    m.start()
    m.join()


if __name__ == '__main__':
    run()
