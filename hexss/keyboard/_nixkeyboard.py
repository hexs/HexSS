import time
import threading
import struct
from ._nixcommon import EV_KEY, aggregate_devices, ensure_root, make_uinput, EV_SYN
from .key_mappings import KEY_MAPPINGS, EXTENDED_KEYS

E0_MAP = {
    0xE01C: 96,  # KEY_KPENTER
    0xE01D: 97,  # KEY_RIGHTCTRL
    0xE035: 98,  # KEY_KPSLASH
    0xE037: 99,  # KEY_SYSRQ
    0xE038: 100,  # KEY_RIGHTALT
    0xE047: 102,  # KEY_HOME
    0xE048: 103,  # KEY_UP
    0xE049: 104,  # KEY_PAGEUP
    0xE04B: 105,  # KEY_LEFT
    0xE04D: 106,  # KEY_RIGHT
    0xE04F: 107,  # KEY_END
    0xE050: 108,  # KEY_DOWN
    0xE051: 109,  # KEY_PAGEDOWN
    0xE052: 110,  # KEY_INSERT
    0xE053: 111,  # KEY_DELETE
    0xE05B: 125,  # KEY_LEFTMETA
    0xE05C: 126,  # KEY_RIGHTMETA
    0xE05D: 127,  # KEY_COMPOSE
}

REV_E0_MAP = {v: k for k, v in E0_MAP.items()}

SCAN_CODES = {}
CHAR_TO_CODE_SHIFT = {}

for scancode, data in KEY_MAPPINGS.items():
    linux_code = scancode
    if scancode >= 0xE000:
        linux_code = E0_MAP.get(scancode, scancode & 0xFF)

    names = data['name']
    for name in names:
        SCAN_CODES[name.lower()] = linux_code

    if len(names) >= 1:
        base_name = names[0]
        if len(base_name) == 1:
            CHAR_TO_CODE_SHIFT[base_name.lower()] = (linux_code, False)
        for name in names[1:]:
            if len(name) == 1:
                CHAR_TO_CODE_SHIFT[name] = (linux_code, True)

for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if char.lower() in CHAR_TO_CODE_SHIFT:
        code, _ = CHAR_TO_CODE_SHIFT[char.lower()]
        CHAR_TO_CODE_SHIFT[char] = (code, True)


class keyboard:
    active_keys = {}
    _uinput_device = None
    _lock = threading.Lock()

    @classmethod
    def _get_uinput(cls):
        with cls._lock:
            if cls._uinput_device is None:
                ensure_root()
                cls._uinput_device = make_uinput()
            return cls._uinput_device

    @classmethod
    def _write_event(cls, type, code, value):
        device = cls._get_uinput()
        integer, fraction = divmod(time.time(), 1)
        seconds = int(integer)
        microseconds = int(fraction * 1e6)
        event_bin_format = 'llHHI'
        data_event = struct.pack(event_bin_format, seconds, microseconds, type, code, value)
        sync_event = struct.pack(event_bin_format, seconds, microseconds, EV_SYN, 0, 0)
        device.write(data_event + sync_event)
        device.flush()

    @classmethod
    def press(cls, hotkey: str):
        hotkey = hotkey.lower()
        if hotkey in SCAN_CODES:
            if cls.active_keys.get(hotkey, False):
                return
            cls.active_keys[hotkey] = True
            code = SCAN_CODES[hotkey]
            cls._write_event(EV_KEY, code, 1)
        else:
            print(f"[Error] Unknown key: {hotkey}")

    @classmethod
    def release(cls, hotkey: str):
        hotkey = hotkey.lower()
        if hotkey in SCAN_CODES:
            cls.active_keys[hotkey] = False
            code = SCAN_CODES[hotkey]
            cls._write_event(EV_KEY, code, 0)
        else:
            print(f"[Error] Unknown key: {hotkey}")

    @classmethod
    def send(cls, hotkey_str: str, do_press: bool = True, do_release: bool = True):
        hotkey_str = hotkey_str.replace(' ', '').lower()
        if '++' in hotkey_str:
            hotkey_str = hotkey_str.replace('++', '+plus_key')
            keys = ['+' if k == 'plus_key' else k for k in hotkey_str.split('+')]
        elif hotkey_str == '+':
            keys = ['+']
        else:
            keys = hotkey_str.split('+')

        for k in keys:
            if k not in SCAN_CODES:
                print(f"[Error] Unknown key: {k}")
                return

        if do_press:
            for k in keys:
                code = SCAN_CODES[k]
                cls._write_event(EV_KEY, code, 1)
                time.sleep(0.01)
        if do_press and do_release:
            time.sleep(0.05)
        if do_release:
            for k in reversed(keys):
                code = SCAN_CODES[k]
                cls._write_event(EV_KEY, code, 0)
                time.sleep(0.01)

    @classmethod
    def write(cls, text: str, interval: float = 0.02):
        for ch in text:
            if ch == '\n':
                cls.send('enter')
            elif ch == '\t':
                cls.send('tab')
            elif ch == '\b':
                cls.send('backspace')
            elif ch == '\r':
                continue
            else:
                if ch in CHAR_TO_CODE_SHIFT:
                    code, shift = CHAR_TO_CODE_SHIFT[ch]
                    if shift: cls._write_event(EV_KEY, 42, 1)  # LSHIFT
                    cls._write_event(EV_KEY, code, 1)
                    cls._write_event(EV_KEY, code, 0)
                    if shift: cls._write_event(EV_KEY, 42, 0)
                else:
                    # For non-ASCII, we don't have a good way via uinput without layout knowledge.
                    # On Windows, it uses KEYEVENTF_UNICODE. Linux doesn't have an equivalent in uinput.
                    pass
            time.sleep(interval)


class Key:
    def __init__(self, vk, scancode, unicode_char, mod=0, flags=0):
        self.vk = vk
        self.unicode = unicode_char
        self.mod = mod
        self.scancode = scancode

        mapping = KEY_MAPPINGS.get(self.scancode)
        if mapping:
            self.name = mapping['name'][0]
            if self.vk is None:
                self.vk = mapping.get('vk')
        else:
            self.name = f"UNKNOWN_{self.scancode}"

        if self.vk and 65 <= self.vk <= 90:
            self.key = self.vk + 32
        else:
            self.key = self.vk or 0

    def __str__(self):
        unicode_str = repr(self.unicode) if self.unicode else "None"
        return (f"<Key(name: {self.name}, unicode: {unicode_str}, key: {self.key}, mod: {self.mod}, "
                f"scancode: {self.scancode}, VK:{self.vk})>")


class Listener(threading.Thread):
    def __init__(self, on_press=None, on_release=None, suppress=False):
        super().__init__()
        self.daemon = True
        self.on_press = on_press
        self.on_release = on_release
        self.suppress = suppress
        self._stop_event = threading.Event()
        self.mod_state = 0

    def run(self):
        ensure_root()
        device = aggregate_devices('keyboard')

        while not self._stop_event.is_set():
            # aggregate_devices returns an AggregatedEventDevice which uses a queue.
            # read_event() blocks on the queue.
            try:
                # We can't easily timeout on read_event if it's blocking on a queue
                # unless we modify AggregatedEventDevice.
                # But since it's a daemon thread, it's okay for now.
                time_val, type_val, code, value, device_id = device.read_event()
            except:
                break

            if type_val == EV_KEY:
                is_down = (value != 0)

                # Update mod_state (matching Windows bits)
                if code == 42:  # LSHIFT
                    if is_down:
                        self.mod_state |= 1
                    else:
                        self.mod_state &= ~1
                elif code == 54:  # RSHIFT
                    if is_down:
                        self.mod_state |= 2
                    else:
                        self.mod_state &= ~2
                elif code == 29:  # LCTRL
                    if is_down:
                        self.mod_state |= 64
                    else:
                        self.mod_state &= ~64
                elif code == 97:  # RCTRL
                    if is_down:
                        self.mod_state |= 128
                    else:
                        self.mod_state &= ~128
                elif code == 56:  # LALT
                    if is_down:
                        self.mod_state |= 256
                    else:
                        self.mod_state &= ~256
                elif code == 100:  # RALT
                    if is_down:
                        self.mod_state |= 512
                    else:
                        self.mod_state &= ~512
                elif code == 125:  # LWIN
                    if is_down:
                        self.mod_state |= 1024
                    else:
                        self.mod_state &= ~1024
                elif code == 126:  # RWIN
                    if is_down:
                        self.mod_state |= 2048
                    else:
                        self.mod_state &= ~2048

                win_scancode = REV_E0_MAP.get(code, code)
                key_obj = Key(None, win_scancode, None, self.mod_state)

                if is_down:
                    if self.on_press: self.on_press(key_obj)
                else:
                    if self.on_release: self.on_release(key_obj)

    def stop(self):
        self._stop_event.set()
