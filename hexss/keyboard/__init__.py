import platform

if platform.system() == 'Windows':
    from ._winkeyboard import keyboard as _kb
    from ._winkeyboard import Listener
elif platform.system() == 'Linux':
    from ._nixkeyboard import keyboard as _kb
    from ._nixkeyboard import Listener
else:
    raise NotImplementedError(f"Currently, {platform.system()} is not supported.")


press = _kb.press
release = _kb.release
send = _kb.send
write = _kb.write
is_pressed = _kb.is_pressed