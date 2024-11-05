import serial.tools.list_ports


def get_comport(*args: str, show_status=True) -> str:
    """
    Detect and return an available COM port matching the given descriptions.

    Args:
        *args: Strings to match against port descriptions (case-insensitive).

    Returns:
        str: The device path of the first matching COM port.

    Raises:
        ValueError: If no suitable COM port is found matching the given descriptions,
                    or if no COM ports are available when no arguments are provided.
    """
    ports = list(serial.tools.list_ports.comports())
    if show_status:
        for port in ports:
            print(f"Found port: {port.device} - {port.description}")
        print()

    if args:
        for port in ports:
            if any(arg.lower() in port.description.lower() for arg in args):
                if show_status:
                    print(f"Connect to: {port.device}")
                return port.device
        raise ValueError(f"No COM port found matching: {', '.join(args)}")
    else:
        if ports:
            if show_status:
                print(f"Connect to: {ports[0].device}")
            return ports[0].device
        else:
            raise ValueError("No COM ports available")


if __name__ == '__main__':
    port = get_comport('ATEN USB to Serial', 'USB-Serial Controller')
