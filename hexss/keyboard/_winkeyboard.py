"""Windows

ส่วนส่งปุ่ม (class keyboard)  : SendInput — คงพฤติกรรมเดิม
ส่วนรับปุ่ม (class Backend)   : WH_KEYBOARD_LL hook -> RawKey, หา layout ของหน้าต่างที่พิมพ์อยู่,
                                 แปลง scancode -> ตัวอักษรด้วย ToUnicodeEx
"""
import ctypes
import threading
import time
import traceback
from ctypes import wintypes

from .events import Layout, RawKey
from .key_mappings import (
    MOD_NUMLOCK, MOD_CAPSLOCK, MOD_SCROLLLOCK,
    SCANCODE_TO_VK, parse_hotkey, scancode_of,
)

# ใช้ instance ส่วนตัว (ไม่ใช่ ctypes.windll.user32 ที่ใช้ร่วมกันทั้งโปรเซส) เพื่อไม่ไปเปลี่ยน argtypes ของโค้ดอื่น
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class Input_I(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", Input_I)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

# --- WIN32 SIGNATURES (64-bit safe) ---
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetKeyState.argtypes = [ctypes.c_int]
user32.GetKeyState.restype = ctypes.c_short
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
user32.GetKeyboardLayout.restype = ctypes.c_void_p            # HKL เป็น pointer-sized ห้ามถูกตัดเป็น int 32 บิต
user32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_ubyte),
                               wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, ctypes.c_void_p]
user32.ToUnicodeEx.restype = ctypes.c_int
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.LCIDToLocaleName.argtypes = [wintypes.DWORD, wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD]
kernel32.LCIDToLocaleName.restype = ctypes.c_int

# --- CONSTANTS ---
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_QUIT = 0x0012
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLKHF_UP = 0x80
TOUNICODE_NO_STATE_CHANGE = 0x04   # Win10 1607+: ไม่ให้ ToUnicodeEx แตะ dead-key state ของระบบ

VK_SHIFT, VK_CONTROL, VK_MENU, VK_PAUSE = 0x10, 0x11, 0x12, 0x13
VK_CAPITAL, VK_NUMLOCK, VK_SCROLL = 0x14, 0x90, 0x91


def _focus_thread_id() -> int:
    """thread id ของหน้าต่างที่รับการพิมพ์อยู่ (focus > active > foreground)"""
    gti = GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(gti)
    hwnd = None
    if user32.GetGUIThreadInfo(0, ctypes.byref(gti)):
        hwnd = gti.hwndFocus or gti.hwndActive
    if not hwnd:
        hwnd = user32.GetForegroundWindow()
    return user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0


# ===========================================================================
# ส่งปุ่ม (output)
# ===========================================================================
class keyboard:
    active_keys: dict = {}
    _lock = threading.Lock()

    @staticmethod
    def _key_input(code: int, flags: int) -> Input:
        ii_ = Input_I()
        ii_.ki = KeyBdInput(0, code, flags, 0, 0)
        return Input(INPUT_KEYBOARD, ii_)

    @staticmethod
    def _send_inputs(inputs) -> int:
        n = len(inputs)
        arr = (Input * n)(*inputs)
        return user32.SendInput(n, arr, ctypes.sizeof(Input))

    @classmethod
    def _send_scancode(cls, scancode: int, keyup: bool = False):
        flags = KEYEVENTF_SCANCODE
        if keyup:
            flags |= KEYEVENTF_KEYUP
        if scancode >= 0xE000:
            flags |= KEYEVENTF_EXTENDEDKEY
        cls._send_inputs([cls._key_input(scancode & 0xFF, flags)])

    @classmethod
    def _press_key(cls, scancode: int):
        cls._send_scancode(scancode, keyup=False)

    @classmethod
    def _release_key(cls, scancode: int):
        cls._send_scancode(scancode, keyup=True)

    @classmethod
    def _auto_repeat(cls, stop_event: threading.Event, scancode: int):
        cls._press_key(scancode)
        if stop_event.wait(0.5):
            return
        while not stop_event.wait(0.03):
            cls._press_key(scancode)

    @classmethod
    def _write_unicode(cls, ch: str):
        """พิมพ์ตัวอักษรตรงๆ (ไม่ขึ้นกับ layout) — พิมพ์ภาษาไทยได้แม้หน้าต่างอยู่ภาษาอังกฤษ"""
        utf16 = ch.encode('utf-16-le')
        for i in range(0, len(utf16), 2):
            code = int.from_bytes(utf16[i:i + 2], byteorder='little')
            cls._send_inputs([cls._key_input(code, KEYEVENTF_UNICODE)])
            time.sleep(0.01)
            cls._send_inputs([cls._key_input(code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)])

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
        keys = parse_hotkey(hotkey_str)
        if not keys:
            return
        scancodes = [scancode_of(k) for k in keys]      # ตรวจชื่อทั้งหมดก่อนส่งจริง (ValueError ถ้าไม่รู้จัก)

        if do_press:
            for sc in scancodes:
                cls._press_key(sc)
                time.sleep(0.01)
        if do_press and do_release:
            time.sleep(0.05)
        if do_release:
            for sc in reversed(scancodes):
                cls._release_key(sc)
                time.sleep(0.01)

    @classmethod
    def press(cls, hotkey: str):
        """กดค้าง (ส่ง auto-repeat ให้เหมือนคีย์บอร์ดจริงจนกว่าจะ release)"""
        hotkey = hotkey.strip().lower()
        scancode = scancode_of(hotkey)
        with cls._lock:
            if hotkey in cls.active_keys:
                return
            stop_event = threading.Event()
            cls.active_keys[hotkey] = stop_event
        threading.Thread(target=cls._auto_repeat, args=(stop_event, scancode), daemon=True).start()

    @classmethod
    def release(cls, hotkey: str):
        hotkey = hotkey.strip().lower()
        scancode = scancode_of(hotkey)
        with cls._lock:
            stop_event = cls.active_keys.pop(hotkey, None)
        if stop_event is not None:
            stop_event.set()
        cls._release_key(scancode)


# ===========================================================================
# รับปุ่ม (input backend)
# ===========================================================================
class Backend:
    native_state = True        # is_pressed ใช้ GetAsyncKeyState ได้เลย ไม่ต้องมี hook
    supports_suppress = True

    def __init__(self):
        self._layouts = {}
        self._thread = None
        self._tid = 0
        self._proc = None
        self._on_raw = None
        self._error = None

    # ------------------------------------------------------------ hook
    def start(self, on_raw) -> None:
        if self._thread:
            return
        self._on_raw = on_raw
        self._error = None
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(ready,), name="keyboard-hook", daemon=True)
        self._thread.start()
        ready.wait()
        if self._error:
            self._thread = None
            raise self._error

    def stop(self) -> None:
        t = self._thread
        if not t:
            return
        user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        t.join(timeout=2)
        self._thread = None

    def _run(self, ready: threading.Event) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0x400, 0x400, 0)   # สร้าง message queue ของ thread นี้
        self._proc = HOOKPROC(self._hook_proc)    # ต้องเก็บ reference ไว้ ไม่งั้นถูก GC แล้ว crash
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._error = ctypes.WinError(ctypes.get_last_error())
            ready.set()
            return
        ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        user32.UnhookWindowsHookEx(hook)

    def _hook_proc(self, n_code, w_param, l_param):
        if n_code == HC_ACTION:
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = info.vkCode
                sc = info.scanCode
                if not sc:                               # event ที่จำลองด้วย vk อย่างเดียว
                    sc = user32.MapVirtualKeyW(vk, 0)
                if vk == VK_NUMLOCK:                     # NumLock ถูกรายงานพร้อม flag extended
                    sc = 0x45
                elif vk == VK_PAUSE:                     # Pause มี scancode 0x45 เหมือน NumLock
                    sc = 0xE11D
                elif sc == 0x21D:                        # LCtrl ปลอมที่ Windows ส่งคู่กับ AltGr
                    sc = 0x1D
                elif info.flags & LLKHF_EXTENDED:
                    sc |= 0xE000
                raw = RawKey(vk, sc, not (info.flags & LLKHF_UP), bool(info.flags & LLKHF_INJECTED))
                if self._on_raw(raw):
                    return 1                             # suppress
            except Exception:
                traceback.print_exc()                    # error ใน hook ต้องไม่ทำให้คีย์บอร์ดทั้งระบบค้าง
        return user32.CallNextHookEx(None, n_code, w_param, l_param)

    # ---------------------------------------------------------- layout
    def get_layout(self) -> Layout:
        hkl = user32.GetKeyboardLayout(_focus_thread_id()) or 0
        layout = self._layouts.get(hkl)
        if layout is None:
            langid = hkl & 0xFFFF
            buf = ctypes.create_unicode_buffer(85)
            n = kernel32.LCIDToLocaleName(langid, buf, 85, 0)
            layout = Layout(hkl, langid, buf.value if n > 0 else f"0x{langid:04x}")
            self._layouts[hkl] = layout
        return layout

    def translate(self, vk, scancode, shift, ctrl, alt, caps, hkl) -> str:
        """scancode + modifier + layout -> ตัวอักษร ('' ถ้าปุ่มนี้ไม่ให้ตัวอักษร / เป็น dead key)"""
        ks = (ctypes.c_ubyte * 256)()
        if shift:
            ks[VK_SHIFT] = 0x80
        if ctrl:
            ks[VK_CONTROL] = 0x80
        if alt:
            ks[VK_MENU] = 0x80
        if caps:
            ks[VK_CAPITAL] = 0x01
        buf = ctypes.create_unicode_buffer(8)
        n = user32.ToUnicodeEx(vk, scancode & 0xFF, ks, buf, 8, TOUNICODE_NO_STATE_CHANGE, hkl)
        return buf.value[:n] if n > 0 else ""

    def toggle_state(self) -> int:
        mods = 0
        if user32.GetKeyState(VK_NUMLOCK) & 1:
            mods |= MOD_NUMLOCK
        if user32.GetKeyState(VK_CAPITAL) & 1:
            mods |= MOD_CAPSLOCK
        if user32.GetKeyState(VK_SCROLL) & 1:
            mods |= MOD_SCROLLLOCK
        return mods

    def is_down(self, scancode: int) -> bool:
        vk = SCANCODE_TO_VK.get(scancode) or user32.MapVirtualKeyW(scancode & 0xFF, 3)
        if not vk:
            raise ValueError(f"Unknown scancode: {hex(scancode)}")
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)
