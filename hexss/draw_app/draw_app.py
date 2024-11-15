# app.py
from datetime import datetime
import cv2
import numpy as np
from flask import Flask, render_template, jsonify, request, Response
import os
from hexss import json_update, json_load


class Video:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.frame_number = 0
        self.json_path = os.path.join('data', os.path.splitext(os.path.basename(path))[0] + '.json')
        self.rectangles = json_load(self.json_path, {})

    def get_img(self):
        if 0 <= self.frame_number < self.total_frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_number)
            ret, frame = self.cap.read()
            if ret:
                return frame
        return None

    def update_rectangles(self, new_data):
        self.rectangles = json_update(self.json_path, new_data)


video = None
app = Flask(__name__)


@app.route('/')
def index():
    videos = [f for f in os.listdir('data') if f.endswith(('.mp4', '.avi'))]
    return render_template('index.html', videos=videos)


@app.route('/api/setup_video')
def setup_video():
    global video
    file_name = request.args.get('name', default='', type=str)
    if file_name and file_name in os.listdir('data'):
        video_path = os.path.join('data', file_name)
        video = Video(video_path)
        return jsonify({
            'success': True,
            'total_frames': video.total_frames,
            'rectangles': video.rectangles
        })
    return jsonify({'success': False, 'error': 'Invalid video file'})


@app.route('/api/set_frame_number')
def set_frame_number():
    global video
    if video is None:
        return jsonify({'success': False, 'error': 'Video not set up'})
    video.frame_number = request.args.get('frame', default=0, type=int)
    return jsonify({'success': True, 'frame': video.frame_number})


@app.route('/api/get_img')
def get_video():
    def generate():
        global video
        if video is None:
            return jsonify({'success': False, 'error': 'Video not set up'})
        while True:
            img = video.get_img()
            if img is None:
                img = np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
                cv2.putText(img, 'No image available', (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.putText(img, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 1,
                            (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', img)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/save_rectangle', methods=['POST'])
def save_rectangle():
    global video
    if video is None:
        return jsonify({'success': False, 'error': 'Video not set up'})
    data = request.json
    video.update_rectangles({str(data['frame']): data['rectangles']})

    return jsonify({'success': True})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5002, debug=True)
