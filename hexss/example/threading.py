import random
import numpy as np
import cv2
import time
import hexss
from hexss.threading import Multithread
from threading_app import run_server


def capture(data):
    while not data.get('close'):
        random_color = [random.randint(150,255) for _ in range(3)]
        data['img'] = np.full((500, 500, 3), random_color, dtype=np.uint8)
        time.sleep(0.5)


def show_img(data, multithread):
    cv2.namedWindow('image')
    font = cv2.FONT_HERSHEY_SIMPLEX
    while data.get('img') is None:
        time.sleep(0.1)
    while data['play']:
        img = data['img'].copy()

        # Get thread status
        status = multithread.get_status()

        cv2.putText(img, "ESC => data['play'] = False", (10, 30), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(img, "s => data['close'] = True", (10, 60), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        # Add status text to image
        y_offset = 100
        for thread in status:
            text = f"{thread['name']}: {thread['status']} ({thread['join']})"
            cv2.putText(img, text, (10, y_offset), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            y_offset += 30

        cv2.imshow('image', img)
        key = cv2.waitKey(1)
        if key == 27:
            data['play'] = False
        if key == ord('s'):
            data['close'] = True
    cv2.destroyAllWindows()


def main():
    m = Multithread()
    data = {
        'play': True
    }

    m.add_func(capture, args=(data,), join=True, name="Capture")
    m.add_func(show_img, args=(data, m), join=True, name="Display")
    m.add_func(run_server, args=(data, m), join=False, name="Server")

    m.start()
    hexss.open_url("http://127.0.0.1:5000")
    try:
        while data['play']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        data['play'] = False
        data['close'] = True
        m.join()


if __name__ == '__main__':
    main()
