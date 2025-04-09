import json
import time
from typing import Optional, Union, Any
import hexss

hexss.check_packages('pyserial', auto_install=True)

from hexss.constants.terminal_color import *
import serial
import serial.tools.list_ports


def get_comport(*args: str, verbose: bool = True) -> Optional[str]:
    """
    Detect and return an available COM port matching the given descriptions.

    Args:
        *args (str): Descriptions to match against port information (case-insensitive).
        verbose (bool): If True, displays detected ports and connection status.

    Returns:
        Optional[str]: The device path of the first matching COM port, or None if no match is found.

    Raises:
        ValueError: If no matching COM port is found based on descriptions.
    """
    ports = list(serial.tools.list_ports.comports())

    if verbose:
        if ports:
            print("Available COM Ports:")
            for port in ports:
                print(f" - {port.device}: {port.description}")
        else:
            print("No COM ports detected.")

    if args:
        for port in ports:
            if any(arg.lower() in port.description.lower() for arg in args):
                return port.device
        raise ValueError(f"No COM port found matching: {', '.join(args)}")

    return ports[0].device if ports else None


class Arduino:
    INPUT = 0
    OUTPUT = 1
    INPUT_PULLUP = 2
    LOW = 0
    HIGH = 1
    TOGGLE = 2

    def __init__(self, *args: str, baudrate: int = 9600, timeout: Optional[float] = 1.0) -> None:
        """
        Initialize the Arduino connection by automatically detecting a matching COM port.

        Args:
            *args (str): Descriptions that help identify the correct COM port.
            baudrate (int): Serial communication speed.
            timeout (Optional[float]): Timeout period for serial operations.

        Raises:
            ValueError: If no matching COM port is found.
            serial.SerialException: If the serial connection cannot be opened.
        """
        self.port: Optional[str] = get_comport(*args)
        if not self.port:
            raise ValueError(f"No matching COM port found for: {', '.join(args)}")

        try:
            self.serial = serial.Serial(self.port, baudrate=baudrate, timeout=timeout)
        except serial.SerialException as e:
            raise serial.SerialException(f"Failed to open serial connection on {self.port}: {e}")

        self.verbose: bool = False
        self.pin_status: dict[int, int] = {}

        print(f"{CYAN}Connected to: {self.port}{END}")

    def __enter__(self) -> "Arduino":
        """Enable usage with the 'with' statement."""
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Ensure the serial connection is closed when exiting the with-block."""
        self.close()

    def send(self, command: str) -> None:
        """
        Send a command string to the Arduino.

        Args:
            command (str): The command string to be sent.
        """
        if self.verbose:
            print(f"Sending command: {command}")
        self.serial.write(command.encode('utf-8'))

    def send_and_receive(self, command: str) -> dict:
        """
        Sends a command and waits for a newline-terminated JSON reply.

        Args:
            command (str): Command string to send.

        Returns:
            dict: The decoded JSON response.

        Raises:
            ValueError: If the received response is not valid JSON.
        """
        self.send(command)
        line = self.serial.readline().decode('utf-8').strip()
        try:
            response = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {line}\nError: {e}")
        return response

    def close(self) -> None:
        """
        Closes the serial connection.
        """
        if self.serial.is_open:
            self.serial.close()
            print(f"{CYAN}Serial port {self.port} closed.{END}")

    def echo(self, text: str) -> Optional[str]:
        """
        Sends an echo command to the Arduino and returns the echoed text.

        Args:
            text (str): The text to echo.

        Returns:
            Optional[str]: The response text if successful, else None.
        """
        try:
            response = self.send_and_receive(f"<echo,{text}>")
            return response.get('text')
        except Exception as e:
            if self.verbose:
                print(f"Echo command failed: {e}")
            return None

    def waiting_for_reply(self, max_wait: int = 30) -> None:
        """
        Waits until a valid echo reply is received from the Arduino.

        Args:
            max_wait (int): Maximum time to wait (in seconds) before giving up.

        Raises:
            TimeoutError: If no valid reply is received within max_wait seconds.
        """
        start_time = time.time()
        elapsed = 0
        while elapsed < max_wait:
            if self.echo('hi') == 'hi':
                return
            print(f"{YELLOW}Waiting for reply... {int(elapsed)}s{END}")
            time.sleep(1)
            elapsed = time.time() - start_time
        raise TimeoutError("No response from Arduino within the given wait time.")

    def pinMode(self, pin: int, mode: int) -> bool:
        """
        Sets the mode of a specific pin.

        Args:
            pin (int): The pin number.
            mode (int): The mode (e.g., INPUT (0), OUTPUT (1), INPUT_PULLUP (2)).

        Returns:
            bool: True if the Arduino confirmed the command; False otherwise.
        """
        response = self.send_and_receive(f"<pinMode,{pin},{mode}>")
        if response.get('command') == 'pinMode' and response.get('pin') == pin and response.get('mode') == mode:
            return True
        print(f"pinMode command failed or unexpected response: {response}")
        return False

    def digitalWrite(self, pin: int, value: int) -> bool:
        """
        Writes a digital value to a pin.

        Args:
            pin (int): The pin number.
            value (int): 0=LOW, 1=HIGH, 2=TOGGLE.

        Returns:
            bool: True if the command succeeded; otherwise False.
        """
        response = self.send_and_receive(f"<digitalWrite,{pin},{value}>")
        if response.get('command') == 'digitalWrite' and response.get('pin') == pin:
            return True
        print(f"digitalWrite command failed or unexpected response: {response}")
        return False

    def digitalRead(self, pin: int) -> int:
        """
        Reads a digital value from the specified pin.

        Args:
            pin (int): The pin number.

        Returns:
            int: The digital value read (0 or 1).

        Raises:
            ValueError: If the response from Arduino is invalid.
        """
        response = self.send_and_receive(f"<digitalRead,{pin}>")
        if response.get('command') == 'digitalRead' and 'value' in response:
            try:
                return int(response['value'])
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error parsing value from response: {response}\n{e}")
        raise ValueError(f"digitalRead command failed or returned unexpected response: {response}")

    def analogWrite(self, pin: int, value: int) -> bool:
        """
        Writes an analog value to the specified pin.

        Args:
            pin (int): The pin number.
            value (int): The analog value to write (range depends on Arduino model).

        Returns:
            bool: True if the command was acknowledged; else False.
        """
        response = self.send_and_receive(f"<analogWrite,{pin},{value}>")
        if response.get('command') == 'analogWrite' and response.get('pin') == pin:
            print(f"analogWrite successful on pin {pin} with value {value}")
            return True
        print(f"analogWrite command failed or unexpected response: {response}")
        return False

    def analogRead(self, pin: int) -> int:
        """
        Reads an analog value from the specified pin.

        Args:
            pin (int): The pin number.

        Returns:
            int: The analog value read.

        Raises:
            ValueError: If the response from Arduino is not as expected.
        """
        response = self.send_and_receive(f"<analogRead,{pin}>")
        if response.get('command') == 'analogRead' and 'value' in response:
            try:
                value = int(response['value'])
                print(f"analogRead pin {pin} returned {value}")
                return value
            except (ValueError, TypeError) as e:
                raise ValueError(f"Error parsing analog value: {response}\n{e}")
        raise ValueError(f"analogRead command failed or returned unexpected response: {response}")

    def is_rising_edge(self, pin: int) -> bool:
        """
        Checks if a digital pin experienced a rising edge (transition from LOW to HIGH).

        Args:
            pin (int): The pin number.

        Returns:
            bool: True if a rising edge is detected; otherwise False.
        """
        current_value = self.digitalRead(pin)
        previous_value = self.pin_status.get(pin, current_value)
        self.pin_status[pin] = current_value
        if previous_value == self.LOW and current_value == self.HIGH:
            return True
        return False

    def is_falling_edge(self, pin: int) -> bool:
        """
        Checks if a digital pin experienced a falling edge (transition from HIGH to LOW).

        Args:
            pin (int): The pin number.

        Returns:
            bool: True if a falling edge is detected; otherwise False.
        """
        current_value = self.digitalRead(pin)
        previous_value = self.pin_status.get(pin, current_value)
        self.pin_status[pin] = current_value
        if previous_value == self.HIGH and current_value == self.LOW:
            return True
        return False


if __name__ == "__main__":
    # Example 1
    ar = Arduino('Arduino', 'USB-SERIAL CH340')
    ar.waiting_for_reply(max_wait=5)
    ar.pinMode(13, ar.OUTPUT)
    for _ in range(10):
        ar.digitalWrite(13, ar.TOGGLE)
        val = ar.digitalRead(13)
        print(f"digitalRead(13): {val}")
        time.sleep(0.5)
    ar.close()

    # Example 2
    with Arduino('Arduino', 'USB-SERIAL CH340') as ar:
        ar.waiting_for_reply(max_wait=5)
        ar.pinMode(13, ar.OUTPUT)
        for _ in range(10):
            ar.digitalWrite(13, ar.TOGGLE)
            val = ar.digitalRead(13)
            print(f"digitalRead(13): {val}")
            time.sleep(0.5)
