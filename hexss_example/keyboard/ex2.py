from hexss.keyboard import Listener


def on_press(key):
    print(f'P {key}')


def on_release(key):
    print(f'R {key}')


listener = Listener(on_press=on_press, on_release=on_release, suppress=True)
listener.start()
listener.join()

