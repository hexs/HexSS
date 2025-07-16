import time
from pathlib import Path
import cv2
import base64
from hexss.threading import Multithread
from hexss.draw_app.app import run_server


def generate_image(data):
    while True:
        video = data.get('video')
        if video is None:
            time.sleep(0.5)
            continue

        img = video.get_img()
        if img is None:
            print('No frame to display.')
            time.sleep(0.5)
            continue

        cv2.putText(img, video.get_frame_name(), (10, 100), 0, 3, (0, 0, 255), 2, cv2.LINE_AA)
        _, buffer = cv2.imencode('.jpg', img)
        data['response'] = {
            "image": 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8'),
            'current_frame_number': video.current_frame_number,
            'current_frame_name': video.current_frame_name,
            'total_frames': video.total_frames,
            'rectangles': video.rectangles.get(video.current_frame_name, {})
        }
        time.sleep(0.01)


def run(path: Path | str | None = None):
    data = {
        'path': Path(path) if path else Path('data'),
        'play': True,
        'response': None,
        'video': None,
    }

    m = Multithread()
    m.add_func(target=generate_image, args=(data,))
    m.add_func(target=run_server, args=(data,), join=False)
    m.start()
    m.join()


if __name__ == '__main__':
    run('data')
