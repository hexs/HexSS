import time
import logging
from datetime import datetime
from pprint import pprint
from typing import Union, List, Optional
from functools import wraps
from hexss import check_packages

check_packages('pymodbus', 'pyserial', auto_install=True)

import numpy as np
import pandas as pd
from pymodbus.client import ModbusSerialClient

import hexss.control_robot
from hexss.constants.terminal_color import *
from hexss.serial import get_comport
from hexss.numpy import combine_uint16_to_int32, split_int32_to_uint16

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def normalize_slaves(func):
    """Decorator to normalize 'slaves' argument into a list format."""

    @wraps(func)
    def wrapper(self, slaves: Union[int, List[int]], *args, **kwargs):
        if isinstance(slaves, int):
            slaves = [slaves]
        elif not isinstance(slaves, list):
            raise ValueError(f"Invalid 'slaves' type ({type(slaves)}). Must be int or list.")
        return func(self, slaves, *args, **kwargs)

    return wrapper


class Robot:
    # Controller Input Signals
    DRG1 = DEVICE_CONTROL_REGISTER = 0x0D00
    CSTR = 3  # 0: Normal, “0” -> “1” rise edge: Positioning start to the target position specified with the position no.
    HOME = 4  # “0” -> “1” rise edge: Home return operation
    STP = PAUSE = 5  # 0: Normal, 1: Pause (deceleration stop)
    RES = ALARM_RESET = 8  # 0: Normal, “0” -> “1” rise edge: Alarm reset
    SON = SERVO = 12  # 0: Servo OFF, 1: Servo ON
    SFTY = 14  # Safety speed set with the parameter 0: Invalid, 1: Valid

    POSR = 0x0D03
    JOG_MINUS = 8
    JOG_PLUS = 9

    # Controller Output Signals
    DSS1 = DEVICE_STATUS_REGISTER = 0x9005
    PEND = 3  # 1: Positioning completed
    HEND = 4  # 1: Home return completed
    STP = 5  # 1: Pause command being issued
    ALML = 9  # 1: Alarm indicating that continuous operation is impossible
    ALMH = 10  # 1: Alarm indicating that continuous operation is impossible
    PSFL = 11  # 1: Push & hold missing
    SV = 12  # 1: Operation preparation completed (servo ON status)
    PWR = 13  # 1: Controller preparation completed
    SFTY = 14  # 1: Safety speed valid condition
    EMGS = 15  # 1: Under emergency stop

    DSSE = EXPANSION_DEVICE_STATUS_REGISTER = 0x9007
    MOVE = 5  # 1: Moving (including home return, push & hold operation)
    PUSH = 10  # 1: Push & hold operating
    GMHS = 11  # 1: Home returning

    ZONS = ZONE_STATUS_REGISTER = 0x9013
    ZONE1 = 0  # Zone output 1
    ZONE2 = 1  # Zone output 2
    PZONE = 8  # Position zone output

    def __init__(self, comport: str, baudrate: int = 38400, timeout: float = 0.05, dry_run: bool = False) -> None:
        """Initialize Modbus client for robot communication."""
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self.table_data = pd.DataFrame()
        self.stop_waiting = False

        if not dry_run:
            self.client = ModbusSerialClient(port=comport, baudrate=baudrate, timeout=timeout)
            if not self.client.connect():
                self.logger.warning(f"Failed to connect to {comport}. Check configuration.")
        else:
            self.client = None
            self.logger.warning("Dry-run mode enabled. No commands will be sent.")

    def close_connection(self) -> None:
        """Close the Modbus communication client."""
        if self.client and self.client.is_socket_open():
            self.client.close()
            self.logger.info("Connection closed.")

    def read_registers(self, slave_id: int, address: int, count: int = 1) -> Optional[List[int]]:
        """Read registers from the Modbus slave device."""
        try:
            response = self.client.read_input_registers(address=address, count=count, slave=slave_id)
            if response.isError():
                self.logger.error(f"Error reading from slave {slave_id}, address {address}: {response}")
                return None
            return response.registers
        except Exception as e:
            self.logger.exception(f"Exception during read: {e}")
            return None

    def read_memories(self, slave_id: int):
        memories = []

        for i in range(1024):
            data = self.read_registers(slave_id, 64 * i, count=64)
            memories.append(data)
            print(f'\r{i} {data}', end='')

        print()
        return memories

    def write_registers(self, slave_id: int, address: int, values: List[int]) -> None:
        """Write values to Modbus slave device registers."""
        if self.dry_run:
            self.logger.debug(f"Dry-run mode: Writing to {slave_id}, address {address}, values {values}")
            return

        try:
            response = self.client.write_registers(address=address, values=values, slave=slave_id)
            if response.isError():
                self.logger.error(f"Error writing to slave {slave_id}, address {address}: {response}")
        except Exception as e:
            self.logger.exception(f"Exception during write: {e}")

    def read_bit(self, slave: int, register_address: int, bit_number: int) -> Union[bool, None]:
        """Read a specific bit in a register."""
        registers = self.read_registers(slave, register_address, 1)
        if registers:
            return (registers[0] & (1 << bit_number)) != 0
        return None

    def set_bit(self, slave: int, register_address: int, bit_number: int) -> None:
        """Set a specific bit in a register."""
        registers = self.read_registers(slave, register_address, 1)
        if registers:
            new_value = registers[0] | (1 << bit_number)
            if registers[0] == new_value:
                return
            self.write_registers(slave, register_address, [new_value])

    def reset_bit(self, slave: int, register_address: int, bit_number: int) -> None:
        """Reset (clear) a specific bit in a register."""
        registers = self.read_registers(slave, register_address, 1)
        if registers:
            new_value = registers[0] & ~(1 << bit_number)
            if registers[0] == new_value:
                return
            self.write_registers(slave, register_address, [new_value])

    def write_to_register(self, slave: int, register_address: int, value: int) -> None:
        """Write a single value to a register."""
        self.write_registers(slave, register_address, [value])

    def get_current_position(self, slave: int) -> int:
        """Retrieve the current position from registers."""
        registers = self.read_registers(slave, 64 * 16, 2)
        return int(combine_uint16_to_int32(registers)) if registers else 0

    def get_target_position(self, slave: int) -> int:
        """Retrieve the target position from registers."""
        registers = self.read_registers(slave, 64 * 612, 2)
        return int(combine_uint16_to_int32(registers)) if registers else 0

    @normalize_slaves
    def wait_for_target(self, slaves: Union[int, List[int]], timeout: int = 30) -> None:
        """Wait for the robots to reach their target positions."""
        start_time = time.time()
        previous_positions = {slave: [] for slave in slaves}
        target_positions = {slave: self.get_target_position(slave) for slave in slaves}

        while True:
            pause_slaves = self.get_pause(slaves)
            is_pause = any(pause_slaves.values())
            if is_pause:
                start_time = time.time()
            else:
                if time.time() - start_time > timeout:
                    self.logger.warning(f"Timeout: Slaves {slaves} did not reach the target position.")
                    break

            all_reached = True
            distance_status = []

            for slave in slaves:
                current_position = self.get_current_position(slave)
                distance = abs(target_positions[slave] - current_position)
                distance_status.append(f"{RED if pause_slaves[slave] else YELLOW}Slave {slave}: {distance}{END}")

                prev = previous_positions[slave]
                prev.append(current_position)
                previous_positions[slave] = prev[-5:]

                if len(prev) < 5 or len(set(prev)) > 1 or distance > 3:
                    all_reached = False

            print(f"\rWait: ({' | '.join(distance_status)}) {', is pause' if is_pause else ''}     ", end='')

            if all_reached:
                print()
                break

            if self.stop_waiting:
                break

            time.sleep(0.1)

    def read_register(self, slave):
        registers_data = hexss.control_robot.registers.copy()

        for name, register_info in registers_data.items():
            register_value = self.read_registers(slave_id=slave, address=register_info['address'], count=1)
            if register_value:
                register_info['value'] = register_value[0]

                if 'signals' in register_info:
                    for signal in register_info['signals']:
                        bit_value = (register_value[0] & (1 << signal['bit_position'])) != 0
                        signal['value'] = bit_value
            else:
                self.logger.error(f"Failed to read register {name} (Address: 0x{register_info['address']:04X})")

        return registers_data

    @normalize_slaves
    def servo(self, slaves, on: bool = True) -> None:
        self.logger.info(f'servo(on={on})')
        for slave in slaves:
            if on:
                self.set_bit(slave, 64 * 52 + 0, self.SERVO)
            else:
                self.reset_bit(slave, 64 * 52 + 0, self.SERVO)

    @normalize_slaves
    def alarm_reset(self, slaves) -> None:
        self.logger.info(f'alarm_reset(slave={slaves})')
        for slave in slaves:
            self.set_bit(slave, 64 * 52 + 0, self.ALARM_RESET)
            self.reset_bit(slave, 64 * 52 + 0, self.ALARM_RESET)

    @normalize_slaves
    def pause(self, slaves, pause: bool = True) -> None:
        self.logger.info(f'pause(slave={slaves}, pause={pause})')
        for slave in slaves:
            if pause:
                self.set_bit(slave, 64 * 52 + 0, self.PAUSE)
            else:
                self.reset_bit(slave, 64 * 52 + 0, self.PAUSE)

    @normalize_slaves
    def get_pause(self, slaves):
        o = {}
        for slave in slaves:
            o[slave] = self.read_bit(slave, 64 * 52 + 0, self.PAUSE)
        return o

    @normalize_slaves
    def home(self, slaves: Union[int, List[int]], alarm_reset=False, on_servo=False, unpause=False) -> None:
        self.logger.info(f'home(slave={slaves})')
        for slave in slaves:
            if alarm_reset:
                self.set_bit(slave, 64 * 52 + 0, self.ALARM_RESET)
                self.reset_bit(slave, 64 * 52 + 0, self.ALARM_RESET)
            if on_servo:
                self.reset_bit(slave, 64 * 52 + 0, self.SERVO)
                self.set_bit(slave, 64 * 52 + 0, self.SERVO)
            if unpause:
                self.set_bit(slave, 64 * 52 + 0, self.PAUSE)
                self.reset_bit(slave, 64 * 52 + 0, self.PAUSE)

            self.set_bit(slave, 64 * 52 + 0, self.HOME)
            self.reset_bit(slave, 64 * 52 + 0, self.HOME)

    def jog(self, slave: int, direction='+') -> None:
        if direction == '+':
            self.logger.info(f'jog(slave={slave}, direction:{direction})')
            self.set_bit(slave, 64 * 52 + 1, self.JOG_PLUS)
        elif direction == '-':
            self.logger.info(f'jog(slave={slave}, direction:{direction})')
            self.set_bit(slave, 64 * 52 + 1, self.JOG_MINUS)
        else:
            self.reset_bit(slave, 64 * 52 + 1, self.JOG_PLUS)
            self.reset_bit(slave, 64 * 52 + 1, self.JOG_MINUS)

    def move(self, slave, target_position: int):
        self.write_registers(slave, 64 * 612 + 0, split_int32_to_uint16(target_position).tolist())

    def move_multiple_slaves(self, slave_to_value_map: dict[int, int]) -> None:
        for slave, target_position in slave_to_value_map.items():
            self.move(slave, target_position)

    @normalize_slaves
    def move_to(self, slaves: Union[int, list], row: int) -> None:
        self.logger.info(f'move_to(slaves={slaves} ,row={row})')
        for slave in slaves:
            self.write_to_register(slave, 64 * 608 + 0, row)

    def read_table_data(self, slave: int) -> pd.DataFrame:
        try:
            all_positions = []
            start_address = 4096
            num_registers = 16
            total_rows = 64

            for i in range(total_rows):
                row_address = start_address + i * num_registers
                response = self.client.read_input_registers(
                    address=row_address,
                    count=num_registers,
                    slave=slave
                )

                if response.isError():
                    self.logger.error(f"Error reading table data from slave {slave}, row {i}")
                    continue

                data_dict = {f"{j}": val for j, val in enumerate(response.registers)}
                all_positions.append(data_dict)
            self.table_data = pd.DataFrame(all_positions) if all_positions else pd.DataFrame()
            return self.table_data

        except Exception as e:
            self.logger.exception(f"Exception occurred while reading table data: {e}")
            return pd.DataFrame()

    def write_table_data(self, slave: int, table_data: pd.DataFrame):
        try:
            start_address = 4096
            num_registers = 16

            for row in range(len(self.table_data)):
                if self.table_data.iloc[row].values.tolist() != table_data.iloc[row].values.tolist():
                    print(f'{row}-->{table_data.iloc[row].values.tolist()}')

                    row_address = start_address + row * num_registers
                    response = self.client.write_registers(
                        address=row_address,
                        values=table_data.iloc[row].values.tolist(),
                        slave=slave
                    )
            self.table_data = table_data

        except Exception as e:
            self.logger.exception(f"Exception occurred while writing table data: {e}")


if __name__ == '__main__':
    from hexss.threading import Multithread


    def move(robot):
        robot.home([1, 2], alarm_reset=True, on_servo=True, unpause=True)
        robot.wait_for_target([1, 2])

        positions = [
            (10765, 1745),
            (40000, 1976),
            (31559, 1214),
            (5587, 2934),
            (-1, -1)
        ]

        for i, (v1, v2) in enumerate(positions):
            print(f"Moving {i}")
            robot.move(1, v1)
            robot.move(2, v2)
            robot.wait_for_target([1, 2])


    def interrupt(robot):
        t1 = datetime.now()
        step = 0
        while True:
            if step == 0:
                if (datetime.now() - t1).total_seconds() > 7.8:
                    robot.pause([1], pause=True)
                    step = 1

            if step == 1:
                if (datetime.now() - t1).total_seconds() > 20:
                    robot.pause([1], pause=False)
                    step = 2


    def get_mem(robot):
        robot.set_bit(1, 64 * 52 + 0, robot.HOME)
        time.sleep(1)
        memory_pause = robot.read_memories(1)
        time.sleep(1)

        robot.reset_bit(1, 64 * 52 + 0, robot.HOME)
        time.sleep(1)
        memory_unpause = robot.read_memories(1)
        time.sleep(1)

        for i, (p, u) in enumerate(zip(memory_pause, memory_unpause)):
            if p != u:
                print(i)
                print(p)
                print(u)
                print()


    comport = get_comport('ATEN USB to Serial', 'USB-Serial Controller')
    robot = Robot(comport, baudrate=38400)

    m = Multithread()
    m.add_func(move, args=(robot,))
    m.add_func(interrupt, args=(robot,))

    m.start()

    m.join()
