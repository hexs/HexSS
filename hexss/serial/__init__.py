import json
from typing import Optional
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
    # If no arguments are provided, return the first available port.
    return ports[0].device if ports else None


class Serial:
    """
    A utility class for accessing and communicating over a serial connection.
    """

    def __init__(self, *args: str, baudrate: int = 9600, timeout: Optional[float] = 1.0) -> None:
        self.port = get_comport(*args)
        if not self.port:
            raise ValueError(f"No matching COM port found for: {', '.join(args)}")

        try:
            self.serial = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
        except serial.SerialException as e:
            raise serial.SerialException(f"Failed to open serial connection on {self.port}: {e}")
        self.show_status = True

    def write(self, text: str) -> None:
        """
        Writes a string to the serial port.
        """
        if self.serial.is_open:
            self.serial.write(text.encode())
            if self.show_status:
                print(f"Written to {self.port}: {text}")
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def read(self, size: int = 1) -> str:
        """
        Reads a specified number of bytes from the serial port.
        """
        if self.serial.is_open:
            data = self.serial.read(size)
            return data.decode(errors='ignore')
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def readline(self) -> str:
        """
        Reads one line (until newline) from the serial port.
        """
        if self.serial.is_open:
            line = self.serial.readline()
            return line.decode(errors='ignore').strip()
        else:
            raise serial.SerialException(f"Serial port {self.port} is not open.")

    def send_and_receive(self, text: str) -> str:
        """
        Sends a text command over serial and returns the response.
        """
        self.write(text)
        response = self.readline()
        if self.show_status:
            print(f"Received from {self.port}: {response}")
        return response

    def close(self) -> None:
        """
        Closes the serial connection.
        """
        if self.serial.is_open:
            self.serial.close()
            print(f"Serial port {self.port} closed.")


class Arduino(Serial):
    INPUT = 0
    OUTPUT = 1
    INPUT_PULLUP = 2
    LOW = 0
    HIGH = 1

    def echo(self, text):
        return self.send_and_receive(f"<echo,{text}>")

    def waiting_for_reply(self):
        while True:
            try:
                res = (json.loads(self.echo('hi')))
                if res.get('text') == 'hi':
                    break
            except:
                ...
            print('waiting_for_reply')
            time.sleep(1)

    def pinMode(self, pin: int, mode: int) -> None:
        """
        Sets the mode of the specified pin.
        """
        print(self.send_and_receive(f"<pinMode,{pin},{mode}>"))

    def digitalWrite(self, pin: int, value: int) -> None:
        """
        Writes a digital value to the specified pin.
        """
        print(self.send_and_receive(f"<digitalWrite,{pin},{value}>"))

    def digitalRead(self, pin: int) -> bool:
        """
        Reads and returns the digital value (HIGH/LOW) from the specified pin.
        """
        response = self.send_and_receive(f"<digitalRead,{pin}>")
        return bool(int(response))

    def analogWrite(self, pin: int, value: int) -> None:
        """
        Writes an analog (PWM) value (0–255) to the specified pin.
        """
        self.send_and_receive(f"<analogWrite,{pin},{value}>")

    def analogRead(self, pin: int) -> int:
        """
        Reads and returns the analog value (0–1023) from the specified pin.
        """
        response = self.send_and_receive(f"<analogRead,{pin}>")
        return int(response)


if __name__ == "__main__":
    ar = Arduino("USB-SERIAL CH340")
    ar.show_status = False
    ar.waiting_for_reply()

    ar.show_status = True
    # Set pin 13 as OUTPUT and toggle it 10 times.
    ar.pinMode(13, ar.OUTPUT)
    for _ in range(10):
        ar.digitalWrite(13, ar.HIGH)
        time.sleep(0.5)
        ar.digitalWrite(13, ar.LOW)
        time.sleep(0.5)
    ar.close()
