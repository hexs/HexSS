import platform

if platform.system() == 'Windows':
    from ._winkeyboard import keyboard as _win_kb
    from ._winkeyboard import Listener
else:
    raise NotImplementedError("Currently, only Windows is supported.")


press = _win_kb.press
release = _win_kb.release
send = _win_kb.send
write = _win_kb.write