from hexss import keyboard


def on_press(key):
    print(f'P {key}')


def on_release(key):
    print(f'R {key}')


with keyboard.Listener(on_press=on_press, on_release=on_release, suppress=True, repeat=True) as listener:
    listener.join()

# or
listener = keyboard.Listener(on_press=on_press, on_release=on_release, suppress=True, repeat=True)
listener.start()
listener.join()

# or
while True:
    ev = keyboard.wait()
    if ev.type == keyboard.KEYDOWN:
        print(ev.type, ev.name, ev.unicode, ev.layout.lang, ev.time)  # 768, 'A' 'ฟ' 'th'
