"""แกนกลางที่ไม่ผูกกับ OS

backend (Windows / Linux) ส่ง RawKey เข้ามา แล้ว core ทำหน้าที่
  - ติดตามสถานะปุ่ม / modifier
  - ถาม backend ว่า layout อะไร และแปลง scancode -> ตัวอักษร
  - ประกอบ KeyEvent แล้วส่งให้ (1) คิวสำหรับ get()/wait() (2) listener ใน thread แยก
  - ตัดสินใจ suppress (ใน hook thread, ต้องเร็ว)

สัญญาของ backend:
    native_state: bool            True = is_down() ใช้ได้เลยโดยไม่ต้องมี hook (Windows)
    supports_suppress: bool
    start(on_raw)                 on_raw(RawKey) -> bool  (True = กลืน event)
    stop()
    get_layout() -> Layout
    translate(vk, scancode, shift, ctrl, alt, caps, hkl) -> str
    unmodified_char(vk, scancode, hkl) -> str   (ไม่บังคับ) ตัวอักษรตอนไม่กด modifier ใน layout hkl
    toggle_state() -> int         MOD_NUMLOCK | MOD_CAPSLOCK | MOD_SCROLLLOCK ตอนนี้
    is_down(scancode) -> bool | None
"""
import platform
import threading
import time
import traceback
from collections import deque
from queue import SimpleQueue

from .events import KEYDOWN, KEYUP, SPECIAL, KeyEvent, Layout, RawKey
from .key_mappings import (
    KEY_MAPPINGS, KEYPAD_SCANCODES,
    MOD_LSHIFT, MOD_RSHIFT, MOD_LCTRL, MOD_RCTRL, MOD_LALT, MOD_RALT, MOD_LWIN, MOD_RWIN,
    MOD_NUMLOCK, MOD_CAPSLOCK, MOD_SCROLLLOCK, MOD_SHIFT, MOD_CTRL, MOD_ALT, MOD_WIN,
    resolve_scancodes,
)

_HOLD_MODS = {
    0x2A: MOD_LSHIFT, 0x36: MOD_RSHIFT,
    0x1D: MOD_LCTRL, 0xE01D: MOD_RCTRL,
    0x38: MOD_LALT, 0xE038: MOD_RALT,
    0xE05B: MOD_LWIN, 0xE05C: MOD_RWIN,
}
_TOGGLE_MODS = {0x3A: MOD_CAPSLOCK, 0x45: MOD_NUMLOCK, 0x46: MOD_SCROLLLOCK}


def _name_of(scancode: int) -> str:
    mapping = KEY_MAPPINGS.get(scancode)
    return mapping['name'][0] if mapping else f"UNKNOWN_0x{scancode:04X}"


def _default_backend():
    system = platform.system()
    if system == 'Windows':
        from ._winkeyboard import Backend
    elif system == 'Linux':
        from ._nixkeyboard import Backend
    else:
        raise NotImplementedError(f"Currently, {system} is not supported.")
    return Backend()


class Keyboard:
    def __init__(self, backend=None, repeat: bool = False, max_events: int = 1024):
        self._backend = backend if backend is not None else _default_backend()
        self.repeat = repeat                    # True = คิว get()/wait() รับ event กดค้างด้วย
        self._lock = threading.Lock()           # ปกป้อง _down / _toggles
        self._life = threading.RLock()          # ปกป้อง refcount ของ hook
        self._refs = 0
        self._running = False
        self._explicit = False                  # start() แบบ idempotent
        self._state_ref = False                 # is_pressed บน backend ที่ไม่มี native state
        self._down = set()
        self._toggles = 0
        self._queue = deque(maxlen=max_events)
        self._cond = threading.Condition()
        self._listeners = ()                    # tuple ของ (fn, suppress, repeat) — copy-on-write
        self._dispatch_q = None
        self._dispatch_thread = None
        self._keycache = {}                     # (hkl, scancode) -> key

    # ------------------------------------------------------------ lifecycle
    @property
    def running(self) -> bool:
        return self._running

    @property
    def supports_suppress(self) -> bool:
        return bool(getattr(self._backend, 'supports_suppress', False))

    def acquire(self) -> None:
        """ขอใช้ hook (นับจำนวนผู้ใช้; hook เริ่มตอนผู้ใช้คนแรก และหยุดตอนคนสุดท้ายปล่อย)"""
        with self._life:
            if self._refs == 0:
                self._backend.start(self._on_raw)
                with self._lock:
                    self._toggles = self._backend.toggle_state()
                self._running = True
            self._refs += 1

    def release(self) -> None:
        with self._life:
            if self._refs == 0:
                return
            self._refs -= 1
            if self._refs == 0:
                self._running = False
                self._backend.stop()
                with self._lock:
                    self._down.clear()

    def start(self) -> None:
        """เริ่มดักคีย์บอร์ด (เรียกซ้ำได้) ใช้คู่กับ stop()"""
        with self._life:
            if not self._explicit:
                self.acquire()
                self._explicit = True

    def stop(self) -> None:
        with self._life:
            if self._explicit:
                self._explicit = False
                self.release()

    # ---------------------------------------------------------- raw -> event
    def _on_raw(self, raw: RawKey) -> bool:
        """เรียกใน thread ของ hook — ต้องเร็ว ห้าม block  คืน True = กลืน event (suppress)"""
        sc = raw.scancode
        with self._lock:
            repeat = raw.down and sc in self._down
            if raw.down:
                self._down.add(sc)
                if not repeat:
                    self._toggles ^= _TOGGLE_MODS.get(sc, 0)
            else:
                self._down.discard(sc)
            mods = self._mods_locked()

        layout = self._backend.get_layout()
        ev = KeyEvent(
            type=KEYDOWN if raw.down else KEYUP,
            scancode=sc,
            key=self._keycode(raw, layout),
            unicode=self._text(raw, mods, layout) if raw.down else "",
            mod=mods,
            layout=layout,
            name=_name_of(sc),
            vk=raw.vk,
            repeat=repeat,
            injected=raw.injected,
            time=time.time(),
        )
        self._emit(ev)
        return self._swallow(ev)

    def _mods_locked(self) -> int:
        m = self._toggles
        for sc in self._down:
            m |= _HOLD_MODS.get(sc, 0)
        return m

    def _text(self, raw: RawKey, mods: int, layout: Layout) -> str:
        """ตัวอักษรที่พิมพ์ได้จริงจากการกดครั้งนี้ ตาม layout ปัจจุบัน"""
        ctrl = bool(mods & MOD_CTRL)
        alt = bool(mods & MOD_ALT)
        # Ctrl+X / Alt+X / Win+X = shortcut ไม่ใช่ตัวอักษร (ยกเว้น Ctrl+Alt = AltGr)
        if mods & MOD_WIN or ctrl != alt:
            return ""
        return self._backend.translate(
            raw.vk, raw.scancode, bool(mods & MOD_SHIFT), ctrl, alt,
            bool(mods & MOD_CAPSLOCK), layout.hkl)

    def _keycode(self, raw: RawKey, layout: Layout) -> int:
        """key แบบ pygame/SDL: ตัวอักษร (ตัวเล็ก) ที่ปุ่มนี้ให้ตอนไม่กด modifier ใน layout ปัจจุบัน"""
        if raw.scancode in KEYPAD_SCANCODES:
            return SPECIAL | raw.scancode
        cache_key = (layout.hkl, raw.scancode)
        key = self._keycache.get(cache_key)
        if key is None:
            base_char = getattr(self._backend, 'unmodified_char', None)
            if base_char is not None:
                ch = base_char(raw.vk, raw.scancode, layout.hkl)
            else:
                ch = self._backend.translate(
                    raw.vk, raw.scancode, False, False, False, False, layout.hkl)
            key = ord(ch) if len(ch) == 1 else SPECIAL | raw.scancode
            self._keycache[cache_key] = key
        return key

    def _swallow(self, ev: KeyEvent) -> bool:
        if ev.injected:                 # ไม่กลืน event ที่โปรแกรมเราเอง/โปรแกรมอื่นจำลอง
            return False
        for _fn, suppress, _rep in self._listeners:
            if suppress is True:
                return True
            if callable(suppress):
                try:
                    if suppress(ev):
                        return True
                except Exception:
                    traceback.print_exc()
        return False

    # --------------------------------------------------------------- output
    def _emit(self, ev: KeyEvent) -> None:
        if not ev.repeat or self.repeat:
            with self._cond:
                self._queue.append(ev)
                self._cond.notify_all()
        q = self._dispatch_q
        if q is not None:
            q.put(ev)

    def get(self) -> list:
        """ดึง event ที่ค้างอยู่ทั้งหมด (ไม่ block)"""
        with self._cond:
            events = list(self._queue)
            self._queue.clear()
        return events

    def wait(self, timeout=None):
        """รอ event ถัดไป 1 อัน (None = หมดเวลา)"""
        with self._cond:
            if not self._cond.wait_for(lambda: self._queue, timeout):
                return None
            return self._queue.popleft()

    def clear(self) -> None:
        with self._cond:
            self._queue.clear()

    # ------------------------------------------------------------ listeners
    def add_listener(self, fn, suppress=False, repeat: bool = False) -> None:
        """fn(event) ถูกเรียกใน thread แยก (ไม่ใช่ใน hook จึงช้า/โยน exception ได้โดยไม่ทำให้คีย์บอร์ดค้าง)

        suppress: True = กลืนทุกปุ่ม, หรือ callable(event) -> bool ตัดสินรายปุ่ม
                  (callable ทำงานใน hook thread จึงต้องเร็ว)
        repeat:   True = รับ event กดค้างด้วย
        """
        with self._lock:
            self._listeners = tuple(l for l in self._listeners if l[0] != fn) + ((fn, suppress, repeat),)
        self._start_dispatcher()

    def remove_listener(self, fn) -> None:
        with self._lock:
            self._listeners = tuple(l for l in self._listeners if l[0] != fn)
            empty = not self._listeners
        if empty:
            self._stop_dispatcher()

    def _start_dispatcher(self) -> None:
        with self._life:
            if self._dispatch_thread is not None:
                return
            q = SimpleQueue()
            t = threading.Thread(target=self._dispatch_loop, args=(q,),
                                 name="keyboard-dispatch", daemon=True)
            self._dispatch_q = q
            self._dispatch_thread = t
            t.start()

    def _stop_dispatcher(self) -> None:
        with self._life:
            q, t = self._dispatch_q, self._dispatch_thread
            self._dispatch_q = None
            self._dispatch_thread = None
        if q is not None:
            q.put(None)
        if t is not None and t is not threading.current_thread():
            t.join(timeout=1)

    def _dispatch_loop(self, q) -> None:
        while True:
            ev = q.get()
            if ev is None:
                return
            for fn, _suppress, rep in self._listeners:
                if ev.repeat and not rep:
                    continue
                try:
                    fn(ev)
                except Exception:
                    traceback.print_exc()

    # ---------------------------------------------------------------- state
    def get_layout(self) -> Layout:
        return self._backend.get_layout()

    def get_mods(self) -> int:
        with self._lock:
            return self._mods_locked()

    def get_pressed(self) -> frozenset:
        """scancode ของปุ่มที่กำลังกดอยู่ (นับตั้งแต่เริ่มดัก)"""
        with self._lock:
            return frozenset(self._down)

    def is_pressed(self, key=None, scancode=None, vk=None) -> bool:
        """ระบุอย่างใดอย่างหนึ่ง: key (ชื่อ/alias หรือ scancode), scancode, vk
        ชื่อรวม 'shift' 'ctrl' 'alt' 'win' = ซ้ายหรือขวาก็ได้  ใช้ปุ่มกายภาพ ไม่ขึ้นกับภาษา"""
        scs = resolve_scancodes(key, scancode, vk)
        if getattr(self._backend, 'native_state', False):
            return any(self._backend.is_down(sc) for sc in scs)
        with self._life:                          # backend ไม่มี state ของ OS: ใช้ state จาก hook
            if not self._state_ref:
                self.acquire()
                self._state_ref = True
        with self._lock:
            return not self._down.isdisjoint(scs)


_instance = None
_instance_lock = threading.Lock()


def get_keyboard() -> Keyboard:
    """Keyboard ตัวกลางของโปรแกรม (สร้างเมื่อเรียกครั้งแรก)"""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = Keyboard()
        return _instance


def peek_keyboard():
    """คืน Keyboard ตัวกลางถ้าเคยสร้างแล้ว (ไม่สร้างใหม่)"""
    return _instance
