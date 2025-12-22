import socket
import re
from typing import List, Sequence, Union


class MCClient:
    """
    Supports: X, Y, M, S, T, C, D, TN, CN
    """
    # Device Codes (1E ASCII)
    DEV_X = "5820"  # Input (Bit) - Octal
    DEV_Y = "5920"  # Output (Bit) - Octal
    DEV_M = "4D20"  # Internal Relay (Bit) - Decimal
    DEV_S = "5320"  # State (Bit) - Decimal
    DEV_TS = "5453"  # Timer Contact (Bit) - Decimal
    DEV_CS = "4353"  # Counter Contact (Bit) - Decimal
    DEV_D = "4420"  # Data Register (Word) - Decimal
    DEV_TN = "544E"  # Timer Current Value (Word) - Decimal
    DEV_CN = "434E"  # Counter Current Value (Word) - Decimal

    def __init__(self, ip: str, port: int, debug=False) -> None:
        self.ip, self.port, self.debug = ip, port, debug
        self.sock = None
        self._connect()

    def _connect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        if self.debug: print(f"Connecting to {self.ip}:{self.port}...")
        self.sock = socket.create_connection((self.ip, self.port), timeout=2.0)

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _exchange(self, cmd_hex: str) -> str:
        try:
            self.sock.sendall(cmd_hex.encode("ascii"))
            data = self.sock.recv(4096).decode("ascii", errors="ignore").strip()
            if self.debug: print(f"TX: {cmd_hex} | RX: {data}")
            return data
        except (socket.error, OSError):
            self._connect()
            return self._exchange(cmd_hex)

    def _execute(self, cmd: int, dev: str, head: int, pts: int, data: str = "") -> str:
        # Header: Cmd(2) + PC No(FF) + Monitoring Timer(000A)
        header = f"{cmd:02X}FF000A"
        head_hex = f"{head & 0xFFFFFFFF:08X}"
        # Points: Lo-Byte Hi-Byte format (e.g. 0001 -> 0100)
        pts_hex = f"{pts & 0xFF:02X}{(pts >> 8) & 0xFF:02X}"
        rx = self._exchange(header + dev + head_hex + pts_hex + data)

        if len(rx) < 4:
            raise RuntimeError(f"Short response: {rx}")
        if rx[2:4] != "00":
            raise RuntimeError(f"PLC Error Code: 0x{rx[2:4]} (Device: {dev}, Addr: {head})")
        return rx[4:]

    def _parse_addr(self, addr: str):
        m = re.match(r"([A-Z]+)(\d+)", addr.upper())
        if not m: raise ValueError(f"Invalid Address: {addr}")
        prefix, val_str = m.groups()

        if prefix == "X":  return self.DEV_X, int(val_str, 8), True
        if prefix == "Y":  return self.DEV_Y, int(val_str, 8), True
        if prefix == "M":  return self.DEV_M, int(val_str), True
        if prefix == "S":  return self.DEV_S, int(val_str), True
        if prefix == "T":  return self.DEV_TS, int(val_str), True
        if prefix == "C":  return self.DEV_CS, int(val_str), True
        if prefix == "D":  return self.DEV_D, int(val_str), False
        if prefix == "TN": return self.DEV_TN, int(val_str), False
        if prefix == "CN": return self.DEV_CN, int(val_str), False
        raise ValueError(f"Device {prefix} not supported.")

    def read(self, addr: str, count: int = 1) -> List[int]:
        dev, head, is_bit = self._parse_addr(addr)
        payload = self._execute(0x00 if is_bit else 0x01, dev, head, count)

        if is_bit:
            return [1 if c == '1' else 0 for c in payload[:count]]
        else:
            return [int(payload[i * 4: i * 4 + 4], 16) for i in range(count)]

    def write(self, addr: str, values: Union[int, bool, List[int], List[bool]]):
        dev, head, is_bit = self._parse_addr(addr)
        if not isinstance(values, list): values = [values]

        if is_bit:
            data = "".join("1" if v else "0" for v in values)
            if len(data) % 2: data += "0"  # ASCII 1E requires even length
            self._execute(0x02, dev, head, len(values), data)
        else:
            data = "".join(f"{v & 0xFFFF:04X}" for v in values)
            self._execute(0x03, dev, head, len(values), data)
