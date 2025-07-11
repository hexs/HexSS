from hexss import close_port
from hexss.config import load_config
from hexss.constants.terminal_color import *
from hexss.serial import get_comport
from hexss.threading import Multithread
from hexss.modbus.serial import app
from hexss.modbus.serial.robot import Robot


def main():
    comport = get_comport(
        'ATEN USB to Serial',
        'IAI USB to UART Bridge Controller',
        'USB-Serial Controller',
        'USB Serial Port'
    )
    print(f"Using COM port: {comport}\n")
    robot = Robot(comport=comport, baudrate=38400, num_slaves=4)
    config = load_config('control_robot_server', {
        'ipv4': '0.0.0.0',
        'port': 2005,
        'num_slaves': robot.num_slaves
    })
    close_port(config['ipv4'], config['port'])

    data = {
        'config': config,
        'play': True
    }

    m = Multithread()

    m.add_func(app.run, args=(data, robot))

    m.start()
    m.join()


if __name__ == '__main__':
    main()
