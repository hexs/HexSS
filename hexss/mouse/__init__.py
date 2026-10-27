import math
import random
import time as _time
import platform

if platform.system() == 'Windows':
    from hexss.mouse import _winmouse as _os_mouse
elif platform.system() == 'Linux':
    from hexss.mouse import _nixmouse as _os_mouse
else:
    raise OSError("Unsupported platform '{}'".format(platform.system()))

from hexss.mouse._mouse_event import ButtonEvent, MoveEvent, WheelEvent, LEFT, RIGHT, MIDDLE, X, X2, UP, DOWN, DOUBLE
from hexss.mouse._generic import GenericListener as _GenericListener

_pressed_events = set()


class _MouseListener(_GenericListener):
    def init(self):
        _os_mouse.init()

    def pre_process_event(self, event):
        if isinstance(event, ButtonEvent):
            if event.event_type in (UP, DOUBLE):
                _pressed_events.discard(event.button)
            else:
                _pressed_events.add(event.button)
        return True

    def listen(self):
        _os_mouse.listen(self.queue)


_listener = _MouseListener()


def is_pressed(button=LEFT):
    """ Returns True if the given button is currently pressed. """
    _listener.start_if_necessary()
    return button in _pressed_events


def press(button=LEFT):
    """ Presses the given button (but doesn't release). """
    _os_mouse.press(button)


def release(button=LEFT):
    """ Releases the given button. """
    _os_mouse.release(button)


def click(button=LEFT):
    """ Sends a click with the given button. """
    _os_mouse.press(button)
    _os_mouse.release(button)


def double_click(button=LEFT):
    """ Sends a double click with the given button. """
    click(button)
    click(button)


def right_click():
    """ Sends a right click with the given button. """
    click(RIGHT)


def wheel(delta=1):
    """ Scrolls the wheel `delta` clicks. Sign indicates direction. """
    _os_mouse.wheel(delta)


def _cubic_bezier(t, p0, p1, p2, p3):
    """Calculates the coordinates of a cubic Bezier curve."""
    u = 1 - t
    x = u ** 3 * p0[0] + 3 * u ** 2 * t * p1[0] + 3 * u * t ** 2 * p2[0] + t ** 3 * p3[0]
    y = u ** 3 * p0[1] + 3 * u ** 2 * t * p1[1] + 3 * u * t ** 2 * p2[1] + t ** 3 * p3[1]
    return x, y


def _linear_move(start, end, duration):
    """ ลากเมาส์เป็นเส้นตรง (Linear Interpolation) """
    start_x, start_y = start
    end_x, end_y = end

    if duration <= 0:
        _os_mouse.move_to(end_x, end_y)
        return

    dx = end_x - start_x
    dy = end_y - start_y

    if dx == 0 and dy == 0:
        _time.sleep(duration)
        return

    steps = max(1, int(duration * 120.0))
    step_duration = duration / steps

    for i in range(1, steps + 1):
        curr_x = start_x + dx * i / steps
        curr_y = start_y + dy * i / steps
        _os_mouse.move_to(curr_x, curr_y)
        _time.sleep(step_duration)


def _humanized_move(start, end, dist, duration):
    """ ลากเมาส์แบบมนุษย์ (มีเส้นโค้ง, ชะลอ, มือสั่น, ลากเลยเป้า) """
    end_x, end_y = end

    if dist < 5:
        _os_mouse.move_to(end_x, end_y)
        _time.sleep(0.05)
        return

    if duration <= 0:
        duration = max(0.15, dist / 1500.0)

    bend = min(max(dist * 0.15, 20), 120)
    c1 = (start[0] + (end_x - start[0]) * 0.3 + random.uniform(-bend, bend),
          start[1] + (end_y - start[1]) * 0.3 + random.uniform(-bend, bend))
    c2 = (start[0] + (end_x - start[0]) * 0.6 + random.uniform(-bend, bend),
          start[1] + (end_y - start[1]) * 0.6 + random.uniform(-bend, bend))

    overshoot = dist > 200 and random.random() < 0.5
    target = (end_x + random.uniform(-15, 15), end_y + random.uniform(-15, 15)) if overshoot else end

    steps = int(min(max(dist / 4.0, 25), 120))
    step_duration = duration / steps

    # เคลื่อนที่ไปหาเป้าหมาย
    for i in range(1, steps + 1):
        t = i / steps
        eased = t * t * (3 - 2 * t)
        px, py = _cubic_bezier(eased, start, c1, c2, target)

        final_px = px + random.uniform(-0.8, 0.8)
        final_py = py + random.uniform(-0.8, 0.8)

        _os_mouse.move_to(final_px, final_py)
        _time.sleep(step_duration * random.uniform(0.6, 1.4))

    if overshoot:
        for i in range(1, 6):
            t = i / 5.0
            px = target[0] + (end_x - target[0]) * t + random.uniform(-0.5, 0.5)
            py = target[1] + (end_y - target[1]) * t + random.uniform(-0.5, 0.5)
            _os_mouse.move_to(px, py)
            _time.sleep(random.uniform(0.01, 0.03))

    _os_mouse.move_to(end_x, end_y)
    _time.sleep(random.uniform(0.03, 0.12))


def move(x, y, absolute=True, duration=0.0, speed=0.0, humanize=False):
    """
    Moves the mouse to the given (x, y) coordinates.
    Provides options for constant speed or human-like movement (humanize=True).
    """
    start = get_position()
    end_x = x if absolute else start[0] + x
    end_y = y if absolute else start[1] + y

    end = (end_x, end_y)
    dist = math.hypot(end[0] - start[0], end[1] - start[1])

    # If speed is defined, use it to calculate duration
    if speed > 0:
        duration = dist / speed

    if humanize:
        _humanized_move(start, end, dist, duration)
    else:
        _linear_move(start, end, duration)


def drag(start_x, start_y, end_x, end_y, absolute=True, duration=0.0, speed=0.0, humanize=False):
    """
    Holds the left mouse button, moving from start to end position, then releases.
    Now supports `speed` and `humanize` for human-like dragging.
    """
    if is_pressed():
        release()

    move(start_x, start_y, absolute=absolute, duration=0)
    press()
    move(end_x, end_y, absolute=absolute, duration=duration, speed=speed, humanize=humanize)
    release()


def on_button(callback, args=(), buttons=(LEFT, MIDDLE, RIGHT, X, X2), types=(UP, DOWN, DOUBLE)):
    """ Invokes `callback` with `args` when the specified event happens. """
    if not isinstance(buttons, (tuple, list)):
        buttons = (buttons,)
    if not isinstance(types, (tuple, list)):
        types = (types,)

    def handler(event):
        if isinstance(event, ButtonEvent):
            if event.event_type in types and event.button in buttons:
                callback(*args)

    _listener.add_handler(handler)
    return handler


def on_click(callback, args=()):
    """ Invokes `callback` with `args` when the left button is clicked. """
    return on_button(callback, args, [LEFT], [UP])


def on_double_click(callback, args=()):
    """ Invokes `callback` with `args` when the left button is double clicked. """
    return on_button(callback, args, [LEFT], [DOUBLE])


def on_right_click(callback, args=()):
    """ Invokes `callback` with `args` when the right button is clicked. """
    return on_button(callback, args, [RIGHT], [UP])


def on_middle_click(callback, args=()):
    """ Invokes `callback` with `args` when the middle button is clicked. """
    return on_button(callback, args, [MIDDLE], [UP])


def wait(button=LEFT, target_types=(UP, DOWN, DOUBLE)):
    """ Blocks program execution until the given button performs an event. """
    from threading import Lock
    lock = Lock()
    lock.acquire()
    handler = on_button(lock.release, (), [button], target_types)
    lock.acquire()
    _listener.remove_handler(handler)


def get_position():
    """ Returns the (x, y) mouse position. """
    return _os_mouse.get_position()


def hook(callback):
    """
    Installs a global listener on all available mouses, invoking `callback`
    each time it is moved, a key status changes or the wheel is spun.
    """
    _listener.add_handler(callback)
    return callback


def unhook(callback):
    """ Removes a previously installed hook. """
    _listener.remove_handler(callback)


def unhook_all():
    """ Removes all hooks registered by this application. """
    del _listener.handlers[:]


def record(button=RIGHT, target_types=(DOWN,)):
    """
    Records all mouse events until the user presses the given button.
    Then returns the list of events recorded. Pairs well with `play(events)`.
    """
    recorded = []
    hook(recorded.append)
    wait(button=button, target_types=target_types)
    unhook(recorded.append)
    return recorded


def play(events, speed_factor=1.0, include_clicks=True, include_moves=True, include_wheel=True):
    """ Plays a sequence of recorded events, maintaining the relative time intervals. """
    last_time = None
    for event in events:
        if speed_factor > 0 and last_time is not None:
            _time.sleep((event.time - last_time) / speed_factor)
        last_time = event.time

        if isinstance(event, ButtonEvent) and include_clicks:
            if event.event_type == UP:
                _os_mouse.release(event.button)
            else:
                _os_mouse.press(event.button)
        elif isinstance(event, MoveEvent) and include_moves:
            _os_mouse.move_to(event.x, event.y)
        elif isinstance(event, WheelEvent) and include_wheel:
            _os_mouse.wheel(event.delta)


replay = play
hold = press

if __name__ == '__main__':
    print('Recording... Double click to stop and replay.')
    play(record())
