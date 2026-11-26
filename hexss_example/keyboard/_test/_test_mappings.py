"""ทดสอบตารางปุ่ม และฟังก์ชันของ backend Linux ที่ไม่ต้องใช้ root/ฮาร์ดแวร์"""
import os
import sys
import unittest
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from hexss.keyboard import key_mappings as km


class MappingTests(unittest.TestCase):
    def test_main_enter_exists(self):
        self.assertEqual(km.scancode_of("enter"), 0x1C)
        self.assertEqual(km.scancode_of("Return"), 0x1C)
        self.assertEqual(km.scancode_of("numpad enter"), 0xE01C)

    def test_char_table_shift_flags(self):
        cases = {
            ";": (0x27, False), ":": (0x27, True),
            "-": (0x0C, False), "_": (0x0C, True),
            "=": (0x0D, False), "+": (0x0D, True),
            "[": (0x1A, False), "{": (0x1A, True),
            "'": (0x28, False), '"': (0x28, True),
            "a": (0x1E, False), "A": (0x1E, True),
            "1": (0x02, False), "!": (0x02, True),
            " ": (0x39, False),
        }
        for ch, expected in cases.items():
            self.assertEqual(km.CHAR_TO_KEY[ch], expected, ch)

    def test_us_char(self):
        self.assertEqual(km.us_char(0x1E), "a")
        self.assertEqual(km.us_char(0x1E, shift=True), "A")
        self.assertEqual(km.us_char(0x1E, caps=True), "A")
        self.assertEqual(km.us_char(0x1E, shift=True, caps=True), "a")
        self.assertEqual(km.us_char(0x02, shift=True), "!")
        self.assertEqual(km.us_char(0x02, caps=True), "1")
        self.assertEqual(km.us_char(0x1C), "\r")
        self.assertEqual(km.us_char(0x0E), "\x08")
        self.assertEqual(km.us_char(0x39), " ")
        self.assertEqual(km.us_char(0x3B), "")       # F1

    def test_name_aliases_prefer_extended(self):
        self.assertEqual(km.scancode_of("home"), 0xE047)
        self.assertEqual(km.scancode_of("delete"), 0xE053)
        self.assertEqual(km.scancode_of("keypad-7"), 0x47)
        self.assertEqual(km.scancode_of("ctrl"), 0x1D)
        self.assertEqual(km.scancode_of("altgr"), 0xE038)
        with self.assertRaises(ValueError):
            km.scancode_of("nope")

    def test_resolve_scancodes(self):
        self.assertEqual(km.resolve_scancodes("shift"), frozenset({0x2A, 0x36}))
        self.assertEqual(km.resolve_scancodes("lshift"), frozenset({0x2A}))
        self.assertEqual(km.resolve_scancodes(key=0x1E), frozenset({0x1E}))
        self.assertEqual(km.resolve_scancodes(scancode=0xE047), frozenset({0xE047}))
        self.assertIn(0x1E, km.resolve_scancodes(vk=0x41))
        with self.assertRaises(ValueError):
            km.resolve_scancodes()
        with self.assertRaises(ValueError):
            km.resolve_scancodes(vk=0xFFFF)
        with self.assertRaises(TypeError):
            km.resolve_scancodes(key=1.5)

    def test_parse_hotkey(self):
        self.assertEqual(km.parse_hotkey("ctrl + shift + a"), ["ctrl", "shift", "a"])
        self.assertEqual(km.parse_hotkey("+"), ["+"])
        self.assertEqual(km.parse_hotkey("ctrl++"), ["ctrl", "+"])
        self.assertEqual(km.parse_hotkey(" "), ["space"])
        self.assertEqual(km.parse_hotkey(""), [])


class NixHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from keyboard import _nixkeyboard as nix
        except ImportError as e:            # ไม่ใช่ Linux
            raise unittest.SkipTest(str(e))
        cls.nix = nix

    def test_raw_from_event(self):
        nix = self.nix
        raw = nix.raw_from_event(1, 30, 1)
        self.assertEqual((raw.scancode, raw.vk, raw.down, raw.injected), (0x1E, 0x41, True, False))
        self.assertFalse(nix.raw_from_event(1, 30, 0).down)
        self.assertTrue(nix.raw_from_event(1, 30, 2).down)                  # auto-repeat
        self.assertEqual(nix.raw_from_event(1, 103, 1).scancode, 0xE048)    # KEY_UP -> E0 48
        self.assertEqual(nix.raw_from_event(1, 97, 1).scancode, 0xE01D)     # right ctrl
        self.assertIsNone(nix.raw_from_event(1, 0x110, 1))                  # BTN_LEFT
        self.assertIsNone(nix.raw_from_event(0, 0, 0))                      # EV_SYN
        self.assertTrue(nix.raw_from_event(1, 30, 1, injected=True).injected)

    def test_linux_code_roundtrip(self):
        nix = self.nix
        for sc in (0x1E, 0x1C, 0xE01C, 0xE048, 0xE038):
            self.assertEqual(nix.raw_from_event(1, nix.linux_code(sc), 1).scancode, sc)

    def test_write_uses_correct_shift(self):
        nix = self.nix
        events = []
        orig_write_event, orig_send = nix.keyboard._write_event, nix.keyboard.send
        nix.keyboard._write_event = classmethod(lambda cls, t, c, v: events.append((c, v)))
        try:
            nix.keyboard.write("a;A _\n", interval=0)
        finally:
            nix.keyboard._write_event = orig_write_event
        down = [(c, v) for c, v in events if v == 1]
        # a ; (Shift)A space (Shift)_  Enter
        self.assertEqual(down, [(30, 1), (39, 1), (42, 1), (30, 1), (57, 1), (42, 1), (12, 1), (28, 1)])

    def test_write_warns_for_unsupported(self):
        nix = self.nix
        orig = nix.keyboard._write_event
        nix.keyboard._write_event = classmethod(lambda cls, t, c, v: None)
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                nix.keyboard.write("ก", interval=0)
        finally:
            nix.keyboard._write_event = orig
        self.assertEqual(len(w), 1)
        self.assertIn("ก", str(w[0].message))

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            self.nix.keyboard.send("ctrl+nope")

    # ---- สิทธิ์: ไม่บังคับ root ถ้ามีสิทธิ์เข้าถึงอุปกรณ์อยู่แล้ว ----
    def _patched(self, euid, access_ok, devices, uinput_exists=True):
        from unittest import mock
        from hexss.keyboard import _nixcommon as nc
        accessible = set(access_ok)
        stack = [
            mock.patch.object(nc.os, "geteuid", return_value=euid),
            mock.patch.object(nc.os, "access", side_effect=lambda path, mode: path in accessible),
            mock.patch.object(nc.os.path, "exists", return_value=uinput_exists),
            mock.patch.object(nc, "list_devices_from_proc", return_value=iter([nc.EventDevice(d) for d in devices])),
            mock.patch.object(nc, "list_devices_from_by_id", return_value=iter([])),
        ]
        return nc, stack

    def _run(self, stack, fn):
        from contextlib import ExitStack
        with ExitStack() as es:
            for m in stack:
                es.enter_context(m)
            return fn()

    def test_input_access_root_always_ok(self):
        nc, st = self._patched(0, [], ["/dev/input/event3"])
        self._run(st, nc.ensure_input_access)

    def test_input_access_group_member_ok_without_root(self):
        nc, st = self._patched(1000, ["/dev/input/event3"], ["/dev/input/event3"])
        self._run(st, nc.ensure_input_access)

    def test_input_access_denied_has_helpful_message(self):
        nc, st = self._patched(1000, [], ["/dev/input/event3"])
        with self.assertRaises(PermissionError) as cm:
            self._run(st, nc.ensure_input_access)
        self.assertIn("usermod -aG input", str(cm.exception))

    def test_input_access_no_devices_is_not_a_permission_error(self):
        nc, st = self._patched(1000, [], [])
        self._run(st, nc.ensure_input_access)       # Backend.start จะแจ้ง "No keyboard input devices found" เอง

    def test_uinput_access(self):
        nc, st = self._patched(1000, ["/dev/uinput"], [])
        self._run(st, nc.ensure_uinput_access)
        nc, st = self._patched(1000, [], [])
        with self.assertRaises(PermissionError) as cm:
            self._run(st, nc.ensure_uinput_access)
        self.assertIn("99-uinput.rules", str(cm.exception))
        nc, st = self._patched(1000, [], [], uinput_exists=False)
        with self.assertRaises(FileNotFoundError) as cm:
            self._run(st, nc.ensure_uinput_access)
        self.assertIn("modprobe uinput", str(cm.exception))
        nc, st = self._patched(0, [], [], uinput_exists=False)
        self._run(st, nc.ensure_uinput_access)      # root ผ่านเสมอ


if __name__ == "__main__":
    unittest.main()
