import sys
import subprocess
import platform
import base64
import json
import os
import time
import threading
import urllib.request
import urllib.error
from typing import Optional

import hexss
from hexss.constants import *
from hexss.path import get_hexss_dir
from hexss.pyconfig import Config

hexss.check_packages('numpy', 'opencv-python', 'Flask', auto_install=True, venv_only=False)

import cv2
from flask import Flask, request, jsonify, render_template, Response


def get_backend_api(os_name):
    if os_name == 'Windows':
        return cv2.CAP_DSHOW
    elif os_name == 'Linux':
        return cv2.CAP_V4L2
    elif os_name == 'Darwin':
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def get_available_cameras(os_name):
    cameras = []
    if os_name == 'Windows':
        try:
            from pygrabber.dshow_graph import FilterGraph
            cameras = FilterGraph().get_input_devices()
        except ImportError:
            cameras = ["USB Camera 0", "Webcam 1"]
    else:
        cameras = ["Camera 0", "Camera 1"]
    return cameras


class CameraManager:
    def __init__(self):
        self.os_name = platform.system()
        self.api_pref = get_backend_api(self.os_name)
        self.available_cameras = get_available_cameras(self.os_name)
        self.active_caps = {}
        self.latest_frames = {}
        self.threads = {}
        self.running = {}

    def get_list(self):
        return [{"id": i, "name": n, "connected": i in self.active_caps} for i, n in enumerate(self.available_cameras)]

    def connect(self, cam_id):
        if cam_id not in self.active_caps:
            cap = cv2.VideoCapture(cam_id, self.api_pref)
            if cap.isOpened():
                self.active_caps[cam_id] = cap
                self.running[cam_id] = True
                self.latest_frames[cam_id] = None
                thread = threading.Thread(target=self._update_frame, args=(cam_id,), daemon=True)
                self.threads[cam_id] = thread
                thread.start()

                return True
        return False

    def _update_frame(self, cam_id):
        while self.running.get(cam_id, False):
            if cam_id in self.active_caps:
                ret, frame = self.active_caps[cam_id].read()
                if ret:
                    self.latest_frames[cam_id] = frame

    def disconnect(self, cam_id):
        if cam_id in self.active_caps:
            self.running[cam_id] = False
            if cam_id in self.threads:
                self.threads[cam_id].join(timeout=1.0)
                del self.threads[cam_id]

            self.active_caps[cam_id].release()
            del self.active_caps[cam_id]

            if cam_id in self.latest_frames:
                del self.latest_frames[cam_id]
            return True
        return False

    def set_prop(self, cam_id, prop_name, prop_val):
        if cam_id in self.active_caps:
            try:
                prop_id = getattr(cv2, prop_name)
                print(prop_name, prop_id, prop_val)
                self.active_caps[cam_id].set(prop_id, float(prop_val))
                return True
            except AttributeError:
                print(f"Unknown OpenCV Property: {prop_name}")
        return False

    def read(self, cam_id):
        if cam_id in self.latest_frames:
            return self.latest_frames[cam_id]
        return None


cam_manager = CameraManager()
outputs = {}
PROFILE_DIR = get_hexss_dir() / 'config' / 'camera_server' / 'profiles'
PROFILE_DIR.mkdir(exist_ok=True, parents=True)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))


def get_profile_path(profile_name):
    safe_name = "".text if not profile_name else "".join(c for c in profile_name if c.isalnum() or c in ('_', '-'))
    return os.path.join(PROFILE_DIR, f"{safe_name or 'default'}.json")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/system_info', methods=['GET'])
def system_info():
    profiles = [f.split('.')[0] for f in os.listdir(PROFILE_DIR) if f.endswith('.json')]
    if not profiles:
        profiles = ['default']
    return jsonify({
        "os": cam_manager.os_name,
        "cameras": cam_manager.get_list(),
        "profiles": profiles
    })


@app.route('/api/connect/<int:cam_id>', methods=['POST'])
def connect_camera(cam_id):
    if cam_manager.connect(cam_id): return jsonify({"success": True})
    return jsonify({"success": False})


@app.route('/api/disconnect/<int:cam_id>', methods=['POST'])
def disconnect_camera(cam_id):
    if cam_manager.disconnect(cam_id): return jsonify({"success": True})
    return jsonify({"success": False})


@app.route('/api/profile/<profile_name>', methods=['GET'])
def load_profile(profile_name):
    path = get_profile_path(profile_name)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({})


@app.route('/api/profile/<profile_name>', methods=['POST'])
def save_profile(profile_name):
    path = get_profile_path(profile_name)
    graph_data = request.json
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=4)
    return jsonify({"success": True})


def get_execution_path(nodes, current_node_id, visited=None):
    if visited is None:
        visited = set()
    path = []
    current_node = nodes.get(current_node_id)
    if not current_node:
        return path
    try:
        node_outputs = current_node.get('outputs', {})
        connections = []
        if 'trigger_out' in node_outputs:
            connections = node_outputs['trigger_out']['connections']
        elif 'trigger' in node_outputs:
            connections = node_outputs['trigger']['connections']

        for conn in connections:
            next_node_id = str(conn['node'])
            if next_node_id in visited: continue
            visited.add(next_node_id)
            path.append(next_node_id)
            path.extend(get_execution_path(nodes, next_node_id, visited))
    except KeyError:
        pass
    return path


@app.route('/api/execute_trigger/<profile_name>/<trigger_name>', methods=['POST', 'GET'])
def execute_trigger(profile_name, trigger_name):
    global outputs
    path = get_profile_path(profile_name)
    if not os.path.exists(path):
        return jsonify({"success": False, "message": "ไม่พบโปรไฟล์นี้"}), 404

    with open(path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)

    nodes = graph_data.get('nodes', {})
    target_trigger_id = None
    for n_id, node in nodes.items():
        if node['name'] == 'Trigger' and node['data'].get('trigger_name', 'trigger1') == trigger_name:
            target_trigger_id = n_id
            break

    if not target_trigger_id:
        return jsonify({"success": False, "message": f"ไม่พบ Trigger: {trigger_name}"}), 404

    execution_path = get_execution_path(nodes, target_trigger_id)
    results = {}

    for node_id in execution_path:
        node = nodes[node_id]
        node_type = node['name']
        print(node_id, node_type)

        if node_type not in ['Prop', 'Read', 'Delay']: continue

        try:
            if node_type == 'Delay':
                delay_ms = float(node['data'].get('delay_ms', 100))
                time.sleep(delay_ms / 1000.0)
                continue
            cam_conn = node['inputs']['cam']['connections'][0]
            cam_node_id = str(cam_conn['node'])
            cam_device_id = int(nodes[cam_node_id]['data'].get('cam_id', 0))

            if cam_device_id not in cam_manager.active_caps:
                cam_manager.connect(cam_device_id)

            if node_type == 'Prop':
                prop_name = node['data'].get('prop_name', '')
                prop_val = float(node['data'].get('prop_val', 0))
                cam_manager.set_prop(cam_device_id, prop_name, prop_val)

            elif node_type == 'Read':
                output_name = node['data'].get('output_name', f'img_{node_id}')
                frame = cam_manager.read(cam_device_id)
                if frame is not None:
                    outputs[output_name] = {'type': 'img', 'value': frame}
                    _, buffer = cv2.imencode('.jpg', cv2.resize(frame, (320, 240)))
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    results[output_name] = f"data:image/jpeg;base64,{img_base64}"
        except Exception as e:
            print(f"Error on Node {node_id}:", e)

    return jsonify({"success": True, "trigger_executed": trigger_name, "images": results})


@app.route('/api/image/<int:cam_id>', methods=['GET'])
def get_camera_image(cam_id):
    quality_param = request.args.get('quality', default=100, type=int)
    quality_param = max(0, min(100, quality_param))
    jpeg_quality = int(quality_param)

    frame = cam_manager.read(cam_id)

    if frame is None:
        return jsonify({"success": False, "message": "No image found or the camera is not connected."}), 404

    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    success, buffer = cv2.imencode('.jpg', frame, encode_param)

    if not success:
        return jsonify({"success": False, "message": "Image encoding failed."}), 500

    return Response(buffer.tobytes(), mimetype='image/jpeg')


def generate_frames(cam_id):
    while True:
        frame = cam_manager.read(cam_id)

        if frame is None:
            time.sleep(0.1)
            continue

        success, buffer = cv2.imencode('.jpg', frame)
        if not success:
            continue

        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        time.sleep(1.0 / 30.0)


@app.route('/api/video/<int:cam_id>', methods=['GET'])
def video_feed(cam_id):
    if cam_id not in cam_manager.active_caps:
        return jsonify({"success": False, "message": "ยังไม่ได้เชื่อมต่อกล้อง"}), 404

    return Response(generate_frames(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')


def execute_start_node(profile_name="default"):
    path = get_profile_path(profile_name)
    if not os.path.exists(path):
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)

        nodes = graph_data.get('nodes', {})
        start_node_id = None

        # ค้นหาว่ามีกล่องชื่อ Start หรือไม่
        for n_id, node in nodes.items():
            if node['name'] == 'Start':
                start_node_id = n_id
                break

        if not start_node_id:
            return

        print(f"[*] Found Start node in '{profile_name}' profile. Executing...")
        execution_path = get_execution_path(nodes, start_node_id)

        for node_id in execution_path:
            node = nodes[node_id]
            node_type = node['name']

            if node_type not in ['Prop', 'Read', 'Delay']:
                continue

            if node_type == 'Delay':
                delay_ms = float(node['data'].get('delay_ms', 100))
                time.sleep(delay_ms / 1000.0)
                continue

            if 'cam' in node.get('inputs', {}) and node['inputs']['cam']['connections']:
                cam_conn = node['inputs']['cam']['connections'][0]
                cam_node_id = str(cam_conn['node'])
                cam_device_id = int(nodes[cam_node_id]['data'].get('cam_id', 0))

                if cam_device_id not in cam_manager.active_caps:
                    print(f"[*] Auto-connecting Camera ID {cam_device_id}...")
                    cam_manager.connect(cam_device_id)

                if node_type == 'Prop':
                    prop_name = node['data'].get('prop_name', '')
                    prop_val = float(node['data'].get('prop_val', 0))
                    cam_manager.set_prop(cam_device_id, prop_name, prop_val)
                    print(f"[*] Set {prop_name} = {prop_val} for Camera {cam_device_id}")

    except Exception as e:
        print(f"[!] Error executing Start node: {e}")


@app.route('/api/status', methods=['GET'])
def server_status():
    return jsonify({"success": True, "status": "running", "message": "Camera server is active"})


def delayed_shutdown():
    time.sleep(1)
    os._exit(0)


@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    print("[*] Shutdown signal received. Releasing cameras...")

    active_ids = list(cam_manager.active_caps.keys())
    for cam_id in active_ids:
        cam_manager.disconnect(cam_id)

    threading.Thread(target=delayed_shutdown, daemon=True).start()

    return jsonify({"success": True, "message": "Server is shutting down..."})


def is_server_running(port):
    try:
        url = f"http://127.0.0.1:{port}/api/status"
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=1) as response:
            if response.status == 200:
                return True
    except Exception:
        return False
    return False


def run(profile_name="default", background=False, port: Optional[int] = None):
    c = Config(get_hexss_dir() / 'config/camera_server/cfg.py')
    host = c.host = c.host or '0.0.0.0'
    port = c.port = port or c.port or 2002

    if is_server_running(port):
        print(f"[*] Camera Server is already running on background at http://127.0.0.1:{port}")
        print("[*] Skipped creating a new process.")
        return

    if background:
        script = f"from hexss import camera_server; camera_server.run(profile_name='{profile_name}', background=False, port={port})"
        cmd = [sys.executable, "-c", script]

        if platform.system() == 'Windows':
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"[*] Camera Server started in background at http://127.0.0.1:{port}")
        return

    execute_start_node(profile_name)
    txt = ''
    if host != '0.0.0.0':
        txt += f'🌐 {CYAN}Camera server started at: http://{host}:{port}{END}\n'
    else:
        txt += f'🌐 {CYAN}Camera server started at:{END}\n'
        for _host in hexss.network.get_local_ipv4_hosts():
            txt += f'http://{_host}:{port}\n'
    print(end=txt)
    app.run(host=host, port=port, debug=False, use_reloader=False)
