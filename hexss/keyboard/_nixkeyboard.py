"""Linux

ส่วนส่งปุ่ม (class keyboard)  : uinput — คงพฤติกรรมเดิม (แก้การแมป ; - = [ ] ... ที่เคยผิด)
ส่วนรับปุ่ม (class Backend)   : evdev -> RawKey  layout/ตัวอักษรได้จาก libxkbcommon (ดู _xkb.py)
                                 ถ้าใช้ libxkbcommon ไม่ได้ จะถอยกลับไปใช้ตาราง US (en-US)
สิทธิ์: root หรือผู้ใช้ในกลุ่ม input (+ udev rule สำหรับ /dev/uinput ถ้าต้องส่งปุ่ม) — ดู README
"""
import fcntl
import struct
import threading
import time
import traceback
import warnings
import weakref
from queue import Empty

from ._nixcommon import (
    EV_KEY,
    EV_SYN,
    VIRTUAL_KEYBOARD_NAME,
    aggregate_devices,
    ensure_input_access,
    ensure_uinput_access,
    event_bin_format,
    make_uinput,
)
from .events import Layout, RawKey
from ._xkb import XkbConfig, XkbMirror, detect_config
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

_xkb_override = None                 # XkbConfig ที่ผู้ใช้กำหนดเองด้วย set_xkb()
_backends = weakref.WeakSet()


def set_xkb(layout=None, variant=None, options=None, model=None, rules=None):
    """บอกไลบรารีว่า desktop ใช้ layout อะไร เมื่อการตรวจอัตโนมัติไม่ตรง (เฉพาะ Linux)

        set_xkb("us,th", options="grp:alt_shift_toggle")

    เรียกโดยไม่ใส่อะไรเลย = ยกเลิก กลับไปตรวจอัตโนมัติ
    """
    global _xkb_override
    _xkb_override = XkbConfig(rules, model, layout, variant, options, "set_xkb()") if layout else None
    for backend in list(_backends):
        backend.reload_xkb()


def set_xkb_group(index: int):
    """บังคับ layout ปัจจุบัน (0 = layout แรกใน set_xkb) ใช้ซิงก์เมื่อเปิดโปรแกรมขณะอยู่ภาษาอื่น"""
    for backend in list(_backends):
        backend.set_group(index)


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
                ensure_uinput_access()
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
        self._xkb = None
        self._xkb_failed = False
        _backends.add(self)

    def start(self, on_raw) -> None:
        if self._thread:
            return
        ensure_input_access()
        if self._device is None:
            device = aggregate_devices('keyboard', create_uinput=False)
            if device is None:
                raise RuntimeError("No keyboard input devices found.")
            self._device = device
            # event ที่มาจาก uinput ของเราเอง (send/write) -> injected=True
            self._virtual = {d.path for d in getattr(device, 'devices', []) if d.name == VIRTUAL_KEYBOARD_NAME}
        self._drain()
        self._toggle = _read_initial_toggle_mods(self._device)
        self._reset_xkb()
        if self._xkb is not None:
            self._xkb.set_locks(bool(self._toggle & MOD_CAPSLOCK), bool(self._toggle & MOD_NUMLOCK))
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
        if self._xkb is not None:
            self._xkb.close()
            self._xkb = None

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
            xkb = self._xkb
            if xkb is not None and type_val == EV_KEY and code < 0x100 and value in (0, 1):
                xkb.update(code, value == 1)          # ป้อนกดครั้งแรก/ปล่อย (ไม่ป้อนตอนกดค้าง)
            raw = raw_from_event(type_val, code, value, path in self._virtual)
            if raw is None:
                continue
            try:
                self._on_raw(raw)
            except Exception:
                traceback.print_exc()

    # ---------------------------------------------------------- layout
    def _make_xkb(self):
        config = _xkb_override or detect_config()
        try:
            return XkbMirror(config)
        except Exception as e:
            self._xkb_failed = True
            warnings.warn(f"ใช้ libxkbcommon ไม่ได้ ({e}) — ถอยกลับไปใช้ตาราง US (layout เป็น en-US เสมอ)",
                          RuntimeWarning, stacklevel=2)
            return None

    def _reset_xkb(self) -> None:
        old, self._xkb_failed = self._xkb, False
        self._xkb = self._make_xkb()
        if old is not None:
            old.close()

    def _ensure_xkb(self):
        if self._xkb is None and not self._xkb_failed:
            self._xkb = self._make_xkb()
        return self._xkb

    def reload_xkb(self) -> None:
        """ใช้ค่าจาก set_xkb() ใหม่ (ถ้ากำลังทำงานอยู่จะรีเซ็ต state ของ layout)"""
        if self._thread:
            self._reset_xkb()
            if self._xkb is not None:
                self._xkb.set_locks(bool(self._toggle & MOD_CAPSLOCK), bool(self._toggle & MOD_NUMLOCK))
        elif self._xkb is not None:
            self._xkb.close()
            self._xkb = None
            self._xkb_failed = False

    def set_group(self, index: int) -> None:
        xkb = self._ensure_xkb()
        if xkb is not None:
            xkb.set_group(index)

    def get_layout(self) -> Layout:
        xkb = self._ensure_xkb()
        return xkb.layout() if xkb is not None else _EN_US

    def translate(self, vk, scancode, shift, ctrl, alt, caps, hkl) -> str:
        xkb = self._xkb
        if xkb is not None:
            return xkb.text(linux_code(scancode))     # state ของ xkb รู้ Shift/CapsLock/layout เองอยู่แล้ว
        return us_char(scancode, shift, caps)

    def unmodified_char(self, vk, scancode, hkl) -> str:
        xkb = self._xkb
        if xkb is not None:
            return xkb.base_char(linux_code(scancode), group=hkl)
        return us_char(scancode)

    def toggle_state(self) -> int:
        return self._toggle

    def is_down(self, scancode):
        return None
