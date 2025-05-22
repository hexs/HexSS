import time

from hexss import close_port
from hexss.config import load_config
from hexss.constants.terminal_color import *
from hexss.control_robot.robot import Robot
from hexss.serial import get_comport
from hexss.threading import Multithread
from hexss.control_robot import app


def read_mem(robot):
    ...
    while True:

        # print(robot.read_bit(1, robot.DSS1, robot.SV))

        robot.read_register(1)
        time.sleep(2)


def main():
    try:
        comport = get_comport('ATEN USB to Serial', 'USB-Serial Controller')
        robot = Robot(comport, baudrate=38400)
        print(f"{GREEN}Robot initialized successfully{END}")
    except Exception as e:
        print(f"Failed to initialize robot: {e}")
        exit()

    config = load_config('control_robot_server', {
        "ipv4": '0.0.0.0',
        "port": 2005,
    })
    close_port(config['ipv4'], config['port'])

    data = {
        'config': config,
        'play': True
    }

    m = Multithread()
    m.add_func(app.run, args=(data, robot))
    m.add_func(read_mem, args=(robot,))

    m.start()
    m.join()


if __name__ == '__main__':
    main()
