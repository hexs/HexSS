import time
from datetime import datetime
from hexss import check_packages

check_packages(
    'gpiozero', 'lgpio', 'pigpio',
    auto_install=True
)

from gpiozero import DigitalOutputDevice, DigitalInputDevice

OFF = 0
ON = 1
RISING = 2
FALLING = 3


class SimultaneousEvents:
    def __init__(self, pins, max_interval=0.1):
        """
        pins: list/tuple of:
            - DigitalInputDevice instance (default RISING)
            - or (DigitalInputDevice, edge) tuple, where edge is SimultaneousEvents.RISING or .FALLING
        max_interval : max seconds between presses to be considered "simultaneous"
        """
        if not isinstance(pins, (list, tuple)) or len(pins) != 2:
            raise ValueError("pins must be a list or tuple of 2 elements")
        self.max_interval = max_interval
        self.when_activated = None
        self.when_deactivated = None
        self.last_times = [None, None]
        self.states = [False, False]
        self._active_flag = False

        # Parse pins and edges
        self._edges = []
        self.buttons = []
        for item in pins:
            if isinstance(item, DigitalInputDevice):
                self.buttons.append(item)
                self._edges.append(RISING)
            elif (isinstance(item, tuple)
                  and len(item) == 2
                  and isinstance(item[0], DigitalInputDevice)
                  and item[1] in (RISING, FALLING)):
                pin, edge = item
                self.buttons.append(pin)
                self._edges.append(edge)
            else:
                raise ValueError("Each pin must be a DigitalInputDevice, or (DigitalInputDevice, edge) tuple.")

        # Set up edge detection with correct closure binding
        def make_activated(idx):
            return lambda: self._on_rising(idx) if self._edges[idx] == RISING else self._on_falling(idx)

        def make_deactivated(idx):
            return lambda: self._on_falling(idx) if self._edges[idx] == RISING else self._on_rising(idx)

        for idx, btn in enumerate(self.buttons):
            btn.when_activated = make_activated(idx)
            btn.when_deactivated = make_deactivated(idx)

    def _on_rising(self, idx):
        now = time.time()
        self.last_times[idx] = now
        self.states[idx] = True
        other_idx = 1 - idx
        if self.states[other_idx]:
            if self.last_times[other_idx] is not None and abs(now - self.last_times[other_idx]) <= self.max_interval:
                if not self._active_flag:
                    self._active_flag = True
                    if self.when_activated:
                        self.when_activated()
        else:
            if self._active_flag:
                self._active_flag = False
                if self.when_deactivated:
                    self.when_deactivated()

    def _on_falling(self, idx):
        self.states[idx] = False
        if self._active_flag:
            self._active_flag = False
            if self.when_deactivated:
                self.when_deactivated()

    def status(self):
        return tuple(self.states)


if __name__ == '__main__':
    def simultaneous_button_events():
        global start
        button_led.blink(0.2, 0.4)
        print('led blink')
        if alarm.value == 1:
            print('reset alarm')
            reset_alarm.on()
            time.sleep(0.05)
            reset_alarm.off()
        start = True


    def alarm_event():
        print('alarm_event')
        button_led.blink(0.05, 0.10)


    start = False
    O1, O2, O3, O4, BUTTON_LED, O6, RESET_ALARM, O8 = 4, 17, 18, 27, 22, 23, 24, 25
    I1, I2, ALARM, I4, R_BUTTON, L_BUTTON, AREA2, AREA1 = 5, 6, 12, 13, 16, 19, 20, 21

    alarm = DigitalInputDevice(ALARM, bounce_time=0.1)
    reset_alarm = DigitalOutputDevice(RESET_ALARM)
    button_led = DigitalOutputDevice(BUTTON_LED)
    r_button = DigitalInputDevice(R_BUTTON, bounce_time=0.1)
    l_button = DigitalInputDevice(L_BUTTON, bounce_time=0.1)
    area2 = DigitalInputDevice(AREA2, bounce_time=0.1)
    area1 = DigitalInputDevice(AREA1, bounce_time=0.1)
    simultaneous_events = SimultaneousEvents((r_button, l_button), max_interval=0.1)

    alarm.when_activated = alarm_event
    simultaneous_events.when_activated = simultaneous_button_events

    while True:
        print(datetime.now(), simultaneous_events.status())
        if start:
            print('start', area1.value, area2.value)
            if area1.value or area2.value:
                start = False
        else:
            if area1.value or area2.value:
                button_led.off()
            else:
                button_led.on()

        time.sleep(0.1)
