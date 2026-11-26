"""ทดสอบการรู้ layout บน Linux ด้วย libxkbcommon จริง (ข้ามอัตโนมัติถ้าไม่มี libxkbcommon / xkb-data)
ไม่ต้องใช้ root หรือคีย์บอร์ดจริง: ใช้ evdev device จำลอง"""
import os
import queue
import sys
import unittest
import warnings
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from hexss.keyboard import _nixkeyboard as nix
    from hexss.keyboard import _xkb as xkb
    from hexss.keyboard._xkb import XkbConfig, XkbMirror
    _probe = XkbMirror(XkbConfig(None, None, "us,th", None, "grp:alt_shift_toggle", "probe"))
    _probe.close()
    HAVE_XKB = True
    SKIP_REASON = ""
except Exception as e:          # ไม่ใช่ Linux / ไม่มี libxkbcommon / ไม่มี xkb-data
    HAVE_XKB = False
    SKIP_REASON = f"libxkbcommon unavailable: {e}"

import hexss.keyboard as kb
from hexss.keyboard._core import Keyboard

# evdev keycodes
KEY_ESC, KEY_1, KEY_BACKSPACE, KEY_ENTER, KEY_A, KEY_S = 1, 2, 14, 28, 30, 31
KEY_LSHIFT, KEY_LALT, KEY_CAPS, KEY_SPACE, KEY_F1, KEY_KP7 = 42, 56, 58, 57, 59, 71
EV_KEY = 1
US_TH = XkbConfig(None, None, "us,th", None, "grp:alt_shift_toggle", "test") if HAVE_XKB else None


@unittest.skipUnless(HAVE_XKB, SKIP_REASON)
class MirrorTests(unittest.TestCase):
    def setUp(self):
        self.m = XkbMirror(US_TH)

    def tearDown(self):
        self.m.close()

    def toggle(self):
        for code, down in ((KEY_LALT, True), (KEY_LSHIFT, True), (KEY_LSHIFT, False), (KEY_LALT, False)):
            self.m.update(code, down)

    def test_starts_on_first_layout(self):
        self.assertEqual(self.m.group(), 0)
        self.assertEqual(self.m.layout().lang, "en")
        self.assertEqual(self.m.text(KEY_A), "a")

    def test_alt_shift_switches_to_thai_and_back(self):
        self.toggle()
        self.assertEqual((self.m.layout().lang, self.m.layout().locale), ("th", "th-TH"))
        self.assertEqual(self.m.text(KEY_A), "ฟ")
        self.assertEqual(self.m.text(KEY_1), "ๅ")
        self.toggle()
        self.assertEqual(self.m.layout().lang, "en")
        self.assertEqual(self.m.text(KEY_A), "a")

    def test_shift_in_thai(self):
        self.toggle()
        self.m.update(KEY_LSHIFT, True)
        self.assertEqual(self.m.text(KEY_A), "ฤ")
        self.assertEqual(self.m.text(KEY_1), "+")

    def test_base_char_ignores_modifiers_and_follows_group(self):
        self.m.update(KEY_LSHIFT, True)                       # ถึงกด shift อยู่ ก็ต้องได้ตัวไม่ shift
        self.assertEqual(self.m.base_char(KEY_A, 0), "a")
        self.assertEqual(self.m.base_char(KEY_A, 1), "ฟ")
        self.assertEqual(self.m.base_char(KEY_A), "a")        # group ปัจจุบัน = 0

    def test_special_keys(self):
        self.assertEqual(self.m.text(KEY_ENTER), "\r")
        self.assertEqual(self.m.text(KEY_SPACE), " ")
        self.assertEqual(self.m.base_char(KEY_ESC), "\x1b")
        self.assertEqual(self.m.base_char(KEY_BACKSPACE), "\x08")
        self.assertEqual(self.m.base_char(KEY_LSHIFT), "")
        self.assertEqual(self.m.base_char(KEY_F1), "")

    def test_capslock(self):
        self.m.update(KEY_CAPS, True); self.m.update(KEY_CAPS, False)
        self.assertEqual(self.m.text(KEY_A), "A")
        self.m.update(KEY_CAPS, True); self.m.update(KEY_CAPS, False)
        self.assertEqual(self.m.text(KEY_A), "a")

    def test_set_group_and_locks(self):
        self.m.set_group(1)
        self.assertEqual(self.m.layout().lang, "th")
        self.m.set_group(0)
        self.m.set_locks(caps=True, num=False)
        self.assertEqual(self.m.text(KEY_A), "A")
        with self.assertRaises(ValueError):
            self.m.set_group(5)

    def test_layout_names(self):
        self.assertEqual(self.m.layout_names(), ["English (US)", "Thai"])

    def test_close_is_safe(self):
        self.m.close()
        self.assertEqual(self.m.text(KEY_A), "")
        self.assertEqual(self.m.group(), 0)
        self.m.update(KEY_A, True)
        self.m.close()

    def test_bad_config_raises(self):
        # rules ที่ไม่มีอยู่ทำให้คอมไพล์ keymap ไม่ได้ (option ที่ไม่รู้จักแค่ถูกข้าม ไม่ใช่ error)
        with self.assertRaises(RuntimeError):
            XkbMirror(XkbConfig("nonexistent-rules", None, "us", None, None, "bad"))


class ConfigDetectionTests(unittest.TestCase):
    def test_parse_assignments(self):
        text = '# comment\nXKBMODEL="pc105"\nXKBLAYOUT="us,th"\nexport A=1\n\nXKBOPTIONS=\'grp:alt_shift_toggle\'\nbad line\n'
        self.assertEqual(xkb._parse_assignments(text),
                         {"XKBMODEL": "pc105", "XKBLAYOUT": "us,th", "A": "1", "XKBOPTIONS": "grp:alt_shift_toggle"})

    def test_parse_setxkbmap(self):
        text = "rules:      evdev\nmodel:      pc105\nlayout:     us,th\nvariant:    ,\noptions:    grp:alt_shift_toggle\n"
        q = xkb._parse_setxkbmap(text)
        self.assertEqual((q["layout"], q["variant"], q["options"]), ("us,th", ",", "grp:alt_shift_toggle"))

    def test_env_has_priority(self):
        env = {"XKB_DEFAULT_LAYOUT": "us,th", "XKB_DEFAULT_OPTIONS": "grp:win_space_toggle"}
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = xkb.detect_config()
        self.assertEqual((cfg.layout, cfg.options), ("us,th", "grp:win_space_toggle"))
        self.assertIn("XKB_DEFAULT", cfg.source)

    def test_labwc_environment_file(self):
        text = "XKB_DEFAULT_LAYOUT=us,th\nXKB_DEFAULT_OPTIONS=grp:alt_shift_toggle\n"
        with mock.patch.object(xkb, "_read", side_effect=lambda p: text if p.endswith("labwc/environment") else None):
            cfg = xkb._from_labwc()
        self.assertEqual((cfg.layout, cfg.options), ("us,th", "grp:alt_shift_toggle"))

    def test_wayfire_ini(self):
        text = "[core]\nplugins = a b\n\n[input]\nxkb_layout = us,th\nxkb_options = grp:alt_shift_toggle\n"
        with mock.patch.object(xkb, "_read", side_effect=lambda p: text if p.endswith("wayfire.ini") else None):
            cfg = xkb._from_wayfire()
        self.assertEqual((cfg.layout, cfg.options), ("us,th", "grp:alt_shift_toggle"))

    def test_etc_default_keyboard(self):
        text = 'XKBMODEL="pc105"\nXKBLAYOUT="us,th"\nXKBVARIANT=""\nXKBOPTIONS="grp:alt_shift_toggle"\n'
        with mock.patch.object(xkb, "_read", return_value=text):
            cfg = xkb._from_etc_default()
        self.assertEqual((cfg.model, cfg.layout, cfg.variant, cfg.options), ("pc105", "us,th", "", "grp:alt_shift_toggle"))

    def test_falls_back_to_us(self):
        none = lambda: None
        with mock.patch.multiple(xkb, _from_env=none, _from_labwc=none, _from_wayfire=none,
                                 _from_setxkbmap=none, _from_etc_default=none):
            cfg = xkb.detect_config()
        self.assertEqual((cfg.layout, cfg.source), ("us", "default"))

    def test_unknown_layout_code_still_gets_a_lang(self):
        layout = xkb.make_layout(2, "xx")
        self.assertEqual((layout.lang, layout.langid), ("xx", 0))
        self.assertEqual(xkb.make_layout(1, "th").langid, 0x041E)


class FakeDevice:
    """แทน AggregatedEventDevice: อ่าน event จากคิว"""
    devices = []

    def __init__(self):
        self.event_queue = queue.Queue()

    def read_event(self, timeout=None):
        return self.event_queue.get(timeout=timeout)

    def push(self, code, value, path="/dev/input/event0"):
        self.event_queue.put((0.0, EV_KEY, code, value, path))

    def tap(self, code):
        self.push(code, 1)
        self.push(code, 0)


@unittest.skipUnless(HAVE_XKB, SKIP_REASON)
class EndToEndTests(unittest.TestCase):
    """evdev event -> Backend (xkb) -> core -> KeyEvent"""

    def setUp(self):
        nix.set_xkb("us,th", options="grp:alt_shift_toggle")
        patcher = mock.patch.object(nix, "ensure_input_access")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dev = FakeDevice()
        self.be = nix.Backend()
        self.be._device = self.dev
        self.k = Keyboard(backend=self.be)
        self.k.start()
        self.addCleanup(nix.set_xkb)            # ล้าง override
        self.addCleanup(self.k.stop)

    def next_down(self):
        while True:
            ev = self.k.wait(1.0)
            self.assertIsNotNone(ev, "timeout waiting for event")
            if ev.is_down:
                return ev

    def switch_language(self):
        """สลับภาษาด้วย Alt+Shift แล้วรอจน backend ประมวลผลครบ (ใช้ F1 เป็นตัวบอกว่าถึงท้ายแล้ว)"""
        for code, value in ((KEY_LALT, 1), (KEY_LSHIFT, 1), (KEY_LSHIFT, 0), (KEY_LALT, 0), (KEY_F1, 1), (KEY_F1, 0)):
            self.dev.push(code, value)
        while True:
            ev = self.k.wait(1.0)
            self.assertIsNotNone(ev, "timeout waiting for the language switch to be processed")
            if ev.scancode == 0x3B and not ev.is_down:
                break
        self.k.clear()

    def test_english_then_thai(self):
        self.dev.tap(KEY_A)
        ev = self.next_down()
        self.assertEqual((ev.unicode, ev.layout.lang, ev.key, ev.name, ev.scancode),
                         ("a", "en", ord("a"), "A", 0x1E))

        self.switch_language()
        self.dev.tap(KEY_A)
        ev = self.next_down()
        self.assertEqual((ev.unicode, ev.layout.lang, ev.key, ev.scancode),
                         ("ฟ", "th", ord("ฟ"), 0x1E))               # scancode เท่าเดิม ตัวอักษรเปลี่ยน

    def test_shift_and_capslock_in_thai(self):
        self.switch_language()
        self.dev.push(KEY_LSHIFT, 1); self.dev.push(KEY_A, 1); self.dev.push(KEY_A, 0); self.dev.push(KEY_LSHIFT, 0)
        ev = [e for e in iter(lambda: self.k.wait(1.0), None) if e.is_down and e.scancode == 0x1E][0]
        self.assertEqual((ev.unicode, ev.layout.lang), ("ฤ", "th"))
        self.assertTrue(ev.mod & kb.MOD_SHIFT)

    def test_ctrl_a_has_no_text_and_keypad_is_special(self):
        self.dev.push(0x1D, 1)
        self.dev.push(KEY_A, 1)
        ev = [e for e in iter(lambda: self.k.wait(1.0), None) if e.is_down and e.scancode == 0x1E][0]
        self.assertEqual(ev.unicode, "")
        self.dev.push(0x1D, 0); self.dev.push(KEY_A, 0)
        self.dev.tap(KEY_KP7)
        ev = [e for e in iter(lambda: self.k.wait(1.0), None) if e.is_down and e.scancode == 0x47][0]
        self.assertEqual(ev.key, kb.SPECIAL | 0x47)

    def test_enter_key_and_repeat_not_fed_twice(self):
        self.dev.tap(KEY_ENTER)
        ev = self.next_down()
        self.assertEqual((ev.unicode, ev.key), ("\r", 13))
        # กดค้าง (value=2) ต้องไม่ทำให้ state ของ xkb เพี้ยน: ปล่อยแล้ว CapsLock ยังสลับแค่ครั้งเดียว
        self.dev.push(KEY_CAPS, 1); self.dev.push(KEY_CAPS, 2); self.dev.push(KEY_CAPS, 2); self.dev.push(KEY_CAPS, 0)
        self.dev.tap(KEY_A)
        ev = [e for e in iter(lambda: self.k.wait(1.0), None) if e.is_down and e.scancode == 0x1E][0]
        self.assertEqual(ev.unicode, "A")

    def test_get_layout_and_set_group(self):
        self.assertEqual(self.k.get_layout().lang, "en")
        nix.set_xkb_group(1)
        self.assertEqual(self.k.get_layout().lang, "th")
        self.dev.tap(KEY_A)
        self.assertEqual(self.next_down().unicode, "ฟ")

    def test_set_xkb_while_running_resets_layouts(self):
        nix.set_xkb("th,us", options="grp:alt_shift_toggle")      # สลับลำดับ: ไทยเป็นภาษาแรก
        self.assertEqual(self.k.get_layout().lang, "th")
        self.dev.tap(KEY_A)
        self.assertEqual(self.next_down().unicode, "ฟ")


class FallbackTests(unittest.TestCase):
    def test_falls_back_to_us_table_when_xkb_unavailable(self):
        be = nix.Backend() if hasattr(nix, "Backend") else None
        if be is None:
            self.skipTest("not Linux")
        with mock.patch.object(nix, "XkbMirror", side_effect=RuntimeError("no lib")):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                layout = be.get_layout()
        self.assertEqual(layout.locale, "en-US")
        self.assertEqual(be.translate(0, 0x1E, True, False, False, False, 0), "A")
        self.assertEqual(be.unmodified_char(0, 0x1E, 0), "a")
        self.assertTrue(any("libxkbcommon" in str(x.message) for x in w))
        self.assertEqual(len(w), 1)             # เตือนครั้งเดียว ไม่เตือนซ้ำทุก event


if __name__ == "__main__":
    unittest.main()
