from __future__ import annotations
import time
import threading
import json
import cv2
import numpy as np
from typing import List, Optional, Any
from flask import Flask, request, jsonify, abort, Response, render_template_string


class ExposureFusionEngine:
    def __init__(self, contrast_weight=1.0, saturation_weight=1.0, exposure_weight=1.0):
        self.wc, self.ws, self.we = contrast_weight, saturation_weight, exposure_weight

    def _compute_contrast(self, gray_img):
        return np.abs(cv2.Laplacian(gray_img, cv2.CV_64F))

    def _compute_saturation(self, img):
        return np.std(img, axis=2)

    def _compute_exposedness(self, img):
        sigma = 0.2
        gauss_curve = np.exp(-0.5 * np.power(img - 0.5, 2) / np.power(sigma, 2))
        return np.prod(gauss_curve, axis=2)

    def _generate_weight_maps(self, images):
        weights = []
        epsilon = 1e-12
        for img in images:
            img_norm = img / 255.0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) / 255.0
            c_ = self._compute_contrast(gray)
            s_ = self._compute_saturation(img_norm)
            e_ = self._compute_exposedness(img_norm)
            weights.append(np.power(c_, self.wc) * np.power(s_, self.ws) * np.power(e_, self.we) + epsilon)
        sum_weights = np.sum(weights, axis=0)
        return [w / sum_weights for w in weights]

    def _gaussian_pyramid(self, img, levels):
        pyr = [img]
        for _ in range(levels - 1): pyr.append(cv2.pyrDown(pyr[-1]))
        return pyr

    def _laplacian_pyramid(self, img, levels):
        gauss_pyr = self._gaussian_pyramid(img, levels)
        lap_pyr = []
        for i in range(levels - 1):
            h, w = gauss_pyr[i].shape[:2]
            upsampled = cv2.pyrUp(gauss_pyr[i + 1], dstsize=(w, h))
            lap_pyr.append(gauss_pyr[i] - upsampled)
        lap_pyr.append(gauss_pyr[-1])
        return lap_pyr

    def _reconstruct(self, pyramid):
        img = pyramid[-1]
        for i in range(len(pyramid) - 2, -1, -1):
            h, w = pyramid[i].shape[:2]
            img = cv2.pyrUp(img, dstsize=(w, h)) + pyramid[i]
        return img

    def fuse(self, images: List[np.ndarray]) -> Optional[np.ndarray]:
        if not images: return None
        shape = images[0].shape
        weights = self._generate_weight_maps(images)
        min_dim = min(shape[:2])
        num_levels = int(np.log2(min_dim)) - 2
        pyr_fusion = [np.zeros_like(img, dtype=np.float64) for img in self._gaussian_pyramid(images[0], num_levels)]

        for i in range(len(images)):
            img_float = images[i].astype(np.float64) / 255.0
            pyr_img = self._laplacian_pyramid(img_float, num_levels)
            pyr_weight = self._gaussian_pyramid(weights[i], num_levels)
            for level in range(num_levels):
                w_expanded = cv2.cvtColor(pyr_weight[level].astype(np.float32), cv2.COLOR_GRAY2BGR)
                pyr_fusion[level] += w_expanded * pyr_img[level]

        return (np.clip(self._reconstruct(pyr_fusion), 0, 1) * 255).astype(np.uint8)


def single_camera_worker(shared_state: dict, cam_id: str):
    print(f"[Camera {cam_id}] Worker Thread Started.")
    cam_config = shared_state['cameras'][cam_id]
    fusion_engine = ExposureFusionEngine()

    while shared_state['is_running'] and cam_config['is_running']:
        # print(f"[Camera {cam_id}] Connecting...")
        cam_config['fusion_state'] = 'CONNECTING...'

        try:
            cap = cv2.VideoCapture(int(cam_id))
        except Exception as e:
            print(f"[Camera {cam_id}] Exception connecting: {e}")
            cap = None

        if cap is None or not cap.isOpened():
            # print(f"[Camera {cam_id}] Connection failed. Retrying in 5s...")
            cam_config['fusion_state'] = 'DISCONNECTED'
            cam_config['latest_frame_data'] = (False, None)
            time.sleep(5)
            continue

        print(f"[Camera {cam_id}] Connected!")
        cam_config['fusion_state'] = 'READY'

        start_setting = cam_config.get('start_setting', [])
        capture_setting = cam_config['fused_setting'].get('capture_setting', [])
        after_that = cam_config['fused_setting'].get('after_that', [])

        for k, v in start_setting:
            cap.set(k, v)

        while shared_state['is_running'] and cam_config['is_running']:
            ret, frame = cap.read()
            if not ret:
                print(f"[Camera {cam_id}] Lost signal.")
                break

            cam_config['latest_frame_data'] = (ret, frame)

            if cam_config['fusion_state'] == 'REQUESTED':
                cam_config['fusion_state'] = 'PROCESSING'
                print(f"[Camera {cam_id}] Processing Fusion...")

                captured_frames = []
                cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Manual
                ret, _frame = cap.read()
                last_mean = np.mean(_frame) if ret else 0
                fusion_error = False

                for setting_group in capture_setting:
                    if fusion_error: break
                    for k, v in setting_group: cap.set(k, v)

                    start_t = time.time()
                    has_changed = False
                    stable_count = 0
                    prev_b = 0

                    while (time.time() - start_t) < 2.0:
                        ret, frame = cap.read()
                        if not ret:
                            fusion_error = True
                            break
                        cam_config['latest_frame_data'] = (ret, frame)
                        curr_b = np.mean(frame)

                        if not has_changed:
                            safe_old = last_mean if last_mean > 0.001 else 0.001
                            if abs(curr_b - safe_old) / safe_old > 0.15: has_changed = True

                        if has_changed:
                            if abs(curr_b - prev_b) < 1.0:
                                stable_count += 1
                            else:
                                stable_count = 0
                            if stable_count >= 3: break
                        prev_b = curr_b

                    if not fusion_error and cam_config['latest_frame_data'][1] is not None:
                        captured_frames.append(cam_config['latest_frame_data'][1].copy())
                        last_mean = np.mean(cam_config['latest_frame_data'][1])

                if fusion_error: break

                if captured_frames:
                    print(f"[Camera {cam_id}] Fusing {len(captured_frames)} frames...")
                    result = fusion_engine.fuse(captured_frames)
                    cam_config['fused_result'] = result

                for k, v in after_that: cap.set(k, v)
                cap.read()
                cam_config['fusion_state'] = 'READY'
                print(f"[Camera {cam_id}] Fusion Done.")

            time.sleep(0.01)

        cap.release()
        cam_config['latest_frame_data'] = (False, None)
        cam_config['fusion_state'] = 'DISCONNECTED'
        time.sleep(1)

    print(f"[Camera {cam_id}] Worker Stopped.")


app = Flask(__name__)


def generate_placeholder_image(text="No Data", color=(50, 50, 50)):
    img = np.zeros((360, 480, 3), dtype=np.uint8)
    img[:] = color
    # Centered text calculation roughly
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(text, font, 1, 2)[0]
    text_x = (img.shape[1] - text_size[0]) // 2
    text_y = (img.shape[0] + text_size[1]) // 2
    cv2.putText(img, text, (text_x, text_y), font, 1, (255, 255, 255), 2)
    return img


def sanitize_value(value: Any) -> Any:
    simple_types = (bool, int, float, str, type(None))
    if isinstance(value, simple_types): return value
    if isinstance(value, (list, tuple)): return [sanitize_value(v) for v in value]
    if isinstance(value, dict): return {str(k): sanitize_value(v) for k, v in value.items()}
    return str(type(value))


def resolve_path(root: Any, path: str, sep: str = "/") -> Any:
    if not path: return root
    parts = [p for p in path.split(sep) if p != ""]
    node = root
    for part in parts:
        if isinstance(node, dict):
            if part not in node: abort(404, description=f"Key '{part}' not found.")
            node = node[part]
        elif isinstance(node, (list, tuple)):
            try:
                idx = int(part)
            except ValueError:
                abort(404, description="Invalid integer.")
            try:
                node = node[idx]
            except IndexError:
                abort(404, description="Index out of range.")
        else:
            abort(404, description=f"Cannot go deeper at '{part}'.")
    return node


def _parse_value(v: str) -> Any:
    if v.lower() == 'true': return True
    if v.lower() == 'false': return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _get_camera_node(shared_state: dict, cam_id: str) -> dict:
    cameras = shared_state.get("cameras") or {}
    cam = cameras.get(str(cam_id))
    if cam is None: abort(404, description=f"Camera {cam_id} not found")
    return cam


def _get_image_bytes(cam_id, image_type, quality):
    """Helper to fetch and encode image"""
    shared_state = app.config.get("shared_state")
    if not shared_state: return None

    cameras = shared_state.get("cameras", {})
    cam = cameras.get(str(cam_id))
    img = None

    if cam:
        if image_type == 'live':
            latest = cam.get("latest_frame_data")
            if latest and len(latest) >= 2 and latest[0] is True:
                img = latest[1]
            else:
                # Handle disconnection status in image
                state = cam.get('fusion_state', 'UNKNOWN')
                if state == 'DISCONNECTED':
                    img = generate_placeholder_image("DISCONNECTED", (0, 0, 100))  # Red
                elif state == 'CONNECTING...':
                    img = generate_placeholder_image("CONNECTING...", (100, 100, 0))  # Teal
                else:
                    img = generate_placeholder_image("WAIT...", (30, 30, 30))
        elif image_type == 'fused':
            img = cam.get("fused_result")
            if img is None:
                img = generate_placeholder_image("NO FUSED RESULT")

    if img is None:
        img = generate_placeholder_image("NOT FOUND")

    ret, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if ret: return buffer.tobytes()
    return None


def gen_stream_frames(cam_id, image_type, quality=80):
    """Generator for MJPEG stream."""
    while True:
        frame_bytes = _get_image_bytes(cam_id, image_type, quality)
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.05 if image_type == 'live' else 0.5)


@app.route("/")
def index():
    shared_state = app.config.get("shared_state")
    if not shared_state: abort(500, description="System not ready.")
    cameras = (shared_state.get("cameras") or {})

    def _to_int(x: str) -> int:
        try:
            return int(x)
        except ValueError:
            return 0

    camera_ids = sorted(cameras.keys(), key=_to_int)

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Fusion Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #121212; color: #e0e0e0; }
            h1 { text-align: center; color: #fff; margin-bottom: 20px; }

            button { cursor: pointer; border: none; border-radius: 4px; font-weight: bold; transition: 0.2s; font-size: 0.9rem; }
            button.capture-btn { background: #28a745; color: white; font-size: 1.1rem; padding: 10px 20px; }
            button.capture-btn:hover { background: #218838; }
            button.cam-capture-btn { background: #007bff; color: white; padding: 6px 12px; }
            button.cam-capture-btn:hover { background: #0056b3; }
            button.cam-pause-btn { background: #dc3545; color: white; padding: 6px 12px; margin-left: 5px; }
            button.cam-pause-btn:hover { background: #bd2130; }
            button.cam-play-btn { background: #28a745; color: white; padding: 6px 12px; margin-left: 5px; }
            button.cam-play-btn:hover { background: #1e7e34; }
            button.static-btn { background: #444; color: #ccc; font-size: 0.8rem; padding: 5px 10px; }
            button.static-btn:hover { background: #666; color: white; }
            .grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 20px; }
            .cam-card { background: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 15px; width: fit-content; min-width: 400px; }
            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
                padding-bottom: 8px;
                border-bottom: 1px solid #333;
            }
            .card-header h2 { margin: 0; font-size: 1.4rem; color: #fff; }
            .status-wrapper { font-size: 0.9rem; color: #aaa; display: flex; align-items: center; }
            .status-text { font-weight: bold; margin-left: 5px; }
            .screens { display: flex; gap: 15px; }
            .screen-col { display: flex; flex-direction: column; align-items: center; }
            .screen-label { font-size: 0.8rem; color: #888; margin-bottom: 4px; width: 100%; text-align: left; }
            img { display: block; background: #000; border: 1px solid #444; max-width: 360px; height: auto; min-height: 270px; }
            .footer-controls { margin-top: 10px; display: flex; justify-content: space-between; }
        </style>
        <script>
            function setApi(k, v) { fetch(`/api/set?k=${k}&v=${v}`).catch(console.error); }
            function captureAll(ids) { ids.forEach(id => setApi(`cameras/${id}/fusion_state`, 'REQUESTED')); }

            function toggleStream(cid) {
                const btn = document.getElementById(`btn-toggle-${cid}`);
                const liveImg = document.getElementById(`img-live-${cid}`);
                const fusedImg = document.getElementById(`img-fused-${cid}`);

                const isPlaying = btn.getAttribute('data-state') === 'playing';

                if (isPlaying) {
                    const placeholder = `/api/static_placeholder?text=PAUSED`;
                    liveImg.src = placeholder;
                    fusedImg.src = placeholder;

                    btn.innerText = "Play";
                    btn.className = "cam-play-btn";
                    btn.setAttribute('data-state', 'paused');
                } else {
                    const t = new Date().getTime();
                    liveImg.src = `/api/sockets/image/${cid}?t=${t}`;
                    fusedImg.src = `/api/sockets/fused_image/${cid}?t=${t}`;

                    btn.innerText = "Pause";
                    btn.className = "cam-pause-btn";
                    btn.setAttribute('data-state', 'playing');
                }
            }

            // --- SSE STATUS UPDATER ---
            function initStatusUpdates() {
                const evtSource = new EventSource("/api/sockets/status");

                evtSource.onmessage = function(event) {
                    const data = JSON.parse(event.data);

                    for (const [id, state] of Object.entries(data)) {
                        const el = document.getElementById(`status-${id}`);
                        if(el) {
                            el.innerText = state;
                            if(state === 'READY') el.style.color = '#28a745';
                            else if(state === 'DISCONNECTED') el.style.color = '#dc3545';
                            else if(state === 'PROCESSING' || state === 'REQUESTED') el.style.color = '#ffc107';
                            else el.style.color = '#17a2b8';
                        }
                    }
                };

                evtSource.onerror = function() {
                    console.error("SSE Error (Normal if page reloads).");
                };
            }

            window.onload = initStatusUpdates;
        </script>
    </head>
    <body>
        <h1>Exposure Fusion Dashboard</h1>
        <div style="text-align:center;">
            <button class="capture-btn" onclick='captureAll({{ camera_ids | tojson }})'>CAPTURE ALL</button>
        </div>

        <div class="grid">
            {% for cid in camera_ids %}
            <div class="cam-card">
                <div class="card-header">
                    <h2>CAMERA {{ cid }}</h2>
                    <div class="status-wrapper">
                        Status: <span id="status-{{ cid }}" class="status-text">...</span>
                    </div>
                    <div>
                        <button class="cam-capture-btn" onclick="setApi('cameras/{{ cid }}/fusion_state', 'REQUESTED')">Capture</button>
                        <button id="btn-toggle-{{ cid }}" class="cam-pause-btn" data-state="playing" onclick="toggleStream('{{ cid }}')">Pause</button>
                    </div>
                </div>

                <div class="screens">
                    <div class="screen-col">
                        <span class="screen-label">LIVE PREVIEW</span>
                        <img id="img-live-{{ cid }}" src="/api/sockets/image/{{ cid }}" alt="Live">
                    </div>
                    <div class="screen-col">
                        <span class="screen-label">FUSED RESULT</span>
                        <img id="img-fused-{{ cid }}" src="/api/sockets/fused_image/{{ cid }}" alt="Fused">
                    </div>
                </div>

                <div class="footer-controls">
                    <a href="/api/image/{{ cid }}" target="_blank"><button class="static-btn">Download Live (HQ)</button></a>
                    <a href="/api/fused_image/{{ cid }}" target="_blank"><button class="static-btn">Download Fused (HQ)</button></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, camera_ids=camera_ids)


@app.route('/api/static_placeholder')
def api_static_placeholder():
    """Returns a single static JPEG for 'PAUSED' state."""
    text = request.args.get("text", "PAUSED")
    img = generate_placeholder_image(text, (20, 20, 20))  # Dark Gray
    ret, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/api/image/<cam_id>')
def api_image(cam_id):
    """Get single static live frame at 100% quality"""
    data = _get_image_bytes(cam_id, 'live', quality=100)
    if not data: abort(404)
    return Response(data, mimetype='image/jpeg')


@app.route('/api/fused_image/<cam_id>')
def api_fused_image(cam_id):
    """Get single static fused result at 100% quality"""
    data = _get_image_bytes(cam_id, 'fused', quality=100)
    if not data: abort(404)
    return Response(data, mimetype='image/jpeg')


@app.route('/api/sockets/image/<cam_id>')
def api_sockets_image(cam_id):
    """MJPEG Stream of live feed at 80% quality"""
    return Response(gen_stream_frames(cam_id, 'live', quality=80),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/sockets/fused_image/<cam_id>')
def api_sockets_fused_image(cam_id):
    """MJPEG Stream of fused result at 80% quality"""
    return Response(gen_stream_frames(cam_id, 'fused', quality=80),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/api/status")
def api_status():
    """Get Status for External Python API (JSON)"""
    shared_state = app.config.get("shared_state")
    if not shared_state: return jsonify({})
    cameras = shared_state.get("cameras", {})
    status_map = {k: v.get('fusion_state', 'UNKNOWN') for k, v in cameras.items()}
    return jsonify(status_map)


@app.route("/api/sockets/status")
def api_sockets_status():
    """SSE Status stream for Dashboard (Push updates)"""
    shared_state = app.config.get("shared_state")
    if not shared_state: return abort(500)

    def event_stream():
        cameras = shared_state.get("cameras", {})
        old_status = None
        while True:
            current_status = {k: v.get('fusion_state', 'UNKNOWN') for k, v in cameras.items()}
            if current_status != old_status:
                yield f"data: {json.dumps(current_status)}\n\n"
                old_status = current_status
            time.sleep(0.5)  # Check every 0.5s

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/set", methods=["GET"])
def set_data():
    """Set data in shared_state"""
    shared_state = app.config.get("shared_state")
    if shared_state is None: abort(500)
    k, v, sep = request.args.get("k"), request.args.get("v"), request.args.get("sep", "/")
    if not k or v is None: abort(400)

    val = _parse_value(v)
    parts = [p for p in k.split(sep) if p]
    target_key = parts[-1]

    try:
        parent = shared_state
        if len(parts) > 1: parent = resolve_path(shared_state, sep.join(parts[:-1]), sep)

        if isinstance(parent, dict):
            parent[target_key] = val
        elif isinstance(parent, list):
            parent[int(target_key)] = val
        else:
            abort(400)
        return jsonify({"success": True, "k": k, "v": val})
    except Exception as e:
        abort(400, description=str(e))


@app.route("/api/get", methods=["GET"])
def get_data():
    """Get data from shared_state"""
    shared_state = app.config.get("shared_state")
    if shared_state is None: abort(500)
    k, sep = request.args.get("k"), request.args.get("sep", "/")
    if not k: abort(400)

    try:
        val = resolve_path(shared_state, k, sep)
        return jsonify({"k": k, "v": sanitize_value(val)})
    except Exception as e:
        abort(404, description=str(e))


def run_server(shared_state: dict) -> None:
    app.config["shared_state"] = shared_state
    host = shared_state.get('ipv4', '0.0.0.0')
    port = shared_state.get('port', 5000)
    app.run(host=host, port=port, debug=False, threaded=True, use_reloader=False)


def run(shared_state: Optional[dict] = None):
    if shared_state is None:
        shared_state = {
            'is_running': True,
            'ipv4': '0.0.0.0',
            'port': 2002,
            'cameras': {
                '0': {
                    'is_running': True,
                    'start_setting': [
                        (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75),
                        (cv2.CAP_PROP_FRAME_WIDTH, 1024),
                        (cv2.CAP_PROP_FRAME_HEIGHT, 768)
                    ],
                    'fused_setting': {
                        'capture_setting': [
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -5)],
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -9)],
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -10)]
                        ],
                        'after_that': [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)]
                    },
                    'latest_frame_data': (None, None),
                    'fused_result': None,
                    'fusion_state': 'IDLE'
                },
                '2': {
                    'is_running': True,
                    'start_setting': [
                        (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75),
                        (cv2.CAP_PROP_FRAME_WIDTH, 1024),
                        (cv2.CAP_PROP_FRAME_HEIGHT, 768)
                    ],
                    'fused_setting': {
                        'capture_setting': [
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -2)],
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -5)],
                            [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -8)]
                        ],
                        'after_that': [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)]
                    },
                    'latest_frame_data': (None, None),
                    'fused_result': None,
                    'fusion_state': 'IDLE'
                }
            }
        }

    threads = []
    print("--- SYSTEM STARTING ---")
    t_server = threading.Thread(target=run_server, args=(shared_state,))
    t_server.start()
    threads.append(t_server)

    print("Starting Camera Workers...")
    for cam_id in shared_state['cameras']:
        t_cam = threading.Thread(target=single_camera_worker, args=(shared_state, cam_id))
        t_cam.start()
        threads.append(t_cam)

    print(f"Server available at http://localhost:{shared_state['port']}")
    print("Press CTRL+C to stop.")

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        shared_state['is_running'] = False
        for t in threads: t.join()
        print("Shutdown Complete.")


if __name__ == "__main__":
    run()
