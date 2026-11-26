"""libxkbcommon ผ่าน ctypes (ไม่ต้อง pip install อะไรเพิ่ม) — ใช้บน Linux เพื่อ
  - รู้ว่า layout ปัจจุบันคืออะไร (ไทย/อังกฤษ ...)
  - แปลง keycode -> ตัวอักษรตาม layout นั้น

หลักการ: evdev ให้แค่รหัสปุ่มกายภาพ และบอกไม่ได้ว่า desktop ใช้ layout ไหนอยู่
เราจึง "จำลอง" xkb state เดียวกับที่ desktop ใช้ (อ่านค่า layout/options จากระบบ) แล้วป้อนทุก event เข้าไป
เมื่อผู้ใช้กดปุ่มสลับภาษา (เช่น Alt+Shift) state ของเราก็สลับตาม

ข้อจำกัด:
  - ต้องตั้งค่า layout ตรงกับของ desktop (ตรวจอัตโนมัติ หรือบอกเองด้วย set_xkb)
  - state เริ่มที่ layout แรกเสมอ ถ้าเปิดโปรแกรมตอนอยู่ภาษาอื่นอยู่ ให้ใช้ set_xkb_group(index)
  - ใช้ไม่ได้ถ้าสลับภาษาด้วย input method (ibus/fcitx) หรือการตั้งค่าของ desktop ที่ไม่ใช้ XKB group
"""
import configparser
import ctypes
import ctypes.util
import os
import shutil
import subprocess
import threading
from collections import namedtuple

from .events import Layout

XkbConfig = namedtuple("XkbConfig", "rules model layout variant options source")

XKB_KEY_UP, XKB_KEY_DOWN = 0, 1
XKB_STATE_MODS_DEPRESSED = 1 << 0
XKB_STATE_MODS_LATCHED = 1 << 1
XKB_STATE_MODS_LOCKED = 1 << 2
XKB_STATE_LAYOUT_DEPRESSED = 1 << 4
XKB_STATE_LAYOUT_LATCHED = 1 << 5
XKB_STATE_LAYOUT_LOCKED = 1 << 6
XKB_STATE_LAYOUT_EFFECTIVE = 1 << 7
XKB_MOD_INVALID = 0xFFFFFFFF
EVDEV_OFFSET = 8  # xkb keycode = evdev code + 8

# รหัส layout ของ xkb -> (LANGID แบบ Windows, locale)
_LANG = {
    "us": (0x0409, "en-US"), "gb": (0x0809, "en-GB"), "th": (0x041E, "th-TH"),
    "jp": (0x0411, "ja-JP"), "kr": (0x0412, "ko-KR"), "cn": (0x0804, "zh-CN"), "tw": (0x0404, "zh-TW"),
    "de": (0x0407, "de-DE"), "fr": (0x040C, "fr-FR"), "es": (0x040A, "es-ES"), "it": (0x0410, "it-IT"),
    "ru": (0x0419, "ru-RU"), "ua": (0x0422, "uk-UA"), "pl": (0x0415, "pl-PL"), "tr": (0x041F, "tr-TR"),
    "pt": (0x0816, "pt-PT"), "br": (0x0416, "pt-BR"), "vn": (0x042A, "vi-VN"),
    "ara": (0x0401, "ar-SA"), "il": (0x040D, "he-IL"),
}


def make_layout(index: int, code: str) -> Layout:
    langid, locale = _LANG.get(code, (0, code))
    return Layout(index, langid, locale)


# ---------------------------------------------------------------------------
# libxkbcommon
# ---------------------------------------------------------------------------
class _RuleNames(ctypes.Structure):
    _fields_ = [("rules", ctypes.c_char_p), ("model", ctypes.c_char_p), ("layout", ctypes.c_char_p),
                ("variant", ctypes.c_char_p), ("options", ctypes.c_char_p)]


_lib = None
_lib_lock = threading.Lock()


def _load():
    global _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        lib = ctypes.CDLL(ctypes.util.find_library("xkbcommon") or "libxkbcommon.so.0")
        vp, u32, i32, cp = ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_char_p
        sigs = {
            "xkb_context_new": (vp, [i32]),
            "xkb_context_unref": (None, [vp]),
            "xkb_keymap_new_from_names": (vp, [vp, ctypes.POINTER(_RuleNames), i32]),
            "xkb_keymap_unref": (None, [vp]),
            "xkb_keymap_num_layouts": (u32, [vp]),
            "xkb_keymap_layout_get_name": (cp, [vp, u32]),
            "xkb_keymap_mod_get_index": (u32, [vp, cp]),
            "xkb_keymap_key_get_syms_by_level": (
                i32, [vp, u32, u32, u32, ctypes.POINTER(ctypes.POINTER(u32))]),
            "xkb_keysym_to_utf32": (u32, [u32]),
            "xkb_state_new": (vp, [vp]),
            "xkb_state_unref": (None, [vp]),
            "xkb_state_update_key": (i32, [vp, u32, i32]),
            "xkb_state_update_mask": (i32, [vp, u32, u32, u32, u32, u32, u32]),
            "xkb_state_key_get_utf8": (i32, [vp, u32, ctypes.c_char_p, ctypes.c_size_t]),
            "xkb_state_serialize_layout": (u32, [vp, i32]),
            "xkb_state_serialize_mods": (u32, [vp, i32]),
        }
        for name, (restype, argtypes) in sigs.items():
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = restype, argtypes
        _lib = lib
        return lib


def _b(value):
    return value.encode() if value else None


class XkbMirror:
    """xkb state จำลอง: ป้อน event ด้วย update() แล้วถามตัวอักษร/layout ปัจจุบันได้"""

    def __init__(self, config: XkbConfig):
        lib = _load()
        self._lib = lib
        self._lock = threading.RLock()
        self.config = config
        names = _RuleNames(_b(config.rules), _b(config.model), _b(config.layout),
                           _b(config.variant), _b(config.options))
        self._ctx = lib.xkb_context_new(0)
        if not self._ctx:
            raise RuntimeError("xkb_context_new failed")
        self._keymap = lib.xkb_keymap_new_from_names(self._ctx, ctypes.byref(names), 0)
        if not self._keymap:
            lib.xkb_context_unref(self._ctx)
            self._ctx = None
            raise RuntimeError(
                f"cannot compile xkb keymap (layout={config.layout!r}, variant={config.variant!r}, "
                f"options={config.options!r}) — check xkb-data is installed")
        self._state = lib.xkb_state_new(self._keymap)
        count = lib.xkb_keymap_num_layouts(self._keymap)
        codes = [c.strip() for c in (config.layout or "us").split(",")]
        self.layouts = tuple(
            make_layout(i, codes[i] if i < len(codes) and codes[i] else "us") for i in range(count))

    # ------------------------------------------------------------ state
    def update(self, evdev_code: int, down: bool) -> None:
        """ป้อน event จริง (กดครั้งแรก/ปล่อย — ไม่ต้องป้อนตอนกดค้าง)"""
        with self._lock:
            if self._state:
                self._lib.xkb_state_update_key(
                    self._state, evdev_code + EVDEV_OFFSET, XKB_KEY_DOWN if down else XKB_KEY_UP)

    def group(self) -> int:
        with self._lock:
            if not self._state:
                return 0
            return self._lib.xkb_state_serialize_layout(self._state, XKB_STATE_LAYOUT_EFFECTIVE)

    def layout(self) -> Layout:
        g = self.group()
        return self.layouts[g] if g < len(self.layouts) else self.layouts[0]

    def layout_names(self) -> list:
        with self._lock:
            if not self._keymap:
                return []
            names = []
            for i in range(len(self.layouts)):
                raw = self._lib.xkb_keymap_layout_get_name(self._keymap, i)
                names.append(raw.decode("utf-8", "replace") if raw else "")
            return names

    def text(self, evdev_code: int) -> str:
        """ตัวอักษรของปุ่มนี้ภายใต้ state ปัจจุบัน (รวม Shift/CapsLock/layout) — '' ถ้าไม่มี"""
        with self._lock:
            if not self._state:
                return ""
            buf = ctypes.create_string_buffer(32)
            n = self._lib.xkb_state_key_get_utf8(self._state, evdev_code + EVDEV_OFFSET, buf, 32)
            return buf.value.decode("utf-8", "replace") if n > 0 else ""

    def base_char(self, evdev_code: int, group=None) -> str:
        """ตัวอักษรของปุ่มนี้ตอนไม่กด modifier ใน layout `group` (level 0) — '' ถ้าไม่มี"""
        with self._lock:
            if not self._keymap:
                return ""
            g = self.group() if group is None else group
            syms = ctypes.POINTER(ctypes.c_uint32)()
            n = self._lib.xkb_keymap_key_get_syms_by_level(
                self._keymap, evdev_code + EVDEV_OFFSET, g, 0, ctypes.byref(syms))
            if n < 1:
                return ""
            cp = self._lib.xkb_keysym_to_utf32(syms[0])
            return chr(cp) if cp else ""

    def _components(self):
        s, lib = self._state, self._lib
        mods = [lib.xkb_state_serialize_mods(s, c) for c in
                (XKB_STATE_MODS_DEPRESSED, XKB_STATE_MODS_LATCHED, XKB_STATE_MODS_LOCKED)]
        layouts = [lib.xkb_state_serialize_layout(s, c) for c in
                   (XKB_STATE_LAYOUT_DEPRESSED, XKB_STATE_LAYOUT_LATCHED, XKB_STATE_LAYOUT_LOCKED)]
        return mods, layouts

    def set_locks(self, caps: bool, num: bool) -> None:
        """ตั้งสถานะ CapsLock / NumLock ตอนเริ่ม (อ่านจาก LED)"""
        with self._lock:
            if not self._state:
                return
            mask = 0
            for name, on in ((b"Lock", caps), (b"Mod2", num)):
                if on:
                    idx = self._lib.xkb_keymap_mod_get_index(self._keymap, name)
                    if idx != XKB_MOD_INVALID:
                        mask |= 1 << idx
            mods, layouts = self._components()
            self._lib.xkb_state_update_mask(
                self._state, mods[0], mods[1], mods[2] | mask, layouts[0], layouts[1], layouts[2])

    def set_group(self, index: int) -> None:
        """บังคับ layout ปัจจุบัน (ใช้ซิงก์ตอนเปิดโปรแกรมขณะอยู่ภาษาที่ไม่ใช่ภาษาแรก)"""
        with self._lock:
            if not self._state:
                return
            if not 0 <= index < len(self.layouts):
                raise ValueError(f"layout index {index} out of range (0..{len(self.layouts) - 1})")
            mods, layouts = self._components()
            self._lib.xkb_state_update_mask(
                self._state, mods[0], mods[1], mods[2], layouts[0], layouts[1], index)

    def close(self) -> None:
        with self._lock:
            lib = self._lib
            if self._state:
                lib.xkb_state_unref(self._state)
                self._state = None
            if self._keymap:
                lib.xkb_keymap_unref(self._keymap)
                self._keymap = None
            if self._ctx:
                lib.xkb_context_unref(self._ctx)
                self._ctx = None


# ---------------------------------------------------------------------------
# ตรวจ layout/options ที่ระบบใช้
# ---------------------------------------------------------------------------
def _parse_assignments(text: str) -> dict:
    """KEY=value / KEY="value" / export KEY=value (ไฟล์ environment ของ labwc, /etc/default/keyboard)"""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip("\"'")
    return out


def _parse_setxkbmap(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def _real_home() -> str:
    """home ของผู้ใช้จริง (ถ้าสคริปต์ถูกรันด้วย sudo ให้ใช้ของผู้ที่เรียก sudo)"""
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            import pwd
            return pwd.getpwnam(user).pw_dir
        except (ImportError, KeyError):
            pass
    return os.path.expanduser("~")


def _read(path: str):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return None


def _from_xkb_default(values: dict, source: str):
    if not (values.get("XKB_DEFAULT_LAYOUT") or values.get("XKB_DEFAULT_OPTIONS")):
        return None
    return XkbConfig(
        values.get("XKB_DEFAULT_RULES"), values.get("XKB_DEFAULT_MODEL"),
        values.get("XKB_DEFAULT_LAYOUT") or "us", values.get("XKB_DEFAULT_VARIANT"),
        values.get("XKB_DEFAULT_OPTIONS"), source
    )


def _from_env():
    return _from_xkb_default(os.environ, "environment XKB_DEFAULT_*")


def _from_labwc():
    for path in (os.path.join(_real_home(), ".config/labwc/environment"), "/etc/xdg/labwc/environment"):
        text = _read(path)
        if text:
            cfg = _from_xkb_default(_parse_assignments(text), path)
            if cfg:
                return cfg
    return None


def _from_wayfire():
    path = os.path.join(_real_home(), ".config/wayfire.ini")
    text = _read(path)
    if not text:
        return None
    parser = configparser.RawConfigParser(strict=False)
    parser.read_string(text)
    if not parser.has_section("input"):
        return None
    get = lambda k: (parser.get("input", k, fallback="") or "").strip() or None
    layout = get("xkb_layout")
    if not layout:
        return None
    return XkbConfig(
        None, get("xkb_model"), layout, get("xkb_variant"), get("xkb_options"), path
    )


def _from_setxkbmap():
    if not shutil.which("setxkbmap") or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    result = subprocess.run(["setxkbmap", "-query"], capture_output=True, text=True, timeout=2)
    if result.returncode != 0:
        return None
    q = _parse_setxkbmap(result.stdout)
    if not q.get("layout"):
        return None
    return XkbConfig(
        q.get("rules"), q.get("model"), q["layout"], q.get("variant"), q.get("options"), "setxkbmap -query"
    )


def _from_etc_default():
    text = _read("/etc/default/keyboard")
    if not text:
        return None
    v = _parse_assignments(text)
    if not v.get("XKBLAYOUT"):
        return None
    return XkbConfig(
        None, v.get("XKBMODEL"), v["XKBLAYOUT"], v.get("XKBVARIANT"), v.get("XKBOPTIONS"), "/etc/default/keyboard"
    )


def detect_config() -> XkbConfig:
    """ลำดับ: environment -> labwc -> wayfire -> setxkbmap -> /etc/default/keyboard -> us"""
    for probe in (_from_env, _from_labwc, _from_wayfire, _from_setxkbmap, _from_etc_default):
        try:
            cfg = probe()
        except Exception:
            cfg = None
        if cfg:
            return cfg
    return XkbConfig(None, None, "us", None, None, "default")
