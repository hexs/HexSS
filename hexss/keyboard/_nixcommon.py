# -*- coding: utf-8 -*-
import struct
import os
import atexit
from time import time as now
from threading import Thread
import re
from collections import namedtuple
from glob import glob
from queue import Queue

event_bin_format = 'llHHI'
event_size = struct.calcsize(event_bin_format)

# Taken from include/linux/input.h
# https://www.kernel.org/doc/Documentation/input/event-codes.txt
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
EV_MSC = 0x04

VIRTUAL_KEYBOARD_NAME = "Virtual Keyboard"

HANDLER_ALIASES = {
    'keyboard': 'kbd',
    'mouse': 'mouse',
}


def make_uinput():
    import fcntl

    uinput = open("/dev/uinput", 'wb')
    UI_SET_EVBIT = 0x40045564
    fcntl.ioctl(uinput, UI_SET_EVBIT, EV_KEY)

    UI_SET_KEYBIT = 0x40045565
    for i in range(256):
        fcntl.ioctl(uinput, UI_SET_KEYBIT, i)

    BUS_USB = 0x03
    uinput_user_dev = "80sHHHHi64i64i64i64i"
    axis = [0] * 64 * 4
    uinput.write(struct.pack(uinput_user_dev, VIRTUAL_KEYBOARD_NAME.encode(), BUS_USB, 1, 1, 1, 0, *axis))
    uinput.flush()

    UI_DEV_CREATE = 0x5501
    UI_DEV_DESTROY = 0x5502
    fcntl.ioctl(uinput, UI_DEV_CREATE)

    def _cleanup():
        try:
            fcntl.ioctl(uinput, UI_DEV_DESTROY)
        except Exception:
            pass
        try:
            uinput.close()
        except Exception:
            pass

    atexit.register(_cleanup)
    return uinput


class EventDevice:
    def __init__(self, path, name=None):
        self.path = path
        self.name = name
        self._input_file = None
        self._output_file = None

    @property
    def input_file(self):
        if self._input_file is None:
            try:
                self._input_file = open(self.path, 'rb')
            except PermissionError as e:
                raise PermissionError(
                    f"Permission denied ({self.path}). You must run as root to access global events."
                ) from e

            def try_close():
                try:
                    self._input_file.close()
                except Exception:
                    pass

            atexit.register(try_close)
        return self._input_file

    @property
    def output_file(self):
        if self._output_file is None:
            self._output_file = open(self.path, 'wb')

            def try_close():
                try:
                    self._output_file.close()
                except Exception:
                    pass

            atexit.register(try_close)
        return self._output_file

    def read_event(self, timeout=None):
        data = self.input_file.read(event_size)
        if len(data) < event_size:
            raise EOFError(f"Device closed or disconnected: {self.path}")
        seconds, microseconds, type_val, code, value = struct.unpack(event_bin_format, data)
        return seconds + microseconds / 1e6, type_val, code, value, self.path

    def write_event(self, type_val, code, value):
        integer, fraction = divmod(now(), 1)
        seconds = int(integer)
        microseconds = int(fraction * 1e6)
        data_event = struct.pack(event_bin_format, seconds, microseconds, type_val, code, value)
        sync_event = struct.pack(event_bin_format, seconds, microseconds, EV_SYN, 0, 0)

        self.output_file.write(data_event + sync_event)
        self.output_file.flush()


class AggregatedEventDevice:
    def __init__(self, devices, output=None):
        self.event_queue = Queue()
        self.devices = devices
        self.output = output or (self.devices[0] if self.devices else None)

        def start_reading(device):
            while True:
                try:
                    self.event_queue.put(device.read_event())
                except (OSError, EOFError, struct.error):
                    break

        for device in self.devices:
            thread = Thread(target=start_reading, args=(device,), daemon=True)
            thread.start()

    def read_event(self, timeout=None):
        return self.event_queue.get(block=True, timeout=timeout)

    def write_event(self, type_val, code, value):
        if self.output is None:
            raise RuntimeError("No output device available.")
        self.output.write_event(type_val, code, value)


DeviceDescription = namedtuple('DeviceDescription', 'event_file is_mouse is_keyboard')
device_pattern = r"""N: Name="([^"]+?)".+?H: Handlers=([^\n]+)"""


def list_devices_from_proc(type_name):
    try:
        with open('/proc/bus/input/devices', 'r', encoding='utf-8', errors='ignore') as f:
            description = f.read()
    except FileNotFoundError:
        return

    handler_token = HANDLER_ALIASES.get(type_name, type_name)
    for name, handlers in re.findall(device_pattern, description, re.DOTALL):
        match = re.search(r'event(\d+)', handlers)
        if not match:
            continue
        tokens = handlers.split()
        if handler_token in tokens or type_name in tokens:
            yield EventDevice('/dev/input/event' + match.group(1), name=name)


def list_devices_from_by_id(type_name):
    for path in glob('/dev/input/by-id/*-event-' + type_name):
        yield EventDevice(path)


def aggregate_devices(type_name, create_uinput=True):
    fake_device = None
    if create_uinput:
        uinput = make_uinput()
        fake_device = EventDevice('uinput Fake Device')
        fake_device._input_file = uinput
        fake_device._output_file = uinput

    devices_from_proc = list(list_devices_from_proc(type_name))
    if devices_from_proc:
        return AggregatedEventDevice(devices_from_proc, output=fake_device)

    devices_from_by_id = list(list_devices_from_by_id(type_name))
    if devices_from_by_id:
        return AggregatedEventDevice(devices_from_by_id, output=fake_device)

    return fake_device


def ensure_root():
    if os.geteuid() != 0:
        raise PermissionError('You must be root to use this library on Linux.')