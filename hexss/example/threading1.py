import random
import numpy as np
from hexss.threading import Multithread
import time
from flask import Flask
import tkinter as tk

# web server
app = Flask(__name__)


@app.route('/color')
def color():
    data = app.config['data']
    return data["random_color"]


@app.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Color Display</title>
        <script>
            function updateColor() {
                fetch('/color')
                    .then(response => response.text())
                    .then(color => {
                        document.getElementById('color').textContent = color;
                    });
            }
            setInterval(updateColor, 500);
        </script>
    </head>
    <body>
        <h1 id="color"></h1>
    </body>
    </html>
    '''


def run_server(data):
    app.config['data'] = data
    app.run(debug=False, use_reloader=False)


# normal loop
def capture(data):
    while data['play']:
        random_color = [random.randint(150, 255) for _ in range(3)]
        data['random_color'] = f'{random_color}'
        data['img'] = np.full((500, 500, 3), random_color, dtype=np.uint8)
        time.sleep(0.5)


# tk
def tk_ui(data):
    root = tk.Tk()
    root.geometry("300x100")
    root.title("Random Color Updater")

    var = tk.StringVar()
    label = tk.Label(root, textvariable=var, relief=tk.RAISED, font=("Arial", 14))
    var.set(data['random_color'])
    label.pack(pady=20)

    def update_label():
        if data['play']:
            var.set(data['random_color'])
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
        'random_color': '-',
    }

    m.add_func(capture, args=(data,))
    m.add_func(run_server, args=(data,), join=False)
    m.add_func(tk_ui, args=(data,))

    m.start()
    m.join()


if __name__ == '__main__':
    main()
