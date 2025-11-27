import socket
from typing import List, Sequence


class MCClient:
    # support
    # FX3U-16M + FX3U-ENET-L  (MC protocol A-compatible 1E, ASCII)
    DEV_D = "4420"
    DEV_X = "5820"
    DEV_Y = "5920"

    def __init__(self, ip: str, port: int, debug=False) -> None:
        self.ip = ip
        self.port = port
        self.debug = debug
        self.sock = None
        self._connect()

    def _connect(self):
        """Establish the connection. Close old one if exists."""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

        if self.debug: print(f"Connecting to {self.ip}:{self.port}...")
        self.sock = socket.create_connection((self.ip, self.port), timeout=2.0)

    def close(self):
        """Clean up socket explicitly."""
        if self.sock:
            self.sock.close()
            self.sock = None

    def _exchange(self, cmd_hex: str) -> str:
        if self.debug: print(f"\nTX: {cmd_hex}")
        try:
            self.sock.sendall(cmd_hex.encode("ascii"))
            data = self.sock.recv(4096)
        except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError) as e:
            if self.debug: print(f"Socket error ({e}), reconnecting...")
            self._connect()
            self.sock.sendall(cmd_hex.encode("ascii"))
            data = self.sock.recv(4096)

        if self.debug: print("Raw response:", data)
        rx = data.decode("ascii", errors="ignore").strip()
        if self.debug: print("Decoded     :", rx)
        return rx

    def _parse_mc_payload(self, rx: str, expect_ok: bool = True) -> str:
        if len(rx) < 4:
            raise RuntimeError(f"Response too short: {rx!r}")
        subheader = rx[0:2]
        end_code = rx[2:4]
        if self.debug: print(f"MC header: subheader={subheader}, end_code={end_code}")
        if expect_ok and end_code != "00":
            raise RuntimeError(f"MC protocol error, end_code=0x{end_code}, raw={rx}")
        return rx[4:]

    def _build_1e_cmd(self, cmd: int, dev_code: str, head: int, points: int) -> str:
        header = f"{cmd:02X}FF000A"
        head_hex = f"{head & 0xFFFFFFFF:08X}"
        lo = points & 0xFF
        hi = (points >> 8) & 0xFF
        pts_hex = f"{lo:02X}{hi:02X}"
        return header + dev_code + head_hex + pts_hex

    def _execute_cmd(self, cmd: int, dev_code: str, head: int, points: int, data_field: str | None = None) -> str:
        cmd_hex = self._build_1e_cmd(cmd, dev_code, head, points)
        if data_field:
            cmd_hex += data_field
        rx = self._exchange(cmd_hex)
        payload = self._parse_mc_payload(rx, expect_ok=True)
        return payload

    def _read_bits(self, dev_code: str, head: int, points: int) -> List[int]:
        if points <= 0: return []
        payload = self._execute_cmd(0x00, dev_code, head, points)
        if len(payload) < points:
            raise RuntimeError(f"Not enough bit data, payload={payload!r}")
        return [1 if c == "1" else 0 for c in payload[:points]]

    def _write_bits(self, dev_code: str, head: int, values: Sequence[int | bool]) -> None:
        vals = [1 if bool(v) else 0 for v in values]
        points = len(vals)
        if points == 0: return
        data_chars = "".join("1" if v else "0" for v in vals)
        if points % 2 == 1: data_chars += "0"
        self._execute_cmd(0x02, dev_code, head, points, data_field=data_chars)

    def read_x(self, head: int, points: int) -> List[int]:
        return self._read_bits(self.DEV_X, head, points)

    def read_y(self, head: int, points: int) -> List[int]:
        return self._read_bits(self.DEV_Y, head, points)

    def write_y(self, head: int, values: Sequence[int | bool] | int | bool) -> None:
        if isinstance(values, (int, bool)):
            vals_seq = [values]
        else:
            vals_seq = list(values)
        self._write_bits(self.DEV_Y, head, vals_seq)

    def read_d(self, head: int, words: int = 1) -> List[int]:
        if words <= 0: return []
        payload = self._execute_cmd(0x01, self.DEV_D, head, words)
        vals: List[int] = []
        for i in range(words):
            s = payload[i * 4: i * 4 + 4]
            vals.append(int(s, 16))
        return vals

    def write_d(self, head: int, values: Sequence[int] | int) -> None:
        if isinstance(values, int): values = [values]
        words = len(values)
        if words <= 0: return
        data_field = "".join(f"{v & 0xFFFF:04X}" for v in values)
        self._execute_cmd(0x03, self.DEV_D, head, words, data_field=data_field)

    def _parse_addr(self, addr: str):
        """
        Convert 'X0', 'Y5', 'D10' into (dev_code, head, is_bit)
        """
        addr = addr.strip().upper()

        if addr.startswith("X"):
            return self.DEV_X, int(addr[1:]), True
        elif addr.startswith("Y"):
            return self.DEV_Y, int(addr[1:]), True
        elif addr.startswith("D"):
            return self.DEV_D, int(addr[1:]), False
        else:
            raise ValueError(f"Unsupported address: {addr}")

    def read(self, addr: str, count: int = 1):
        dev, head, is_bit = self._parse_addr(addr)

        if is_bit:
            return self._read_bits(dev, head, count)
        else:
            return self.read_d(head, count)

    def write(self, addr: str, values):
        dev, head, is_bit = self._parse_addr(addr)

        if is_bit:
            if isinstance(values, (int, bool)):
                values = [values]
            return self._write_bits(dev, head, values)
        else:
            return self.write_d(head, values)
