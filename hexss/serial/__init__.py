import serial.tools.list_ports
from typing import List, Optional


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
