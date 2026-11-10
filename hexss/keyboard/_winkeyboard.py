import ctypes
from ctypes import wintypes
import time
import threading
from .key_mappings import KEY_MAPPINGS, EXTENDED_KEYS

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

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

SCAN_CODES = {}
for scancode, data in KEY_MAPPINGS.items():
    for name in data['name']:
        SCAN_CODES[name.lower()] = scancode


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


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]


HOOKPROC = ctypes.WINFUNCTYPE(wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class Key:
    def __init__(self, vk, scancode, unicode_char, mod=0, flags=0):
        self.vk = vk
        self.unicode = unicode_char
        self.mod = mod

        actual_scancode = scancode | 0xE000 if (flags & 1) and scancode < 0xE000 else scancode
        self.scancode = actual_scancode

        mapping = KEY_MAPPINGS.get(self.scancode)
        if mapping and mapping['vk'] == self.vk:
            self.name = mapping['name'][0]
        else:
            self.name = f"UNKNOWN_{self.vk}"
            for sc, data in KEY_MAPPINGS.items():
                if data['vk'] == self.vk:
                    self.name = data['name'][0]
                    break

        if 65 <= self.vk <= 90:
            self.key = self.vk + 32
        else:
            self.key = self.vk

    def __str__(self):
        return (f"<Key(name: {self.name}, unicode: '{self.unicode}', key: {self.key}, mod: {self.mod}, "
                f"scancode: {self.scancode}, VK:{self.vk})>")


class Listener(threading.Thread):
    def __init__(self, on_press=None, on_release=None, suppress=False):
        super().__init__()
        self.daemon = True
        self.on_press = on_press
        self.on_release = on_release
        self.suppress = suppress
        self.hook_id = None
        self._hook_proc_pointer = None

    def run(self):
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self._hook_proc_pointer = HOOKPROC(self._hook_proc)

        ctypes.windll.kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        ctypes.windll.user32.SetWindowsHookExW.restype = wintypes.HHOOK
        ctypes.windll.user32.CallNextHookEx.restype = wintypes.LPARAM

        ctypes.windll.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        ctypes.windll.user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD
        ]
        ctypes.windll.user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM
        ]

        h_mod = ctypes.windll.kernel32.GetModuleHandleW(None)

        self.hook_id = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc_pointer,
            h_mod,
            0
        )

        if not self.hook_id:
            print("[Error] Failed to install keyboard hook.")
            return

        msg = wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        ctypes.windll.user32.UnhookWindowsHookEx(self.hook_id)

    def stop(self):
        if hasattr(self, 'thread_id'):
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)

    def _hook_proc(self, nCode, wParam, lParam):
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            scancode = kb.scanCode

            keyboard_state = (ctypes.c_uint8 * 256)()
            ctypes.windll.user32.GetKeyboardState(ctypes.byref(keyboard_state))

            mod = 0
            if keyboard_state[0x10] & 0x80: mod |= 1  # VK_SHIFT
            if keyboard_state[0x11] & 0x80: mod |= 2  # VK_CONTROL
            if keyboard_state[0x12] & 0x80: mod |= 4  # VK_MENU

            buffer = ctypes.create_unicode_buffer(4)
            result = ctypes.windll.user32.ToUnicode(vk, scancode, keyboard_state, buffer, 4, 0)
            unicode_char = buffer.value if result > 0 else None

            key_obj = Key(vk, scancode, unicode_char, mod, kb.flags)

            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN) and self.on_press:
                self.on_press(key_obj)
            elif wParam in (WM_KEYUP, WM_SYSKEYUP) and self.on_release:
                self.on_release(key_obj)

            if self.suppress:
                return 1

        return ctypes.windll.user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)
