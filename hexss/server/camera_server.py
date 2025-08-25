import json
import platform
import time
import logging
from typing import Dict, Any, List
from datetime import datetime

import hexss

if platform.system() == "Windows":
    hexss.check_packages('numpy', 'opencv-python', 'Flask', 'mss', auto_install=True, venv_only=False)
    import mss
else:
    hexss.check_packages('numpy', 'opencv-python', 'Flask', auto_install=True, venv_only=False)

from hexss.config import load_config, update_config
from hexss.network import get_all_ipv4, close_port
from hexss.threading import Multithread
import numpy as np
import cv2
from flask import Flask, render_template, Response, request, redirect, url_for, current_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
app = Flask(__name__)


def display_capture(data: Dict[str, Any]) -> None:
    if platform.system() != "Windows":
        logger.warning("Display capture is only supported on Windows.")
        return
    with mss.mss() as sct:
        while data.get('play', False):
            try:
                screenshot = sct.grab(sct.monitors[0])
                image = np.array(screenshot)
                data['display_capture'] = image
            except Exception as e:
                logger.error(f"Error in display capture: {e}")
                time.sleep(1)


def video_capture(data: Dict[str, Any], camera_id: int) -> None:
    def setup() -> cv2.VideoCapture:
        cap = cv2.VideoCapture(camera_id)
        settings = data['config']['camera'][camera_id]
        width, height = settings.get('width_height', [640, 480])
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        settings['width_height_from_cap'] = [int(cap.get(3)), int(cap.get(4))]
        if settings.get('CAP_PROP_AUTO_EXPOSURE'):
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, settings.get('CAP_PROP_AUTO_EXPOSURE'))
        if settings.get('CAP_PROP_EXPOSURE'):
            cap.set(cv2.CAP_PROP_EXPOSURE, settings.get('CAP_PROP_EXPOSURE'))

        return cap

    cap = setup()
    while data.get('play', False):
        try:
            settings = data['config']['camera'][camera_id]
            if settings['setup']:
                settings['setup'] = False
                cap.release()
                cap = setup()
            if settings['camera_enabled']:
                status, img = cap.read()
                settings['status'] = status
                settings['img'] = img
                if not status:
                    logger.warning(f"Failed to capture image from camera {camera_id}")
                    time.sleep(1)
                    cap.release()
                    cap = setup()
        except Exception as e:
            logger.error(f"Error in video capture for camera {camera_id}: {e}")
            time.sleep(1)
    cap.release()


def get_data(data: Dict[str, Any], source: str, camera_id: int, quality: int = 100,
             crosshairs: list = []) -> np.ndarray:
    if source == 'video_capture':
        settings = data['config']['camera'][camera_id]
        frame = settings.get('img')
        status = settings.get('status')
        if not status or frame is None:
            w, h = settings.get('width_height', [640, 480])
            frame = np.full((int(h), int(w), 3), (50, 50, 50), dtype=np.uint8)
            cv2.putText(frame, f'Failed to capture image', (100, 150), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, f'from camera {camera_id}', (100, 190), 1, 2, (0, 0, 255), 2)
            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (100, 230), 1, 2, (0, 0, 255), 2)
    else:  # source == 'display_capture':
        frame = data.get('display_capture')
        if frame is None:
            frame = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
    for crosshair in crosshairs:
        if crosshair['type'] == 'line':
            cv2.line(frame, crosshair['pt1'], crosshair['pt2'], crosshair['color'], crosshair['thickness'])
        elif crosshair['type'] == 'circle':
            cv2.circle(frame, crosshair['center'], crosshair['radius'], crosshair['color'], crosshair['thickness'])
        elif crosshair['type'] == 'rectangle':
            cv2.rectangle(frame, crosshair['pt1'], crosshair['pt2'], crosshair['color'], crosshair['thickness'])
    encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]
    ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


crosshairs = [{"type": "circle", "center": [500, 500], "radius": 100, "color": [255, 0, 0], "thickness": 2}]


@app.route('/')
def index():
    data = current_app.config['data']
    camera_states = [
        {
            'camera_enabled': cam.get('camera_enabled', False),
            'width': cam.get('width_height_from_cap', [None, None])[0],
            'height': cam.get('width_height_from_cap', [None, None])[1]
        }
        for cam in data['config']['camera']
    ]
    return render_template('camera.html', camera_states=camera_states)


@app.route('/update_cameras', methods=['POST'])
def update_cameras():
    data = current_app.config['data']
    for camera_id, cam in enumerate(data['config']['camera']):
        camera_key = f'camera_{camera_id}'
        cam['camera_enabled'] = camera_key in request.form
        width = request.form.get(f'w{camera_key}')
        height = request.form.get(f'h{camera_key}')
        if width and height:
            cam['width_height'] = [int(width), int(height)]
            cam['width_height_from_cap'] = [None, None]
            cam['setup'] = True
            config = load_config('camera_server')
            config['camera'][camera_id]['width_height'] = [int(width), int(height)]
            update_config('camera_server', config)
    return redirect(url_for('index'))


@app.route('/image')
def get_image():
    source = request.args.get('source', default='display_capture', type=str)  # display_capture, video_capture,
    camera_id = request.args.get('id', default=0, type=int)  # 1, 2, ...
    quality = request.args.get('quality', default=100, type=int)
    buffer = get_data(current_app.config['data'], source, camera_id, quality)
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/video')
def get_video():
    data = current_app.config['data']
    source = request.args.get('source', default='display_capture', type=str)
    camera_id = request.args.get('id', default=0, type=int)
    quality = request.args.get('quality', default=30, type=int)
    sleep = request.args.get('sleep', default=0.05, type=float)
    crosshairs = request.args.get('crosshairs', default='', type=str)
    try:
        crosshairs = json.loads(crosshairs)
    except:
        logger.error(f"Invalid crosshairs JSON: {crosshairs}")
        crosshairs = []

    def generate():
        while data.get('play', False):
            buffer = get_data(data, source, camera_id, quality, crosshairs)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(sleep)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def run_server(data: Dict[str, Any]) -> None:
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.config['data'] = data
    ipv4 = data['config']['ipv4']
    port = data['config']['port']
    if ipv4 == '0.0.0.0':
        for ipv4_ in {'127.0.0.1', *get_all_ipv4(), hexss.get_hostname()}:
            logger.info(f"Running on http://{ipv4_}:{port}")
    else:
        logger.info(f"Running on http://{ipv4}:{port}")
    app.run(host=ipv4, port=port, debug=False, use_reloader=False)


def run():
    config = load_config('camera_server', {
        "ipv4": '0.0.0.0',
        "port": 2002,
        "camera": [{"width_height": [640, 480]}]
    })
    close_port(config['ipv4'], config['port'], verbose=False)
    data: Dict[str, Any] = {
        'play': True,
        'config': config,
        'display_capture': np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
    }

    m = Multithread()
    for camera_id, cam in enumerate(data['config']['camera']):
        cam.setdefault('status', False)
        cam.setdefault('img', None)
        cam.setdefault('camera_enabled', True)
        cam.setdefault('width_height_from_cap', [None, None])
        cam.setdefault('setup', False)
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
