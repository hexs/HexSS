"""Linux

ส่วนส่งปุ่ม (class keyboard)  : uinput — คงพฤติกรรมเดิม (แก้การแมป ; - = [ ] ... ที่เคยผิด)
ส่วนรับปุ่ม (class Backend)   : evdev -> RawKey  (ตอนนี้ layout/ตัวอักษรเป็น US อย่างเดียว —
                                 รองรับภาษาไทยบน Linux ต้องต่อ xkbcommon เพิ่ม ดู README)
ต้องรันด้วย root
"""
import fcntl
import struct
import threading
import time
import traceback
import warnings
from queue import Empty

from ._nixcommon import (
    EV_KEY,
    EV_SYN,
    VIRTUAL_KEYBOARD_NAME,
    aggregate_devices,
    ensure_root,
    event_bin_format,
    make_uinput,
)
from .events import Layout, RawKey
from .key_mappings import (
    CHAR_TO_KEY,
    MOD_NUMLOCK,
    MOD_CAPSLOCK,
    MOD_SCROLLLOCK,
    SCANCODE_TO_VK,
    parse_hotkey,
    scancode_of,
    us_char,
)

# Linux evdev EVIOCGLED(2) = _IOR('E', 0x19, 2)
EVIOCGLED_2 = 0x80024519
LED_NUML = 0
LED_CAPSL = 1
LED_SCROLLL = 2

E0_MAP = {
    0xE01C: 96,   # KEY_KPENTER
    0xE01D: 97,   # KEY_RIGHTCTRL
    0xE035: 98,   # KEY_KPSLASH
    0xE037: 99,   # KEY_SYSRQ
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

KEY_LEFTSHIFT = 42
_EN_US = Layout(0, 0x0409, "en-US")


def linux_code(scancode: int) -> int:
    """scancode ของ Windows (มี E0) -> keycode ของ evdev"""
    return E0_MAP.get(scancode, scancode & 0xFF) if scancode >= 0xE000 else scancode


def raw_from_event(type_val, code, value, injected=False):
    """evdev event -> RawKey (None ถ้าไม่ใช่ปุ่มคีย์บอร์ด)"""
    if type_val != EV_KEY or code >= 0x100:      # >= 0x100 คือ BTN_* (เมาส์/จอย)
        return None
    sc = REV_E0_MAP.get(code, code)
    return RawKey(SCANCODE_TO_VK.get(sc, 0), sc, value != 0, injected)


def _read_initial_toggle_mods(device) -> int:
    """อ่านสถานะ NumLock / CapsLock / ScrollLock (LED) ตอนเริ่ม"""
    devices = getattr(device, 'devices', [device])
    buf = bytearray(2)
    for dev in devices:
        try:
            fcntl.ioctl(dev.input_file.fileno(), EVIOCGLED_2, buf, True)
            led_bits = int.from_bytes(buf, byteorder='little')
            mod = 0
            if led_bits & (1 << LED_NUML):
                mod |= MOD_NUMLOCK
            if led_bits & (1 << LED_CAPSL):
                mod |= MOD_CAPSLOCK
            if led_bits & (1 << LED_SCROLLL):
                mod |= MOD_SCROLLLOCK
            return mod
        except OSError:
            continue
    return 0


# ===========================================================================
# ส่งปุ่ม (output)
# ===========================================================================
class keyboard:
    active_keys: dict = {}
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
    def _write_event(cls, type_val, code, value):
        device = cls._get_uinput()
        integer, fraction = divmod(time.time(), 1)
        seconds = int(integer)
        microseconds = int(fraction * 1e6)
        data_event = struct.pack(event_bin_format, seconds, microseconds, type_val, code, value)
        sync_event = struct.pack(event_bin_format, seconds, microseconds, EV_SYN, 0, 0)
        with cls._lock:
            device.write(data_event + sync_event)
            device.flush()

    @classmethod
    def press(cls, hotkey: str):
        """กดค้าง (desktop session จะ auto-repeat เองบน Linux จึงส่ง keydown ครั้งเดียว)"""
        hotkey = hotkey.strip().lower()
        code = linux_code(scancode_of(hotkey))
        if cls.active_keys.get(hotkey, False):
            return
        cls.active_keys[hotkey] = True
        cls._write_event(EV_KEY, code, 1)

    @classmethod
    def release(cls, hotkey: str):
        hotkey = hotkey.strip().lower()
        code = linux_code(scancode_of(hotkey))
        cls.active_keys[hotkey] = False
        cls._write_event(EV_KEY, code, 0)

    @classmethod
    def send(cls, hotkey_str: str, do_press: bool = True, do_release: bool = True):
        keys = parse_hotkey(hotkey_str)
        if not keys:
            return
        codes = [linux_code(scancode_of(k)) for k in keys]     # ValueError ถ้าไม่รู้จักปุ่ม (ก่อนส่งจริง)

        if do_press:
            for code in codes:
                cls._write_event(EV_KEY, code, 1)
                time.sleep(0.01)
        if do_press and do_release:
            time.sleep(0.05)
        if do_release:
            for code in reversed(codes):
                cls._write_event(EV_KEY, code, 0)
                time.sleep(0.01)

    @classmethod
    def write(cls, text: str, interval: float = 0.02):
        """พิมพ์ข้อความ (ตอนนี้ได้เฉพาะตัวอักษรที่มีบน US layout; ตัวอื่นเช่นภาษาไทยจะถูกข้ามพร้อมคำเตือน)"""
        skipped = []
        for ch in text:
            if ch == '\n':
                cls.send('enter')
            elif ch == '\t':
                cls.send('tab')
            elif ch == '\b':
                cls.send('backspace')
            elif ch == '\r':
                continue
            elif ch in CHAR_TO_KEY:
                scancode, shift = CHAR_TO_KEY[ch]
                code = linux_code(scancode)
                if shift:
                    cls._write_event(EV_KEY, KEY_LEFTSHIFT, 1)
                    time.sleep(0.005)
                cls._write_event(EV_KEY, code, 1)
                cls._write_event(EV_KEY, code, 0)
                if shift:
                    time.sleep(0.005)
                    cls._write_event(EV_KEY, KEY_LEFTSHIFT, 0)
            else:
                skipped.append(ch)
            time.sleep(interval)
        if skipped:
            warnings.warn(f"write(): ข้ามตัวอักษรที่พิมพ์ไม่ได้บน Linux: {''.join(dict.fromkeys(skipped))!r}",
                          RuntimeWarning, stacklevel=2)


# ===========================================================================
# รับปุ่ม (input backend)
# ===========================================================================
class Backend:
    native_state = False       # is_pressed ต้องใช้ state จาก hook (core จัดการให้)
    supports_suppress = False  # ต้องใช้ EVIOCGRAB + ส่งต่อผ่าน uinput (ยังไม่ทำ)

    def __init__(self):
        self._device = None
        self._virtual = set()
        self._thread = None
        self._stop = threading.Event()
        self._on_raw = None
        self._toggle = 0

    def start(self, on_raw) -> None:
        if self._thread:
            return
        ensure_root()
        if self._device is None:
            device = aggregate_devices('keyboard', create_uinput=False)
            if device is None:
                raise RuntimeError("No keyboard input devices found.")
            self._device = device
            # event ที่มาจาก uinput ของเราเอง (send/write) -> injected=True
            self._virtual = {d.path for d in getattr(device, 'devices', []) if d.name == VIRTUAL_KEYBOARD_NAME}
        self._drain()
        self._toggle = _read_initial_toggle_mods(self._device)
        self._on_raw = on_raw
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="keyboard-evdev", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        t = self._thread
        if not t:
            return
        self._stop.set()
        t.join(timeout=1)
        self._thread = None

    def _drain(self) -> None:
        """ทิ้ง event ที่ค้างในคิวระหว่างที่หยุดอยู่ (reader thread ของ evdev อ่านต่อเนื่องตลอด)"""
        queue = getattr(self._device, 'event_queue', None)
        while queue is not None:
            try:
                queue.get_nowait()
            except Empty:
                break

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                _t, type_val, code, value, path = self._device.read_event(timeout=0.1)
            except Empty:
                continue
            except Exception:
                traceback.print_exc()
                break
            raw = raw_from_event(type_val, code, value, path in self._virtual)
            if raw is None:
                continue
            try:
                self._on_raw(raw)
            except Exception:
                traceback.print_exc()

    # ---------------------------------------------------------- layout
    def get_layout(self) -> Layout:
        return _EN_US

    def translate(self, vk, scancode, shift, ctrl, alt, caps, hkl) -> str:
        return us_char(scancode, shift, caps)

    def toggle_state(self) -> int:
        return self._toggle

    def is_down(self, scancode):
        return None
