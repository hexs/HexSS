import platform

from .events import KEYDOWN, KEYUP, SPECIAL, KeyEvent, Layout
from .key_mappings import (
    MOD_NONE,
    MOD_LSHIFT,
    MOD_RSHIFT,
    MOD_SHIFT,
    MOD_LCTRL,
    MOD_RCTRL,
    MOD_CTRL,
    MOD_LALT,
    MOD_RALT,
    MOD_ALT,
    MOD_LWIN,
    MOD_RWIN,
    MOD_WIN,
    MOD_NUMLOCK,
    MOD_CAPSLOCK,
    MOD_SCROLLLOCK,
)
from ._core import Keyboard, get_keyboard, peek_keyboard
from ._listener import Listener

_system = platform.system()
if _system == 'Windows':
    from ._winkeyboard import keyboard as _out

    def set_xkb(*args, **kwargs):
        """Linux only (no-op on Windows: the keyboard layout comes from the OS)."""

    def set_xkb_group(index):
        """Linux only (no-op on Windows)."""
elif _system == 'Linux':
    from ._nixkeyboard import keyboard as _out, set_xkb, set_xkb_group
else:
    raise NotImplementedError(f"Currently, {_system} is not supported.")


# ---- Sending keys ----
press = _out.press
release = _out.release
send = _out.send
write = _out.write


# ---- Receiving keys ----
def start(repeat: bool = False) -> None:
    """Start keyboard hooking (idempotent). If repeat=True, get()/wait() queues also receive key-repeat events."""
    kb = get_keyboard()
    kb.repeat = repeat
    kb.start()


def stop() -> None:
    kb = peek_keyboard()
    if kb is not None:
        kb.stop()


def _kbd() -> Keyboard:
    kb = get_keyboard()
    kb.start()
    return kb


def get() -> list:
    """Return all pending events (non-blocking)."""
    return _kbd().get()


def wait(timeout=None):
    """Wait for the next event; returns None on timeout."""
    return _kbd().wait(timeout)


def clear() -> None:
    _kbd().clear()


def add_listener(fn, suppress=False, repeat=False) -> None:
    """Register a callback fn(event) invoked in a separate thread (Listener uses the same mechanism)."""
    kb = _kbd()
    kb.add_listener(fn, suppress=suppress, repeat=repeat)


def remove_listener(fn) -> None:
    kb = peek_keyboard()
    if kb is not None:
        kb.remove_listener(fn)


def get_layout() -> Layout:
    """Return the keyboard layout of the currently active window (e.g., .lang == 'th')."""
    return get_keyboard().get_layout()


def get_mods() -> int:
    return _kbd().get_mods()


def get_pressed() -> frozenset:
    """Return scancodes of currently pressed keys."""
    return _kbd().get_pressed()


def is_pressed(key=None, scancode=None, vk=None) -> bool:
    """Specify one of: key (name/scancode), scancode, or vk. 'shift'/'ctrl'/'alt'/'win' match either left or right."""
    return get_keyboard().is_pressed(key, scancode, vk)


__all__ = [
    'press', 'release', 'send', 'write', 'is_pressed',
    'start', 'stop', 'get', 'wait', 'clear', 'add_listener', 'remove_listener',
    'get_layout', 'get_mods', 'get_pressed',
    'set_xkb', 'set_xkb_group',
    'KeyEvent', 'Layout', 'Listener', 'Keyboard',
    'KEYDOWN', 'KEYUP', 'SPECIAL',
    'MOD_NONE', 'MOD_LSHIFT', 'MOD_RSHIFT', 'MOD_SHIFT', 'MOD_LCTRL', 'MOD_RCTRL', 'MOD_CTRL',
    'MOD_LALT', 'MOD_RALT', 'MOD_ALT', 'MOD_LWIN', 'MOD_RWIN', 'MOD_WIN',
    'MOD_NUMLOCK', 'MOD_CAPSLOCK', 'MOD_SCROLLLOCK',
]
