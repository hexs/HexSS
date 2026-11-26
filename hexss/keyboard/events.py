"""ชนิดข้อมูลกลาง: Layout, KeyEvent (ส่งออกเป็น Key ด้วย), RawKey"""
from collections import namedtuple
from dataclasses import dataclass

# event type (ค่าเดียวกับ pygame)
KEYDOWN = 768
KEYUP = 769

# key ที่ไม่มีตัวอักษร (Shift, F1, ลูกศร, numpad ...) = SPECIAL | scancode  (แบบ SDL)
SPECIAL = 1 << 30


@dataclass(frozen=True)
class Layout:
    """keyboard layout ที่ active อยู่ตอนกดปุ่ม"""
    hkl: int       # Windows: HKL / Linux: group index
    langid: int    # เช่น 0x041E = ไทย, 0x0409 = อังกฤษ (US)
    locale: str    # เช่น "th-TH", "en-US"

    @property
    def lang(self) -> str:
        """รหัสภาษาสั้นๆ เช่น 'th', 'en'"""
        return self.locale.split("-")[0].lower()


@dataclass(frozen=True)
class KeyEvent:
    type: int          # KEYDOWN / KEYUP
    scancode: int      # ปุ่มกายภาพ ไม่เปลี่ยนตามภาษา (ปุ่ม extended = 0xE000 | sc)
    key: int           # ตัวอักษรที่ปุ่มนี้ให้ตอนไม่กด modifier ใน layout ปัจจุบัน (ord) หรือ SPECIAL | scancode
    unicode: str       # ตัวอักษรที่พิมพ์ได้จริง ('a', 'ฟ', '' ถ้าไม่มี) มีเฉพาะ KEYDOWN
    mod: int           # MOD_* ตอนเกิด event
    layout: Layout     # layout ที่ active (ดู .lang ว่า 'th' หรือ 'en')
    name: str          # ชื่อปุ่มกายภาพจาก KEY_MAPPINGS เช่น 'A', 'Enter', 'lshift'
    vk: int            # virtual-key (Windows, Linux ได้จากตาราง)
    repeat: bool       # True ถ้าเป็นการกดค้าง (auto-repeat)
    injected: bool     # True ถ้าถูกจำลองโดยโปรแกรมอื่น (SendInput / uinput)
    time: float        # time.time() ตอนรับ event

    @property
    def is_down(self) -> bool:
        return self.type == KEYDOWN

    def __str__(self):
        u = repr(self.unicode) if self.unicode else "None"
        return (f"<Key(name: {self.name}, unicode: {u}, key: {self.key}, mod: {self.mod}, "
                f"scancode: {self.scancode}, VK:{self.vk}, layout: {self.layout.locale})>")


# event ดิบจาก backend (ยังไม่ผ่าน layout) — backend ทุกตัวส่งรูปแบบนี้เข้า core
RawKey = namedtuple("RawKey", "vk scancode down injected")
