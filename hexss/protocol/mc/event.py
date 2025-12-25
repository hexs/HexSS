from typing import Union, List, Optional


class Event:
    def __init__(self, address: str, name: str, value: float):
        self.address = address
        self.name = name
        self.value = value

    def __getitem__(self, key):
        if key == 'address':
            return self.address
        elif key == 'name':
            return self.name
        elif key == 'value':
            return self.value
        raise KeyError(f"Key '{key}' not found")

    def __dict__(self):
        return {'address': self.address, 'name': self.name, 'value': self.value}

    def __repr__(self):
        if self.address == self.name:
            return f"<{self.address}: {self.value}>"
        return f"<{self.address}({self.name}): {self.value}>"


class Events:
    def __init__(self, events: Optional[List[Event]] = None):
        self.events = events or []

    def add_event(self, event: Event):
        self.events.append(event)

    @property
    def last(self) -> Optional[Event]:
        return self.events[-1] if self.events else None

    def matches(self, names: List[str], value: Union[int, float, List[Union[int, float]]] = 1) -> bool:
        if not isinstance(value, list):
            values = [value] * len(names)
        else:
            values = value

        if len(names) != len(values) or not self.events:
            return False

        is_trigger_valid = any(
            self.last.name == n and self.last.value == v
            for n, v in zip(names, values)
        )

        if not is_trigger_valid:
            return False

        current_state = {(e.name, e.value) for e in self.events}
        required_state = set(zip(names, values))

        return required_state.issubset(current_state)

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        return iter(self.events)

    def __getitem__(self, index):
        return self.events[index]

    def __repr__(self):
        return f"Events({self.events})"


class Match:
    def __init__(self, name: str):
        self._name = name
        self._value = None
        self._check_value = False

    def value(self, v):
        self._value = v
        self._check_value = True
        return self

    def __eq__(self, other):
        if not isinstance(other, Event): return NotImplemented
        name_match = (self._name == other.name)
        if not self._check_value: return name_match
        return name_match and (self._value == other.value)


if __name__ == "__main__":
    e1 = Event("X1", "Left Button", 1)
    e2 = Event("X2", "Right Button", 1)
    e3 = Event("X0", "Emergency Stop", 0)

    events = Events([e1, e2, e3])

    if Match("Left Button").value(1) in events:
        print("✅ Left Button is ON")

    if Match("Left Button").value(1) in events and Match("Right Button").value(1) in events:
        print("✅ Both buttons are ON")

    if Match("Left Button").value(1) in events or Match("Right Button").value(1) in events:
        print("✅ At least one button is ON")

    if Match("Emergency Stop") in events:
        print("✅ Emergency Stop event exists (regardless of value)")
