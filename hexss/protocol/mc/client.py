import socket
import re
import threading
import time
from typing import List, Union, Dict, Any, Tuple, Optional, Callable

from hexss.protocol.mc.event import Event, Events


class MCTag:
    def __init__(self, client: 'MCClient', address: str, name: str):
        self._client = client
        self.address = address
        self.name = name
        self.value = 0
        self.last_update = 0.0
        self.last_change = 0.0

    def set(self, value: Union[int, bool]):
        self._client.write(self.address, value)

    def on(self): self.set(1)

    def off(self): self.set(0)

    def toggle(self):
        self.set(0 if self.value else 1)

    def __repr__(self):
        return f"<MCTag {self.name} ({self.address}): {self.value}>"


class MCClient:
    DEV_X = "5820"
    DEV_Y = "5920"
    DEV_M = "4D20"
    DEV_S = "5320"
    DEV_TS = "5453"
    DEV_CS = "4353"
    DEV_D = "4420"
    DEV_TN = "544E"
    DEV_CN = "434E"

    def __init__(self, ip: str, port: int, debug=False) -> None:
        self.ip = ip
        self.port = port
        self.debug = debug
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

        self._tags: Dict[str, MCTag] = {}
        self._tags_by_name: Dict[str, MCTag] = {}
        self._callbacks: List[Callable[[Event], None]] = []
        self._simultaneous_listeners: List[Dict] = []
        self._event_history: List[Tuple[float, Event]] = []

        self._running = False
        self._connect()

    def _connect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        try:
            if self.debug: print(f"[MC] Connecting to {self.ip}:{self.port}...")
            self.sock = socket.create_connection((self.ip, self.port), timeout=2.0)
        except (socket.error, OSError) as e:
            if self.debug: print(f"[MC] Connection failed: {e}")
            self.sock = None

    def close(self):
        self._running = False
        if self.sock:
            self.sock.close()
            self.sock = None

    def _exchange(self, cmd_hex: str) -> str:
        with self._lock:
            if self.sock is None:
                self._connect()
                if self.sock is None: raise ConnectionError("PLC offline")
            try:
                self.sock.sendall(cmd_hex.encode("ascii"))
                data = self.sock.recv(4096).decode("ascii", errors="ignore").strip()
                if self.debug: print(f"TX: {cmd_hex} | RX: {data}")
                return data
            except (socket.error, OSError):
                if self.debug: print("[MC] Socket error, reconnecting...")
                self._connect()
                if self.sock:
                    return self._exchange(cmd_hex)
                raise ConnectionError("Lost connection to PLC")

    def _execute(self, cmd: int, dev: str, head: int, pts: int, data: str = "") -> str:
        header = f"{cmd:02X}FF000A"
        head_hex = f"{head & 0xFFFFFFFF:08X}"
        pts_hex = f"{pts & 0xFF:02X}{(pts >> 8) & 0xFF:02X}"
        rx = self._exchange(header + dev + head_hex + pts_hex + data)
        if len(rx) < 4: raise RuntimeError(f"Short response: {rx}")
        if rx[2:4] != "00": raise RuntimeError(f"PLC Error: 0x{rx[2:4]}")
        return rx[4:]

    def _parse_addr(self, addr: str) -> Tuple[str, int, bool]:
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
            return [int(payload[i * 4:i * 4 + 4], 16) for i in range(count)]

    def write(self, addr: str, values: Union[int, bool, List[int], List[bool]]):
        dev, head, is_bit = self._parse_addr(addr)
        if not isinstance(values, list): values = [values]
        if is_bit:
            data = "".join("1" if v else "0" for v in values)
            if len(data) % 2: data += "0"
            self._execute(0x02, dev, head, len(values), data)
        else:
            data = "".join(f"{v & 0xFFFF:04X}" for v in values)
            self._execute(0x03, dev, head, len(values), data)

    def add_tag(self, addr: str, name: Optional[str] = None):
        name = name or addr
        new_tag = MCTag(self, addr, name)
        self._tags[addr] = new_tag
        self._tags_by_name[name] = new_tag

    def get(self, key: str) -> MCTag:
        return self._tags_by_name.get(key) or self._tags.get(key) or (_ for _ in ()).throw(
            KeyError(f"Tag {key} not found"))

    def get_tags(self) -> Dict[str, MCTag]:
        return self._tags

    def on_change(self, callback: Callable[[Event], None]):
        self._callbacks.append(callback)

    def simultaneous_events(self, callback: Callable[[Events], None], duration: float):
        self._simultaneous_listeners.append({'callback': callback, 'duration': duration})

    def _trigger_callbacks(self, address: str, name: str, value: Any):
        event = Event(address, name, value)
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                print(f"[Callback Error] {e}")

        if not self._simultaneous_listeners:
            return

        now = time.time()
        self._event_history.append((now, event))
        max_duration = max(l['duration'] for l in self._simultaneous_listeners)
        self._event_history = [ev for ev in self._event_history if now - ev[0] <= max_duration]
        for listener in self._simultaneous_listeners:
            dur = listener['duration']
            cb = listener['callback']
            relevant_events = [ev[1] for ev in self._event_history if now - ev[0] <= dur]
            if relevant_events:
                events_obj = Events(relevant_events)
                try:
                    cb(events_obj)
                except Exception as e:
                    print(f"[Simultaneous Callback Error] {e}")

    def auto_update(self, interval: float = 0):
        self._running = True

        def updater():
            while self._running:
                for addr in list(self._tags.keys()):
                    try:
                        tag = self._tags[addr]
                        val = self.read(addr, 1)[0]
                        if tag.value != val:
                            tag.value = val
                            self._trigger_callbacks(tag.address, tag.name, val)
                            tag.last_change = time.time()
                        tag.last_update = time.time()

                    except Exception as e:
                        if self.debug: print(f"Error updating {addr}: {e}")
                if interval > 0:
                    time.sleep(interval)

        t = threading.Thread(target=updater, daemon=True)
        t.start()

    def start_server(self, host="0.0.0.0", port=2006):
        import hexss.protocol.mc.server
        print(f"[System] Starting server at http://{host}:{port}")
        threading.Thread(
            target=hexss.protocol.mc.server.run,
            args=({'host': host, 'port': port, 'client': self},),
            daemon=True
        ).start()
