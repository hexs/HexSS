import ctypes
import time
import threading

# --- CTYPES STRUCTURES ---
SendInput = ctypes.windll.user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]


# --- CONSTANTS ---
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

ordinary_scancodes = {
    0x00: 'error code',
    0x01: ['Esc'],
    0x02: ['1', '!'], 0x03: ['2', '@'], 0x04: ['3', '#'], 0x05: ['4', '$'], 0x06: ['5', '%'], 0x07: ['6', '^'],
    0x08: ['7', '&'], 0x09: ['8', '*'], 0x0A: ['9', '('], 0x0B: ['0', ')'], 0x0C: ['-', '_'], 0x0D: ['=', '+'],
    0x0E: ['Backspace'],
    0x0F: ['Tab'], 0x10: ['Q'], 0x11: ['W'], 0x12: ['E'], 0x13: ['R'], 0x14: ['T'], 0x15: ['Y'], 0x16: ['U'],
    0x17: ['I'], 0x18: ['O'], 0x19: ['P'], 0x1A: ['[', '{'], 0x1B: [']', '}'],
    0x1C: ['Enter'], 0x1D: ['LCtrl', 'left ctrl', 'ctrl'],
    0x1E: ['A'], 0x1F: ['S'], 0x20: ['D'], 0x21: ['F'], 0x22: ['G'], 0x23: ['H'], 0x24: ['J'], 0x25: ['K'],
    0x26: ['L'], 0x27: [';', ':'], 0x28: ["'", '"'],
    0x29: ['`', '~'],
    0x2A: ['LShift', 'left shift', 'shift'],
    0x2B: ['\\', '|'],
    0x2C: ['Z'], 0x2D: ['X'], 0x2E: ['C'], 0x2F: ['V'], 0x30: ['B'], 0x31: ['N'], 0x32: ['M'],
    0x33: [',', '<'], 0x34: ['.', '>'], 0x35: ['/', '?'], 0x36: ['RShift', 'right shift'],
    0x37: ['Keypad-*', 'PrtScn'],
    0x38: ['LAlt', 'left alt', 'alt'], 0x39: ['Space', 'space bar'], 0x3A: ['CapsLock'],
    0x3B: ['F1'], 0x3C: ['F2'], 0x3D: ['F3'], 0x3E: ['F4'], 0x3F: ['F5'], 0x40: ['F6'],
    0x41: ['F7'], 0x42: ['F8'], 0x43: ['F9'], 0x44: ['F10'],
    0x45: ['NumLock'], 0x46: ['ScrollLock'],
    0x47: ['Keypad-7', 'Home'], 0x48: ['Keypad-8', 'Up'], 0x49: ['Keypad-9', 'PgUp'],
    0x4A: ['Keypad--'],
    0x4B: ['Keypad-4', 'Left'], 0x4C: ['Keypad-5'], 0x4D: ['Keypad-6', 'Right'], 0x4E: ['Keypad-+'],
    0x4F: ['Keypad-1', 'End'], 0x50: ['Keypad-2', 'Down'], 0x51: ['Keypad-3', 'PgDn'],
    0x52: ['Keypad-0', 'Ins'], 0x53: ['Keypad-.', 'Del'],
    0x57: ['F11'], 0x58: ['F12'],
    0x5B: ['Win', 'left win'], 0x5C: ['right win']
}

SCAN_CODES = {}

for key, value in ordinary_scancodes.items():
    if isinstance(value, list):
        for char in value:
            SCAN_CODES[char.lower()] = key

EXTENDED_KEYS = {
    'right ctrl', 'right alt', 'up', 'down', 'left', 'right',
    'win', 'left win', 'right win', 'home', 'end', 'ins', 'del', 'pgup', 'pgdn'
}
SHIFT_CHARS = set('~!@#$%^&*()_+{}|:"<>?ABCDEFGHIJKLMNOPQRSTUVWXYZ')


# --- KEYBOARD CLASS ---
class keyboard:
    active_keys = {}

    @staticmethod
    def _press_key(hexKeyCode: int, is_extended: bool = False):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        flags = KEYEVENTF_SCANCODE
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        ii_.ki = KeyBdInput(0, hexKeyCode, flags, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    @staticmethod
    def _release_key(hexKeyCode: int, is_extended: bool = False):
        extra = ctypes.c_ulong(0)
        ii_ = Input_I()
        flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        ii_.ki = KeyBdInput(0, hexKeyCode, flags, 0, ctypes.pointer(extra))
        x = Input(ctypes.c_ulong(1), ii_)
        SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

    @staticmethod
    def _auto_repeat(hotkey: str, scan_code: int, is_ext: bool):
        keyboard._press_key(scan_code, is_extended=is_ext)
        time_elapsed = 0.0
        while keyboard.active_keys.get(hotkey, False) and time_elapsed < 0.5:
            time.sleep(0.01)
            time_elapsed += 0.01

        while keyboard.active_keys.get(hotkey, False):
            keyboard._press_key(scan_code, is_extended=is_ext)
            time.sleep(0.03)

    @staticmethod
    def _write_unicode(ch: str):
        extra = ctypes.c_ulong(0)
        utf16_bytes = ch.encode('utf-16-le')

        for i in range(0, len(utf16_bytes), 2):
            code = int.from_bytes(utf16_bytes[i:i + 2], byteorder='little')

            ii_ = Input_I()

            # Press
            ii_.ki = KeyBdInput(0, 0, KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
            ii_.ki.wScan = code
            x = Input(ctypes.c_ulong(1), ii_)
            SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))
            time.sleep(0.01)

            # Release
            ii_.ki = KeyBdInput(0, 0, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
            ii_.ki.wScan = code
            x = Input(ctypes.c_ulong(1), ii_)
            SendInput(1, ctypes.pointer(x), ctypes.sizeof(x))

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
                cls._write_unicode(ch)

            time.sleep(interval)

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
                is_ext = k in EXTENDED_KEYS
                cls._press_key(SCAN_CODES[k], is_extended=is_ext)
                time.sleep(0.01)
        if do_press and do_release:
            time.sleep(0.05)
        if do_release:
            for k in reversed(keys):
                is_ext = k in EXTENDED_KEYS
                cls._release_key(SCAN_CODES[k], is_extended=is_ext)
                time.sleep(0.01)

    @classmethod
    def press(cls, hotkey: str):
        hotkey = hotkey.lower()
        if hotkey in SCAN_CODES:
            if cls.active_keys.get(hotkey, False):
                return
            cls.active_keys[hotkey] = True
            is_ext = hotkey in EXTENDED_KEYS
            t = threading.Thread(target=cls._auto_repeat, args=(hotkey, SCAN_CODES[hotkey], is_ext))
            t.daemon = True
            t.start()
        else:
            print(f"[Error] Unknown key: {hotkey}")

    @classmethod
    def release(cls, hotkey: str):
        hotkey = hotkey.lower()
        if hotkey in SCAN_CODES:
            cls.active_keys[hotkey] = False
            is_ext = hotkey in EXTENDED_KEYS
            cls._release_key(SCAN_CODES[hotkey], is_extended=is_ext)
        else:
            print(f"[Error] Unknown key: {hotkey}")
