import random
import numpy as np
from hexss.threading import Multithread
import time
from flask import Flask
import tkinter as tk

# web server
app = Flask(__name__)


@app.route('/')
def index():
    data = app.config['data']
    return f'{data["text label"]}'


def run_server(data):
    app.config['data'] = data
    app.run(debug=False, use_reloader=False)


# normal loop
def capture(data):
    while data['play']:
        random_color = [random.randint(150, 255) for _ in range(3)]
        data['text label'] = f'{random_color}'
        data['img'] = np.full((500, 500, 3), random_color, dtype=np.uint8)
        time.sleep(0.5)


# tk
def ui(data):
    root = tk.Tk()
    root.geometry("300x100")
    root.title("Text Label Updater")

    var = tk.StringVar()
    label = tk.Label(root, textvariable=var, relief=tk.RAISED, font=("Arial", 14))
    var.set(data['text label'])
    label.pack(pady=20)

    def update_label():
        if data['play']:
            var.set(data['text label'])
            root.after(500, update_label)
        else:
            root.quit()

    def on_closing():
        data['play'] = False
        root.quit()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    update_label()
    root.mainloop()


def main():
    m = Multithread()
    data = {
        'play': True,
        'text label': '123',
    }

    m.add_func(capture, args=(data,))
    m.add_func(run_server, args=(data,), join=False)
    m.add_func(ui, args=(data,), name='ui')

    m.start()
    m.join()


if __name__ == '__main__':
    main()
