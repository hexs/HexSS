import threading
import warnings

from ._core import get_keyboard
from .events import KEYDOWN


class Listener(threading.Thread):
    """API เดิม: Listener(on_press, on_release, suppress)  ใช้แบบ context manager หรือ start()/stop()/join()

    ต่างจากเดิม:
      - ทุก Listener แชร์ hook ตัวเดียว (เดิม 1 Listener = 1 hook)
      - on_press / on_release ถูกเรียกใน thread แยก ไม่ใช่ใน hook thread
      - callback รับ KeyEvent ที่มี .layout / .unicode เพิ่ม
      - กดค้าง (auto-repeat) ไม่ถูกส่งเป็น on_press ถ้าไม่ระบุ repeat=True
      - suppress เป็น True หรือ callable(event) -> bool  (ไม่กลืน event ที่ถูกจำลอง; ยังไม่รองรับบน Linux)
    """

    def __init__(self, on_press=None, on_release=None, suppress=False, repeat=False, keyboard=None):
        super().__init__(daemon=True)
        self.on_press = on_press
        self.on_release = on_release
        self.suppress = suppress
        self.repeat = repeat
        self._kb = keyboard
        self._acquired = False
        self._stop_event = threading.Event()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def start(self):
        if self._kb is None:
            self._kb = get_keyboard()
        if self.suppress and not self._kb.supports_suppress:
            warnings.warn("suppress ยังไม่รองรับบนแพลตฟอร์มนี้ — event จะยังถูกส่งต่อให้โปรแกรมอื่น",
                          RuntimeWarning, stacklevel=2)
        self._kb.acquire()
        self._acquired = True
        try:
            self._kb.add_listener(self._handle, suppress=self.suppress, repeat=self.repeat)
        except BaseException:
            self._acquired = False
            self._kb.release()
            raise
        super().start()

    def run(self):
        self._stop_event.wait()      # ให้ join() บล็อกจนกว่าจะ stop() เหมือนเดิม

    def stop(self):
        self._stop_event.set()
        if self._acquired:
            self._acquired = False
            self._kb.remove_listener(self._handle)
            self._kb.release()

    def _handle(self, ev):
        if ev.type == KEYDOWN:
            if self.on_press:
                self.on_press(ev)
        elif self.on_release:
            self.on_release(ev)
