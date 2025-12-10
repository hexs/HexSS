from __future__ import annotations
from typing import List, Optional, Callable, Dict, Tuple, Any, Union
import time
import threading
import gpiozero


class DigitalInputDevice(gpiozero.DigitalInputDevice):
    def __init__(
            self,
            pin: int,
            name: Optional[str] = None,
            *,
            pull_up: bool = False,
            active_state: Optional[bool] = None,
            bounce_time: Optional[float] = None,
            pin_factory=None,
    ):
        super().__init__(
            pin,
            pull_up=pull_up,
            active_state=active_state,
            bounce_time=bounce_time,
            pin_factory=pin_factory,
        )
        self.name = name or f'Pin{pin}'

    def __str__(self) -> str:
        return f"{self.name}:{int(self.value)}"


class DigitalOutputDevice(gpiozero.DigitalOutputDevice):
    def __init__(self, pin=None, name=None, *, active_high=True, initial_value=False, pin_factory=None):
        super().__init__(pin, active_high=active_high, initial_value=initial_value, pin_factory=pin_factory)
        self.name = name or f'Pin{pin}'
        self._state_change_callback = None

    def set_change_callback(self, callback: Callable[[Any, int], None]):
        self._state_change_callback = callback

    def _fire_callback(self):
        if self._state_change_callback:
            self._state_change_callback(self, int(self.value))

    def on(self):
        super().on()
        self._fire_callback()

    def off(self):
        super().off()
        self._fire_callback()

    def toggle(self):
        super().toggle()
        self._fire_callback()

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, value):
        super(DigitalOutputDevice, type(self)).value.fset(self, value)
        self._fire_callback()

    def __str__(self) -> str:
        return f"{self.name}:{int(self.value)}"


class Inputs:
    def __init__(self, gpio_manager: 'IOController'):
        self.inputs: List[DigitalInputDevice] = []
        self._gpio = gpio_manager

    def add(
            self,
            pin: int,
            name: str,
            *,
            pull_up: bool = False,
            active_state: Optional[bool] = None,
            bounce_time: Optional[float] = None,
            pin_factory=None
    ) -> DigitalInputDevice:
        device = DigitalInputDevice(
            pin=pin,
            name=name,
            pull_up=pull_up,
            active_state=active_state,
            bounce_time=bounce_time,
            pin_factory=pin_factory,
        )
        self.inputs.append(device)
        self._gpio._attach_device_handler(device)
        return device

    def get(self, key: Union[int, str]) -> DigitalInputDevice:
        for device in self.inputs:
            if isinstance(key, int) and device.pin.number == key:
                return device
            elif isinstance(key, str) and device.name == key:
                return device
        raise ValueError(f"Input Device not found: {key}")

    def close(self):
        for device in self.inputs:
            device.close()


class Outputs:
    def __init__(self, gpio_manager: 'IOController'):
        self.outputs: List[DigitalOutputDevice] = []
        self._gpio = gpio_manager

    def add(self, device: DigitalOutputDevice) -> DigitalOutputDevice:
        self.outputs.append(device)
        self._gpio._attach_device_handler(device)
        return device

    def get(self, key: Union[int, str]) -> DigitalOutputDevice:
        for device in self.outputs:
            if isinstance(key, int) and device.pin.number == key:
                return device
            elif isinstance(key, str) and device.name == key:
                return device
        raise ValueError(f"Output Device not found: {key}")

    def close(self):
        for device in self.outputs:
            device.close()


class IOController:
    def __init__(self):
        self.input = Inputs(self)
        self.output = Outputs(self)

        self._edge_callbacks: List[Callable[[Any, int], None]] = []
        self._simul_groups: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def get(self, key: Union[int, str]) -> Union[DigitalInputDevice, DigitalOutputDevice]:
        try:
            return self.input.get(key)
        except ValueError:
            pass
        try:
            return self.output.get(key)
        except ValueError:
            pass
        raise ValueError(f"Device '{key}' not found in Inputs or Outputs.")

    def _attach_device_handler(self, device: Union[DigitalInputDevice, DigitalOutputDevice]):
        if isinstance(device, DigitalInputDevice):
            device.when_activated = lambda d=device: self._handle_event(d, 1)
            device.when_deactivated = lambda d=device: self._handle_event(d, 0)
        elif isinstance(device, DigitalOutputDevice):
            device.set_change_callback(self._handle_event)

    def on_change(self, callback: Callable[[Any, int], None]) -> None:
        self._edge_callbacks.append(callback)

    def simultaneous_events(
            self,
            callback: Callable[[List[Tuple[str, int]]], None],
            duration: float
    ) -> None:
        if duration <= 0:
            raise ValueError("duration must be > 0")

        with self._lock:
            group = {
                "duration": duration,
                "callback": callback,
                "events": [],
                "window_start": None,
                "window_id": 0,
            }
            self._simul_groups.append(group)

    def _handle_event(self, device: Union[DigitalInputDevice, DigitalOutputDevice], value: int):
        for cb in self._edge_callbacks:
            cb(device, value)
        self._handle_simultaneous_logic(device, value)

    def _handle_simultaneous_logic(self, device, value):
        now = time.monotonic()
        with self._lock:
            if not self._simul_groups:
                return

            for group in self._simul_groups:
                duration: float = group["duration"]
                window_start: Optional[float] = group["window_start"]
                if window_start is None or (now - window_start) > duration:
                    group["window_start"] = now
                    group["events"] = []
                    group["window_id"] += 1
                    window_id = group["window_id"]
                    timer = threading.Timer(
                        duration,
                        self._flush_simultaneous_events_group,
                        args=(group, window_id),
                    )
                    timer.daemon = True
                    timer.start()

                group["events"].append((device.name, value))

    def _flush_simultaneous_events_group(self, group: Dict[str, Any], window_id: int):
        with self._lock:
            if window_id != group["window_id"]:
                return

            events: List[Tuple[str, int]] = group["events"]
            if not events:
                group["window_start"] = None
                return

            events_to_send = list(events)
            group["events"] = []
            group["window_start"] = None
            cb = group["callback"]

        if cb:
            cb(events_to_send)

    def close(self):
        self.input.close()
        self.output.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start_server(self, host="0.0.0.0", port=2003):
        import hexss.protocol.raspberrypi.server

        print(f"Starting server at http://{host}:{port}")
        threading.Thread(
            target=hexss.protocol.raspberrypi.server.run,
            args=(
                {
                    "host": host,
                    "port": port,
                    'io': self
                },
            ),
            daemon=True
        ).start()


if __name__ == "__main__":
    def universal_callback(device, value):
        type_name = "INPUT " if isinstance(device, DigitalInputDevice) else "OUTPUT"
        print(f"[LOG] {type_name}: {device.name} -> {value}")


    def handle_simultaneous(events: List[Tuple[str, int]]):
        print(f"[SIMUL EVENT] Captured: {events}")
        if ('Switch L', 1) in events and ('Switch R', 1) in events:
            print(">>> BOTH SWITCHES PRESSED! Triggering sequence...")
            io.get('Cylinder 1+').on()
            time.sleep(1)
            io.get('Cylinder 1+').off()
            time.sleep(1)
            io.get('Cylinder 1-').on()
            time.sleep(1)
            io.get('Cylinder 1-').off()

        if ('Cylinder 1+', 1) in events:
            io.get('Switch Lamp').on()

        if ('Cylinder 1+', 0) in events:
            io.get('Switch Lamp').off()


    io = IOController()

    io.input.add(5, "EM", bounce_time=0.02)
    io.input.add(12, "Switch L", pull_up=True, bounce_time=0.02)
    io.input.add(16, "Switch R", pull_up=True, bounce_time=0.02)
    io.input.add(20, "Area 1", bounce_time=0.02)
    io.input.add(6, "Proximity1", pull_up=True, bounce_time=0.02)
    io.input.add(13, "Proximity2", pull_up=True, bounce_time=0.02)
    io.input.add(19, "Cylinder 1 Reed Switch", pull_up=True, bounce_time=0.02)
    io.input.add(21, "Cylinder 2 Reed Switch", pull_up=True, bounce_time=0.02)

    io.output.add(DigitalOutputDevice(4, 'Switch Lamp'))
    io.output.add(DigitalOutputDevice(18, 'Buzzer'))
    io.output.add(DigitalOutputDevice(22, 'Cylinder 1+'))
    io.output.add(DigitalOutputDevice(24, 'Cylinder 1-'))
    io.output.add(DigitalOutputDevice(17, 'Cylinder 2+'))
    io.output.add(DigitalOutputDevice(27, 'Cylinder 2-'))
    io.output.add(DigitalOutputDevice(23))
    io.output.add(DigitalOutputDevice(25))

    io.on_change(universal_callback)
    io.simultaneous_events(handle_simultaneous, duration=0.2)
    io.start_server()

    print("System Running... Press Ctrl+C to exit.")
    try:
        while True:
            # if io.get("Area 1").value:
            #     if not io.get("Buzzer").value:
            #         io.get("Buzzer").on()
            #         print("[LOOP] Area Breach! Buzzer ON")
            # else:
            #     if io.get("Buzzer").value:
            #         io.get("Buzzer").off()
            #         print("[LOOP] Area Clear. Buzzer OFF")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nExiting...")
        io.close()
