from flask import Flask, render_template, jsonify, request, Response
from pathlib import Path
import json
from threading import Lock
from hexss.draw_app.media_sequence import MediaSequence

app = Flask(__name__)
video_lock = Lock()


@app.route('/')
def index():
    path = Path(app.config['data']['path'])
    videos = [f.name for f in path.iterdir() if f.suffix.lower() in ('.mp4', 'mkv', '.avi') and f.is_file()]
    folders = [f.name for f in path.iterdir() if f.is_dir()]
    return render_template('index.html', entries=sorted(videos + folders))


@app.route('/api/setup_video')
def setup_video():
    path = Path(app.config['data']['path'])
    file_name = request.args.get('name', '', type=str)
    file_path = path / file_name

    if not file_name or not file_path.exists():
        return jsonify({'success': False, 'error': 'Invalid or missing video file'})

    with video_lock:
        try:
            app.config['data']['video'] = MediaSequence(file_path)
            video = app.config['data']['video']
            return jsonify({
                'success': True,
                'current_frame_number': video.current_frame_number,
                'current_frame_name': video.current_frame_name,
                'total_frames': video.total_frames,
                'rectangles': video.rectangles.get(video.current_frame_name, {})
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


@app.route('/api/set_frame_number')
def set_frame_number():
    frame_number = request.args.get('frame', 0, type=int)

    with video_lock:
        video = app.config['data'].get('video')
        if not video:
            return jsonify({'success': False, 'error': 'Video not set up'})

        if not (0 <= frame_number < video.total_frames):
            return jsonify({'success': False, 'error': 'Frame out of range'})

        video.current_frame_number = frame_number
        video.current_frame_name = video.get_frame_name()
        return jsonify({
            'success': True,
            'current_frame_number': video.current_frame_number,
            'current_frame_name': video.current_frame_name
        })


@app.route('/api/get_json_data')
def get_json_data():
    def generate():
        old_response = None
        while True:
            with video_lock:
                response = app.config['data'].get('response')
                if response != old_response:
                    old_response = response
                    yield f"data: {json.dumps(response)}\n\n"

    return Response(generate(), content_type='text/event-stream')


@app.route('/api/save_rectangle', methods=['POST'])
def save_rectangle():
    with video_lock:
        video = app.config['data'].get('video')
        if not video:
            return jsonify({'success': False, 'error': 'Video not set up'})

        try:
            data = request.get_json()
            frame_name = str(data.get('frameName', ''))
            rectangles = data.get('rectangles', {})
            video.update_rectangles({frame_name: rectangles})
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


def run_server(data):
    app.config['data'] = data
    app.run(host="0.0.0.0", port=2003, debug=False, use_reloader=False)
