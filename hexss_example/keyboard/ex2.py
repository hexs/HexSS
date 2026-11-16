from hexss import keyboard


def on_press(key):
    print(f'P {key}')


def on_release(key):
    print(f'R {key}')


with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

# or
# listener = keyboard.Listener(on_press=on_press, on_release=on_release, suppress=True)
# listener.start()
# listener.join()
