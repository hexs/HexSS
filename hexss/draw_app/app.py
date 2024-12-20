from flask import Flask, render_template, jsonify, request, Response
import os
import json
from threading import Lock

app = Flask(__name__)
video_lock = Lock()


@app.route('/')
def index():
    videos = [f for f in os.listdir('data') if f.endswith(('.mp4', '.avi'))]
    folders = [f for f in os.listdir('data') if os.path.isdir(os.path.join('data', f))]
    return render_template('index.html', entries=videos + folders)


@app.route('/api/setup_video')
def setup_video():
    with video_lock:  # Ensure thread-safe access
        try:
            file_name = request.args.get('name', default='', type=str)
            if file_name and file_name in os.listdir('data'):
                file_path = os.path.join('data', file_name)

                # Create Video object and assign it to `data`
                from run import Video  # Import Video from run module
                app.config['data']['video'] = Video(file_path)
                video = app.config['data']['video']

                print('setup ok', file_path)
                return jsonify({
                    'success': True,
                    'current_frame_number': video.current_frame_number,
                    'current_frame_name': video.current_frame_name,
                    'total_frames': video.total_frames,
                    "rectangles": video.rectangles.get(video.current_frame_name) or {}
                })
            return jsonify({'success': False, 'error': 'Invalid video file'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


@app.route('/api/set_frame_number')
def set_frame_number():
    with video_lock:  # Ensure thread-safe access
        try:
            video = app.config['data'].get('video', None)
            if video is None:
                return jsonify({'success': False, 'error': 'Video not set up'})

            frame_number = request.args.get('frame', default=0, type=int)
            video.current_frame_number = frame_number
            video.current_frame_name = video.get_frame_name()

            if not (0 <= video.current_frame_number < video.total_frames):
                return jsonify({'success': False, 'error': 'Frame out of range'})

            return jsonify({
                'success': True,
                'current_frame_number': video.current_frame_number,
                'current_frame_name': video.current_frame_name
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


@app.route('/api/get_json_data')
def get_json_data():
    def generate():
        old_data_response = None
        while True:
            with video_lock:  # Ensure thread-safe access
                if old_data_response != app.config['data'].get('response'):
                    old_data_response = app.config['data']['response']
                    print('send data')
                    yield f'''data: {json.dumps(old_data_response)}\n\n'''

    return Response(generate(), content_type='text/event-stream')


@app.route('/api/save_rectangle', methods=['POST'])
def save_rectangle():
    with video_lock:
        try:
            video = app.config['data'].get('video', None)
            if video is None:
                return jsonify({'success': False, 'error': 'Video not set up'})

            data = request.get_json()
            frame_name = str(data.get('frameName', ''))
            rectangles = data.get('rectangles', {})

            video.update_rectangles({frame_name: rectangles})
            return jsonify({'success': True})
        except Exception as e:
            print(f"Error saving rectangles: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})


def run_server(data):
    app.config['data'] = data
    app.run(host="0.0.0.0", port=5695, debug=False, use_reloader=False)
