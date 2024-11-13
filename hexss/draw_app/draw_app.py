# app.py
from datetime import datetime
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, request, Response
import os


class Video:
    def __init__(self, path):
        self.path = path
        self.cap = None
        self.total_frames = self.get_total_frames()
        self.frame_number = 0

    def get_total_frames(self):
        self.cap = cv2.VideoCapture(self.path)
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return total

    def get_img(self):
        if 0 <= self.frame_number < self.total_frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_number)
            return self.cap.read()[1]


video = None
app = Flask(__name__)


@app.route('/')
def index():
    videos = os.listdir('data')
    return render_template('index.html', videos=videos)


@app.route('/api/setup_video')
def setup_video():
    global video

    file_name = request.args.get('name', default='', type=str)
    if file_name and file_name in os.listdir('data'):
        video = Video(os.path.join('data', file_name))
        print('video.total_frames', video.total_frames)
        return jsonify({
            'success': True,
            'total_frames': video.total_frames
        })
    return jsonify({'success': False, 'error': 'Invalid video file'})


@app.route('/api/set_frame_number')
def set_frame_number():
    global video
    if video is None:
        return "setup_video"
    video.frame_number = request.args.get('frame', default=0, type=int)
    return jsonify({'success': True, 'frame': video.frame_number})


@app.route('/api/get_img')
def get_video():
    def generate():
        if video is None:
            return "setup_video"
        while True:
            img = video.get_img()
            if img is None:
                img = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
                cv2.putText(img, f'img = None', (30, 50), 1, 2, (0, 0, 255), 2)
                cv2.putText(img, datetime.now().strftime('%Y-%m-%d  %H:%M:%S'), (30, 130), 1, 2, (0, 0, 255), 2)

            ret, buffer = cv2.imencode('.jpg', img)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run('0.0.0.0', port=5002, debug=True)
