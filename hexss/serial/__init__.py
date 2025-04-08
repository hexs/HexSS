from typing import List, Optional
import time
import hexss

hexss.check_packages('pyserial', auto_install=True)

import serial
import serial.tools.list_ports


def get_comport(*args: str, show_status: bool = True) -> Optional[str]:
    """
    Detect and return an available COM port matching the given descriptions.

    Args:
        *args: Strings to match against port descriptions (case-insensitive).
        show_status (bool): Whether to print the detected COM ports and connection status.

    Returns:
        Optional[str]: The device path of the first matching COM port, or None if no match is found.

    Raises:
        ValueError: If no matching COM port is found based on descriptions.
    """
    # Get the list of all available COM ports
    ports = list(serial.tools.list_ports.comports())

    # Optionally display available ports
    if show_status:
        if ports:
            print("Available COM Ports:")
            for port in ports:
                print(f"- {port.device}: {port.description}")
        else:
            print("No COM ports detected.")
        print()

    # Match ports to provided arguments (case-insensitive matching)
    if args:
        for port in ports:
            if any(arg.lower() in port.description.lower() for arg in args):
                if show_status:
                    print(f"Connected to: {port.device}")
                return port.device
        raise ValueError(f"No COM port found matching: {', '.join(args)}")


class Serial:
    """
    A utility class for accessing and communicating over a serial connection.
    """

    INPUT = 0
    OUTPUT = 1
    INPUT_PULLUP = 2

    LOW = 0
    HIGH = 1

    def __init__(self, *args: str, baudrate: int = 9600, timeout: Optional[float] = 1.0):
        """
        Initialize and connect to a serial device.

        Args:
            *args (str): Strings to match against port descriptions (case-insensitive).
            baudrate (int): The baudrate for the serial communication. Defaults to 9600.
            timeout (Optional[float]): Timeout in seconds for read/write operations. Defaults to 1.0.

        Raises:
            ValueError: If no matching COM port is found.
            serial.SerialException: If the serial connection cannot be established.
        """
        self.port = get_comport(*args)
        if not self.port:
            raise ValueError(f"No matching COM port found for: {', '.join(args)}")

        try:
            self.serial = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
        except serial.SerialException as e:
            raise serial.SerialException(f"Failed to open serial connection on {self.port}: {e}")
        self.show_status = True

    def write(self, text: str) -> None:
        if self.serial.is_open:
            self.serial.write(text.encode())
            if self.show_status:
                print(f"Written to {self.port}: {text}")
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def read(self, size: int = 1) -> str:
        if self.serial.is_open:
            data = self.serial.read(size)
            return data.decode()
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def readline(self) -> str:
        if self.serial.is_open:
            line = self.serial.readline()
            return line.decode().strip()
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def send_and_receive(self, text: str) -> str:
        self.write(text)
        response = self.readline()
        if self.show_status:
            print(f"Received from {self.port}: {response}")
        return response

    def close(self) -> None:
        """
        Close the serial connection.
        """
        if self.serial.is_open:
            self.serial.close()
            print(f"Serial port {self.port} closed.")

    def pinMode(self, pin: int, mode: int) -> None:
        """
        Set the mode of a pin.

        Args:
            pin (int): The pin number.
            mode (int): The mode (INPUT, OUTPUT, INPUT_PULLUP).
        """
        self.send_and_receive(f"<pinMode,{pin},{mode}>")

    def digitalWrite(self, pin: int, value: bool) -> None:
        """
        Set the value of a pin.

        Args:
            pin (int): The pin number.
            value (bool): The value (HIGH or LOW).
        """
        self.send_and_receive(f"<digitalWrite,{pin},{value}>")

    def digitalRead(self, pin: int) -> bool:
        """
        Read the value of a pin.

        Args:
            pin (int): The pin number.

        Returns:
            bool: The value (HIGH or LOW).
        """
        return int(self.send_and_receive(f"<digitalRead,{pin}>"))

    def analogWrite(self, pin: int, value: int) -> None:
        """
        Set the PWM value of a pin.

        Args:
            pin (int): The pin number.
            value (int): The PWM value (0-255).
        """
        self.send_and_receive(f"<analogWrite,{pin},{value}>")

    def analogRead(self, pin: int) -> int:
        """
        Read the analog value of a pin.

        Args:
            pin (int): The pin number.

        Returns:
            int: The analog value (0-1023).
        """
        return int(self.send_and_receive(f"<analogRead,{pin}>"))


if __name__ == "__main__":
    ser = Serial('Arduino Uno')
    time.sleep(5)
    for _ in range(3):
        ser.write('<setLED,relay,0,0,0,255>')
        time.sleep(0.5)
        ser.write('<clsLED>')
        time.sleep(0.5)

    res = ser.send_and_receive('<PINB>')
    print(res)  # PINB=40
    v = res.split('=')[1]
    if v.isdigit():
        if int(v) & 0b100:
            print('on')
        else:
            print('off')
