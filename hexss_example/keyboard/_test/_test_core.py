import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import hexss.keyboard as kb
from hexss.keyboard._core import Keyboard
from hexss.keyboard.events import Layout, RawKey

EN = Layout(0x04090409, 0x0409, "en-US")
TH = Layout(0x041E041E, 0x041E, "th-TH")

# scancode -> (ปกติ, shift)
TABLE = {
    EN.hkl: {0x1E: ("a", "A"), 0x02: ("1", "!"), 0x39: (" ", " "), 0x1C: ("\r", "\r")},
    TH.hkl: {0x1E: ("ฟ", "ฤ"), 0x02: ("ๅ", "+"), 0x39: (" ", " "), 0x1C: ("\r", "\r")},
}
A, SPACE, ENTER = 0x1E, 0x39, 0x1C
LSHIFT, LCTRL, CAPS = 0x2A, 0x1D, 0x3A


class FakeBackend:
    native_state = False
    supports_suppress = True

    def __init__(self, toggles=0):
        self.layout = EN
        self.on_raw = None
        self.toggles = toggles
        self.started = 0
        self.stopped = 0

    def start(self, on_raw):
        self.on_raw = on_raw
        self.started += 1

    def stop(self):
        self.stopped += 1

    def get_layout(self):
        return self.layout

    def toggle_state(self):
        return self.toggles

    def is_down(self, sc):
        return None

    def translate(self, vk, sc, shift, ctrl, alt, caps, hkl):
        pair = TABLE[hkl].get(sc)
        if not pair:
            return ""
        return pair[1] if (shift != caps and sc not in (SPACE, ENTER)) else pair[0]

    # ตัวช่วยในเทสต์: คืนค่าที่ core ตอบกลับ (suppress หรือไม่)
    def press(self, sc, down=True, injected=False):
        return self.on_raw(RawKey(0, sc, down, injected))


def make(**kw):
    be = FakeBackend(kw.pop("toggles", 0))
    k = Keyboard(backend=be, **kw)
    k.start()
    return be, k


def wait_for(cond, timeout=1.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


class LayoutTests(unittest.TestCase):
    def test_same_key_different_layout(self):
        be, k = make()
        be.press(A); be.press(A, False)
        be.layout = TH
        be.press(A); be.press(A, False)
        en_down, en_up, th_down, th_up = k.get()
        self.assertEqual((en_down.unicode, en_down.layout.lang, en_down.name), ("a", "en", "A"))
        self.assertEqual((th_down.unicode, th_down.layout.lang, th_down.name), ("ฟ", "th", "A"))
        self.assertEqual(en_down.scancode, th_down.scancode)
        self.assertEqual(en_down.key, ord("a"))
        self.assertEqual(th_down.key, ord("ฟ"))
        self.assertEqual(en_up.unicode, "")
        self.assertFalse(en_up.is_down)

    def test_shift_in_thai(self):
        be, k = make()
        be.layout = TH
        be.press(LSHIFT); be.press(A); be.press(A, False); be.press(LSHIFT, False)
        ev = [e for e in k.get() if e.scancode == A and e.is_down][0]
        self.assertEqual(ev.unicode, "ฤ")
        self.assertTrue(ev.mod & kb.MOD_SHIFT)

    def test_shortcut_has_no_unicode(self):
        be, k = make()
        be.press(LCTRL); be.press(A)
        ev = k.get()[-1]
        self.assertEqual(ev.unicode, "")
        self.assertTrue(ev.mod & kb.MOD_CTRL)

    def test_special_keys(self):
        be, k = make()
        be.press(LSHIFT)
        self.assertEqual(k.get()[0].key, kb.SPECIAL | LSHIFT)
        be.press(0x47)          # keypad 7 ต้องไม่ชนกับ '7'
        self.assertEqual(k.get()[0].key, kb.SPECIAL | 0x47)
        be.press(ENTER)
        self.assertEqual(k.get()[0].key, 13)

    def test_str_format(self):
        be, k = make()
        be.press(A)
        s = str(k.get()[0])
        self.assertIn("unicode: 'a'", s)
        self.assertIn("en-US", s)


class StateTests(unittest.TestCase):
    def test_is_pressed_and_groups(self):
        be, k = make()
        be.press(LCTRL); be.press(A)
        self.assertTrue(k.is_pressed("ctrl"))
        self.assertTrue(k.is_pressed("a"))
        self.assertTrue(k.is_pressed(scancode=A))
        self.assertTrue(k.is_pressed(vk=0x41))
        self.assertFalse(k.is_pressed("shift"))
        be.press(A, False); be.press(LCTRL, False)
        self.assertFalse(k.is_pressed("ctrl"))
        self.assertEqual(k.get_pressed(), frozenset())

    def test_is_pressed_argument_checks(self):
        be, k = make()
        with self.assertRaises(ValueError):
            k.is_pressed()
        with self.assertRaises(ValueError):
            k.is_pressed("a", scancode=1)
        with self.assertRaises(ValueError):
            k.is_pressed("no such key")

    def test_caps_toggle_and_initial_state(self):
        be, k = make(toggles=kb.MOD_NUMLOCK)
        self.assertTrue(k.get_mods() & kb.MOD_NUMLOCK)
        be.press(CAPS); be.press(CAPS, False)
        self.assertTrue(k.get_mods() & kb.MOD_CAPSLOCK)
        be.press(CAPS); be.press(CAPS, False)
        self.assertFalse(k.get_mods() & kb.MOD_CAPSLOCK)

    def test_repeat_dropped_by_default_and_optional(self):
        be, k = make()
        be.press(A); be.press(A); be.press(A); be.press(A, False)
        self.assertEqual(len(k.get()), 2)
        k.repeat = True
        be.press(A); be.press(A); be.press(A, False)
        self.assertEqual([e.repeat for e in k.get()], [False, True, False])

    def test_wait_timeout(self):
        be, k = make()
        self.assertIsNone(k.wait(0.05))


class LifecycleTests(unittest.TestCase):
    def test_refcount(self):
        be = FakeBackend()
        k = Keyboard(backend=be)
        k.acquire(); k.acquire()
        self.assertEqual(be.started, 1)
        k.release()
        self.assertTrue(k.running)
        k.release()
        self.assertFalse(k.running)
        self.assertEqual(be.stopped, 1)
        k.release()                      # เกินจำนวน ต้องไม่พัง
        self.assertEqual(be.stopped, 1)

    def test_start_stop_idempotent(self):
        be = FakeBackend()
        k = Keyboard(backend=be)
        k.start(); k.start()
        self.assertEqual(be.started, 1)
        k.stop(); k.stop()
        self.assertEqual(be.stopped, 1)

    def test_is_pressed_without_native_state_starts_tracking(self):
        be = FakeBackend()
        k = Keyboard(backend=be)
        self.assertFalse(k.is_pressed("a"))
        self.assertTrue(k.running)
        k.stop()                          # ref ของ is_pressed ยังถือ hook ไว้
        self.assertTrue(k.running)


class ListenerTests(unittest.TestCase):
    def test_listener_press_release_in_other_thread(self):
        import threading
        be, k = make()
        got = []
        main = threading.current_thread()
        l = kb.Listener(on_press=lambda e: got.append(("down", e.unicode, threading.current_thread())),
                        on_release=lambda e: got.append(("up", e.unicode, threading.current_thread())),
                        keyboard=k)
        l.start()
        be.press(A); be.press(A, False)
        self.assertTrue(wait_for(lambda: len(got) == 2))
        self.assertEqual([g[:2] for g in got], [("down", "a"), ("up", "")])
        self.assertTrue(all(g[2] is not main for g in got))
        l.stop()
        be.press(A)
        time.sleep(0.05)
        self.assertEqual(len(got), 2)       # stop แล้วไม่ถูกเรียกอีก

    def test_listener_repeat_flag(self):
        be, k = make()
        plain, rep = [], []
        l1 = kb.Listener(on_press=plain.append, keyboard=k); l1.start()
        l2 = kb.Listener(on_press=rep.append, repeat=True, keyboard=k); l2.start()
        be.press(A); be.press(A); be.press(A)
        self.assertTrue(wait_for(lambda: len(rep) == 3))
        time.sleep(0.05)
        self.assertEqual(len(plain), 1)
        l1.stop(); l2.stop()

    def test_slow_or_failing_callback_does_not_block_hook(self):
        be, k = make()
        done = []

        def slow(ev):
            time.sleep(0.3)
            raise RuntimeError("boom")

        l = kb.Listener(on_press=slow, keyboard=k); l.start()
        t0 = time.time()
        for _ in range(3):
            be.press(A, False); be.press(A)
        self.assertLess(time.time() - t0, 0.1)      # hook ไม่ต้องรอ callback
        l.stop()

    def test_listener_releases_hook(self):
        be = FakeBackend()
        k = Keyboard(backend=be)
        with kb.Listener(keyboard=k):
            self.assertTrue(k.running)
        self.assertFalse(k.running)


class SuppressTests(unittest.TestCase):
    def test_bool_suppress(self):
        be, k = make()
        self.assertFalse(be.press(A))
        l = kb.Listener(suppress=True, keyboard=k); l.start()
        self.assertTrue(be.press(A))
        self.assertTrue(be.press(A, False))
        l.stop()
        self.assertFalse(be.press(A))

    def test_callable_suppress(self):
        be, k = make()
        l = kb.Listener(suppress=lambda ev: ev.scancode == A, keyboard=k); l.start()
        self.assertTrue(be.press(A))
        self.assertFalse(be.press(SPACE))
        l.stop()

    def test_injected_never_suppressed(self):
        be, k = make()
        l = kb.Listener(suppress=True, keyboard=k); l.start()
        self.assertFalse(be.press(A, injected=True))
        l.stop()

    def test_failing_filter_does_not_suppress(self):
        be, k = make()
        l = kb.Listener(suppress=lambda ev: 1 / 0, keyboard=k); l.start()
        self.assertFalse(be.press(A))
        l.stop()


class ThreadSubclassSafetyTests(unittest.TestCase):
    """Listener สืบทอด threading.Thread — ชื่อเมธอด/attribute ของเราต้องไม่ชนกับของภายใน Thread
    (Python 3.13 มี Thread._handle เป็น _ThreadHandle ซึ่งเคยทับเมธอด _handle ของเรา)
    ใช้รายชื่อที่ Thread ใช้ในแต่ละเวอร์ชัน เพื่อให้เทสต์จับได้แม้รันบน Python รุ่นเก่ากว่า"""

    THREAD_PRIVATE = {
        "_handle", "_stop", "_started", "_target", "_name", "_args", "_kwargs", "_daemonic",
        "_ident", "_native_id", "_is_stopped", "_initialized", "_tstate_lock", "_context",
        "_os_thread_handle", "_invoke_excepthook", "_delete", "_bootstrap", "_bootstrap_inner",
        "_set_ident", "_set_native_id", "_set_tstate_lock", "_wait_for_tstate_lock", "_make_invoke_excepthook",
    }

    def test_no_collision_with_thread_internals(self):
        be, k = make()
        l = kb.Listener(keyboard=k)
        ours = set(Listener_own_names(kb.Listener)) | set(vars(l)) - set(vars(__import__("threading").Thread()))
        self.assertEqual(ours & self.THREAD_PRIVATE, set())

    def test_registered_callback_is_ours(self):
        be, k = make()
        l = kb.Listener(on_press=lambda e: None, keyboard=k)
        l.start()
        registered = [fn for fn, _s, _r in k._listeners]
        self.assertEqual(len(registered), 1)
        self.assertTrue(callable(registered[0]))
        self.assertTrue(hasattr(registered[0], "__func__"))     # bound method ของ Listener ไม่ใช่ attribute ของ Thread
        l.stop()


def Listener_own_names(cls):
    """ชื่อที่คลาสนี้ define เอง (ไม่รวมที่สืบทอด)"""
    return [n for n in vars(cls) if not (n.startswith("__") and n.endswith("__"))]


if __name__ == "__main__":
    unittest.main()
