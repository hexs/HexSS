import platform
import time
import logging
from typing import Dict, Any, List

from hexss import json_load, json_update, check_packages

if platform.system() == "Windows":
    check_packages('numpy', 'opencv-python', 'Flask', 'mss', auto_install=True, verbose=False)
    import mss
else:
    check_packages('numpy', 'opencv-python', 'Flask', auto_install=True, verbose=False)

from hexss import get_hostname
from hexss.network import get_all_ipv4, close_port
from hexss.threading import Multithread
import numpy as np
from flask import Flask, render_template, Response, request, redirect, url_for
import cv2
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def display_capture(data: Dict[str, Any]) -> None:
    if platform.system() != "Windows":
        logging.warning("Display capture is only supported on Windows.")
        return

    with mss.mss() as sct:
        while data['play']:
            try:
                screenshot = sct.grab(sct.monitors[0])
                image = np.array(screenshot)
                data['display_capture'] = image
            except Exception as e:
                logging.error(f"Error in display capture: {e}")
                time.sleep(1)


def video_capture(data: Dict[str, Any], camera_id: int) -> None:
    def setup() -> cv2.VideoCapture:
        cap = cv2.VideoCapture(camera_id)
        cap.set(3, data['config']['camera'][camera_id]['width_height'][0])
        cap.set(4, data['config']['camera'][camera_id]['width_height'][1])
        data['config']['camera'][camera_id]['width_height_from_cap'] = [int(cap.get(3)), int(cap.get(4))]
        return cap

    cap = setup()
    while data['play']:
        try:
            if data['config']['camera'][camera_id]['setup']:
                data['config']['camera'][camera_id]['setup'] = False
                cap.release()
                cap = setup()

            if data['config']['camera'][camera_id]['camera_enabled']:
                status, img = cap.read()
                data['config']['camera'][camera_id]['status'] = status
                data['config']['camera'][camera_id]['img'] = img
                if not status:
                    logging.warning(f"Failed to capture image from camera {camera_id}")
                    time.sleep(1)
                    cap.release()
                    cap = setup()

        except Exception as e:
            logging.error(f"Error in video capture for camera {camera_id}: {e}")
            time.sleep(1)


def get_data(data: Dict[str, Any], source: str, camera_id: int, quality=100) -> np.ndarray:
    if source == 'video_capture':
        frame = data['config']['camera'][camera_id]['img']
        status = data['config']['camera'][camera_id]['status']
        if not status:
            w, h = data['config']['camera'][camera_id]['width_height']
            frame = np.full((int(h), int(w), 3), (50, 50, 50), dtype=np.uint8)
            cv2.putText(frame, f'Failed to capture image', (100, 150), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, f'from camera {camera_id}', (100, 190), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (100, 230), 1, 2, (0, 0, 255), 2)
    else:  # source == 'display_capture':
        frame = data['display_capture']
    if quality == 100:
        ret, buffer = cv2.imencode('.jpg', frame)
    else:
        encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]  # Adjust quality (0-100)
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


@app.route('/')
def index():
    data = app.config['data']
    camera_states = [
        {
            'camera_enabled': data['config']['camera'][camera_id]['camera_enabled'],
            'width': data['config']['camera'][camera_id]['width_height_from_cap'][0],
            'height': data['config']['camera'][camera_id]['width_height_from_cap'][1]
        } for camera_id in range(len(data['config']['camera']))
    ]
    return render_template('camera.html', camera_states=camera_states)


@app.route('/update_cameras', methods=['POST'])
def update_cameras():
    data = app.config['data']
    for camera_id in range(len(data['config']['camera'])):
        camera_key = f'camera_{camera_id}'
        data['config']['camera'][camera_id]['camera_enabled'] = camera_key in request.form
        width = request.form.get(f'w{camera_key}')
        height = request.form.get(f'h{camera_key}')
        if width and height:
            data['config']['camera'][camera_id]['width_height'] = [int(width), int(height)]
            data['config']['camera'][camera_id]['width_height_from_cap'] = [None, None]
            data['config']['camera'][camera_id]['setup'] = True

            # update config file
            config = json_load('camera_server_config.json')
            config['camera'][camera_id]['width_height'] = [int(width), int(height)]
            json_update('camera_server_config.json', config)

    return redirect(url_for('index'))


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    quality = request.args.get('quality', default=100, type=int)
    buffer = get_data(app.config['data'], source, camera_id, quality)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/video')
def get_video():
    data = app.config['data']
    source = request.args.get('source', default='display_capture', type=str)
    camera_id = request.args.get('id', default=0, type=int)
    quality = request.args.get('quality', default=30, type=int)

    def generate():
        while data['play']:
            buffer = get_data(app.config['data'], source, camera_id, quality)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data: Dict[str, Any]) -> None:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.config['data'] = data
    ipv4 = data['config']['ipv4']
    port = data['config']['port']
    if ipv4 == '0.0.0.0':
        for ipv4_ in {'127.0.0.1', *get_all_ipv4(), get_hostname()}:
            logging.info(f"Running on http://{ipv4_}:{port}")
    else:
        logging.info(f"Running on http://{ipv4}:{port}")
    app.run(host=ipv4, port=port, debug=False, use_reloader=False)


def run():
    config = json_load('camera_server_config.json', {
        "ipv4": '0.0.0.0',
        "port": 2002,
        "camera": [
            {
                "width_height": [640, 480]
            }
        ]
    }, dump=True)
    close_port(config['ipv4'], config['port'], verbose=False)

    data = {
        'play': True,
        'config': config
    }

    m = Multithread()
    for camera_id in range(len(data['config']['camera'])):
        data['config']['camera'][camera_id]['status'] = False
        data['config']['camera'][camera_id]['img'] = None
        data['config']['camera'][camera_id]['camera_enabled'] = True
        data['config']['camera'][camera_id]['width_height_from_cap'] = [None, None]
        data['config']['camera'][camera_id]['setup'] = False
    data['display_capture'] = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)

    for camera_id in range(len(data['config']['camera'])):
        m.add_func(video_capture, args=(data, camera_id))
    m.add_func(display_capture, args=(data,))
    m.add_func(run_server, args=(data,), join=False)

    m.start()
    try:
        while data['play']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        data['play'] = False
        m.join()


if __name__ == "__main__":
    run()
