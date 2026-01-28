import json
import re
import subprocess
import time
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from pprint import pprint

import cv2
import numpy as np
from flask import Flask, jsonify, request, Response, render_template

import hexss.path
from hexss.json import json_load, json_update
from hexss.draw_app2.media_dataset import MediaDataset

from hexss.env import set_proxy

set_proxy()

app = Flask(__name__)


def get_media_list(data_dir: Path):
    items = []
    if not data_dir.exists(): return items
    for path in data_dir.glob('*'):
        if path.is_dir():
            if '_detections' in path.name: continue
            items.append(path.name)
        if path.is_file():
            if path.suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov']:
                items.append(path.name)
    return sorted(items)


def convert_to_detection_datasets(data_store, input_paths):
    export_dataset = data_store['export_dataset']
    parameters = export_dataset['parameters']
    valid_ratio = parameters['valid_ratio']
    workers = parameters['workers']

    output_path = Path('YOLO_detect') / parameters['folder_name']
    global_names = []
    names_lock = threading.Lock()
    cnt_lock = threading.Lock()

    def update_status(msg=None, percent=None, status=None):
        if msg is not None:
            export_dataset['result']['message'] = msg
        if percent is not None:
            export_dataset['result']['percent'] = round(percent, 2)
        if status is not None:
            export_dataset['status'] = status

    update_status("Scanning sources...", 0, "running")
    sources = []
    total_frames = 0

    for p in input_paths:
        if export_dataset['status'] == 'stopped':
            return

        p = Path(p)
        if not p.exists():
            print(f"Warning: Source not found {p}")
            continue
        try:
            ds = MediaDataset(p)
            keys = ds.get_frame_keys()
            if keys:
                sources.append((p, keys))
                total_frames += len(keys)
            ds.release()
        except Exception as e:
            print(f"Error scanning {p}: {e}")

    if total_frames == 0:
        if export_dataset['status'] != 'stopped':
            update_status("No frames found", 0, "error")
        return

    update_status(f"Processing {total_frames} frames...", 0)
    processed_count = 0

    def process_source(source_info):
        nonlocal processed_count
        src_path, keys = source_info

        ds = MediaDataset(src_path)
        prefix = "_".join(src_path.parts[-2:])

        for frame_key in keys:
            if export_dataset['status'] == 'stopped':
                return

            try:
                frame_data = ds.get_annotation(frame_key)
                boxes = frame_data.get('boxes', {})
                if not boxes:
                    with cnt_lock:
                        processed_count += 1
                        pct = (processed_count / total_frames) * 100
                        update_status(None, pct)
                    continue

                valid_entries = []
                for box_id, box_info in boxes.items():
                    label = box_info.get('detection', {}).get('label')
                    xywhn = box_info.get('xywhn')

                    if label and xywhn:
                        with names_lock:
                            if label not in global_names:
                                global_names.append(label)
                            cls_idx = global_names.index(label)
                        valid_entries.append(f"{cls_idx} {' '.join(map(str, xywhn))}")

                if valid_entries:
                    img = ds.read_frame(frame_key)
                    if img is not None:
                        subset = 'valid' if random.random() <= valid_ratio else 'train'
                        fname = f"{prefix}_{frame_key}"

                        img_dir = output_path / 'datasets' / subset / 'images'
                        lbl_dir = output_path / 'datasets' / subset / 'labels'

                        img_dir.mkdir(parents=True, exist_ok=True)
                        lbl_dir.mkdir(parents=True, exist_ok=True)

                        cv2.imwrite(str(img_dir / f"{fname}.png"), img)
                        with open(lbl_dir / f"{fname}.txt", 'w', encoding='utf-8') as f:
                            f.write('\n'.join(valid_entries))

            except Exception as e:
                print(f"Frame error {frame_key}: {e}")
            finally:
                with cnt_lock:
                    processed_count += 1
                    pct = (processed_count / total_frames) * 100
                    update_status(None, pct)

        ds.release()

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_source, s) for s in sources]
            for f in futures:
                f.result()
    except Exception as e:
        update_status(f"Error during processing: {e}", None, "error")
        return

    if export_dataset['status'] == 'stopped':
        update_status("Export Stopped by User", None, "stopped")
        return

    update_status("Saving config...", 99)
    output_path.mkdir(parents=True, exist_ok=True)
    json_update(output_path / 'config.json', {"names": global_names})
    update_status("Export Completed", 100, "completed")


def export_task(data_store):
    export_data = data_store['export_dataset']
    params = export_data['parameters']
    media_dir = data_store['media_dir']

    try:
        input_list = []
        if params.get('all', False):
            media_names = get_media_list(media_dir)
            input_list = [media_dir / name for name in media_names]
        else:
            p = params.get('input_path')
            if p:
                input_list = [media_dir / p]

        if not input_list:
            raise ValueError("No media found for export.")

        convert_to_detection_datasets(data_store, input_list)

        if export_data['status'] != 'stopped':
            export_data['status'] = 'completed'
            export_data['result']['percent'] = 100
            export_data['result']['message'] = 'Export Completed Successfully'

    except Exception as e:
        print(f"Export Error: {e}")
        export_data['status'] = 'error'
        export_data['result']['message'] = str(e)
    finally:
        export_data['threading'] = None


def train_task(data_store):
    training = data_store['training']
    params = training['parameters']
    training['result'] = {
        'current_epoch': 0,
        'total_epochs': 0,
        'epoch_percent': 0,
        'remaining': {'hours': 0, 'minutes': 0, 'seconds': 0},
        'percent': 0,
        'message': '...'
    }
    folder_name = params['folder_name']
    base_dir = hexss.path.get_current_working_dir() / 'YOLO_detect'
    dataset_dir = base_dir / folder_name / 'datasets'
    yaml_path = base_dir / "temp_data.yaml"
    names = json_load(base_dir / folder_name / 'config.json')['names']

    yaml_content = f"""
    path: {dataset_dir.as_posix()}
    train: train/images
    val: valid/images
    nc: {len(names)}
    names: {names}
    """

    try:
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)
    except Exception as e:
        training['result']['status'] = 'error'
        training['result']['message'] = f"Config Error: {e}"
        return

    config = json_load('YOLO_detect/config.json', {
        '1': {'value': "detect", 'option': ["detect"]},
        '2': {'value': "train", 'option': ["train"]},
        'model': {'value': "yolo11m.pt",
                  'option': ["yolo11n.pt", "yolo11m.pt", "yolo11l.pt", "yolo11x.pt"]},
        'epochs': {'value': 100},
        'imgsz': {'value': 640}
    })
    cmd = [
        'yolo',
        config['1']['value'],
        config['2']['value'],
        f"model={config['model']['value']}",
        f'data={yaml_path.name}',
        f'epochs={config["epochs"]["value"]}',
        f'imgsz={config["imgsz"]["value"]}',
        f'project={base_dir / folder_name / "model"}',
    ]
    print(f"cmd = {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding='utf-8',
        cwd=str(base_dir)
    )
    training['process'] = process
    training['result']['status'] = 'running'
    training['result']['message'] = 'Training started...'

    progress_pattern = re.compile(r"(\d+)/(\d+)\s+.*?\s+(\d+)%")
    start_time = time.time()
    old = ''
    for line in iter(process.stdout.readline, ''):
        if old[:15] == line[:15]:
            print(end=f'\r{old.strip()}\n')
        print(end=f'\r{line.strip()}')
        old = line

        if not line: break
        if training['result']['status'] == 'stopped':
            break

        training['result']['message'] = f'{line.strip()}'

        match = progress_pattern.search(line)
        if match:
            current_epoch = int(match.group(1))
            total_epochs = int(match.group(2))
            epoch_percent = int(match.group(3))

            total_progress_ratio = (current_epoch - 1 + (epoch_percent / 100.0)) / total_epochs
            elapsed_time = time.time() - start_time
            h, m, s = 0, 0, 0
            if total_progress_ratio > 0.001:
                estimated_total = elapsed_time / total_progress_ratio
                remaining = estimated_total - elapsed_time
                m, s = divmod(remaining, 60)
                h, m = divmod(m, 60)

            training['result']['current_epoch'] = current_epoch
            training['result']['total_epochs'] = total_epochs
            training['result']['epoch_percent'] = epoch_percent
            training['result']['remaining'] = {'hours': int(h), 'minutes': int(m), 'seconds': int(s)}
            training['result']['percent'] = int(total_progress_ratio * 100)

        # elif 'Results saved to ' in line:
        #     training['result']['status'] = 'completed'
        #     break
        # elif 'Results saved to ' in line:
        #     break
    print('train_task end')
    training['status'] = 'completed',  # idle, running, completed, error, stopped


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/get_media_list')
def api_get_media_list():
    data: dict = app.config['data']
    media_dir: Path = data['media_dir']
    return jsonify(get_media_list(media_dir))


@app.route('/api/set_media')
def api_set_media():
    data: dict = app.config['data']
    media_dir: Path = data['media_dir']
    source = request.args.get('source')
    if data.get('media'):
        try:
            data['media'].release()
        except Exception as e:
            print(f"Error releasing old media: {e}")
    try:
        data['media'] = MediaDataset(media_dir / source)
        return jsonify({
            'status': 'success',
            'source': data['media'].source_path.name
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/get_frame_keys')
def api_get_frame_keys():
    data: dict = app.config['data']
    media: MediaDataset = data['media']

    if media is None:
        return jsonify({'frame_keys': []})

    return jsonify({
        'source': media.source_path.name,
        'frame_keys': media.get_frame_keys()
    })


@app.route('/api/update_frame')
def api_update_frame():
    """
    /api/update_frame?frame_key=${frameKey}
    """
    data: dict = app.config['data']
    media: MediaDataset = data.get('media')

    if media is None:
        return jsonify({
            'status': 'error',
            'message': 'Media not initialized or server restarted'
        }), 400

    frame_key = request.args.get('frame_key')

    try:
        media.read_frame(frame_key)
        return jsonify({
            'status': 'success',
            'frame_key': frame_key,
            'annotation': media.get_annotation(frame_key)
        })
    except Exception as e:
        print(f"Frame Read Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/get_image')
def api_get_image():
    """
    API: ส่งรูปภาพ Jpeg ของเฟรมปัจจุบัน
    """
    data: dict = app.config['data']
    media: MediaDataset = data['media']

    if media is None or not hasattr(media, 'frame') or media.frame is None:
        blank = np.zeros((100, 100, 3), np.uint8)
        ret, buffer = cv2.imencode('.jpg', blank)
    else:
        ret, buffer = cv2.imencode('.jpg', media.frame)

    return Response(buffer.tobytes(), mimetype='image/jpeg')


@app.route('/api/update_box', methods=['POST'])
def api_update_box():
    data_store: dict = app.config['data']
    media: MediaDataset = data_store['media']

    req = request.json
    frame_key = req.get('frame_key')
    box_id = req.get('box_id')
    xywhn = req.get('xywhn')
    detection_label = req.get('detection_label')

    if not all([frame_key, box_id, xywhn]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        xywhn = [float(x) for x in xywhn]
        media.update_box(frame_key, box_id, xywhn, detection_label=detection_label)

        return jsonify({
            'status': 'success',
            'box_id': box_id,
            'xywhn': xywhn,
            'detection_label': detection_label
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rename_box', methods=['POST'])
def api_rename_box():
    data_store: dict = app.config['data']
    media: MediaDataset = data_store['media']

    req = request.json
    frame_key = req.get('frame_key')
    box_id = req.get('box_id')
    new_box_id = req.get('new_box_id')

    if not all([frame_key, box_id, new_box_id]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        media.rename_box(frame_key, box_id, new_box_id)
        return jsonify({
            'status': 'success',
            'frame_key': frame_key,
            'box_id': box_id,
            'new_box_id': new_box_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/remove_box', methods=['POST'])
def api_remove_box():
    data_store: dict = app.config['data']
    media: MediaDataset = data_store['media']

    req = request.json
    frame_key = req.get('frame_key')
    box_id = req.get('box_id')

    if not all([frame_key, box_id]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        media.remove_box(frame_key, box_id)
        return jsonify({
            'status': 'success',
            'frame_key': frame_key,
            'box_id': box_id
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load_detection_label')
def api_load_detection_label():
    data_store: dict = app.config['data']
    media_dir = data_store['media_dir']
    config = json_load(media_dir / 'config.json', {'detection': {'names': []}})
    new_label = request.args.get('new_label', None)
    if new_label is not None:
        if new_label not in config['detection']['names']:
            config['detection']['names'].append(new_label)
            json_update(media_dir / 'config.json', config)

    return jsonify({
        'status': 'success',
        'names': config['detection']['names'],
    })


##################### export_dataset ############################
@app.route('/api/detect/export_dataset/start', methods=['POST'])
def api_detect_export_dataset_start():
    data_store = app.config['data']
    export_dataset = data_store['export_dataset']
    media: MediaDataset = data_store['media']

    if export_dataset['status'] == 'running':
        if export_dataset['threading'] and export_dataset['threading'].is_alive():
            return jsonify({'status': 'error', 'message': 'Export in progress'})

    export_dataset['status'] = 'running'
    export_dataset['result'] = {
        'percent': 0,
        'message': 'Initializing...'
    }
    export_dataset['parameters'] = {
        'folder_name': request.json.get('folder_name'),
        'all': request.json.get('all', False),
        'input_path': media.source_path.name if media else None,
        'valid_ratio': 0.2,
        'workers': 4
    }
    t = threading.Thread(target=export_task, args=(data_store,))
    export_dataset['threading'] = t
    t.start()
    return jsonify({'status': 'success', 'message': 'Export started'})


@app.route('/api/detect/export_dataset/stop', methods=['POST'])
def api_detect_export_dataset_stop():
    data_store = app.config['data']
    export_dataset = data_store['export_dataset']

    if export_dataset['status'] == 'running':
        export_dataset['status'] = 'stopped'
        export_dataset['result']['message'] = 'Stopping...'
        return jsonify({'status': 'success', 'message': 'Stop signal sent'})

    return jsonify({'status': 'idle', 'message': 'Not running'})


@app.route('/api/detect/export_dataset/stream')
def api_detect_export_dataset_stream():
    data_store = app.config['data']
    export_dataset = data_store['export_dataset']

    def generate():
        last_dump = None
        while True:
            current_status = export_dataset['status']
            current_result = export_dataset['result']

            payload = {
                'status': current_status,
                'progress': current_result.get('percent', 0),
                'message': current_result.get('message', '')
            }

            current_dump = json.dumps(payload)

            if current_dump != last_dump:
                yield f"data: {current_dump}\n\n"
                last_dump = current_dump

            if current_status in ['completed', 'error', 'stopped']:
                yield f"data: {current_dump}\n\n"
                break

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


##################### training ############################
@app.route('/api/detect/training/start', methods=['POST'])
def api_detect_training_start():
    data_store = app.config['data']
    training = data_store['training']

    if training['status'] == 'running':
        if training['threading'] and training['threading'].is_alive():
            return jsonify({'status': 'error', 'message': 'Training is already in progress'})

    training['status'] = 'running'
    training['process'] = None
    training['result'] = {
        'current_epoch': 0,
        'total_epochs': 0,
        'epoch_percent': 0,
        'remaining': {'hours': 0, 'minutes': 0, 'seconds': 0},
        'percent': 0,
        'message': 'Initializing training...'
    }
    training['parameters'] = {
        'folder_name': request.json.get('folder_name'),
    }

    try:
        t = threading.Thread(target=train_task, args=(data_store,))
        training['threading'] = t
        t.start()
        return jsonify({'status': 'success', 'message': 'Training started successfully'})
    except Exception as e:
        training['status'] = 'error'
        training['result']['message'] = str(e)
        return jsonify({'status': 'error', 'message': f'Failed to start training: {e}'}), 500


@app.route('/api/detect/training/stop', methods=['POST'])
def api_detect_training_stop():
    data_store = app.config['data']
    training = data_store['training']

    if training['status'] == 'running':
        training['status'] = 'stopped'

        proc = training.get('process')
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception as e:
                print(f"Error terminating process: {e}")

        training['result']['message'] = 'Training stopped by user'
        return jsonify({'status': 'success', 'message': 'Stop signal sent'})

    return jsonify({'status': 'idle', 'message': 'Training is not running'})


@app.route('/api/detect/training/stream')
def api_detect_training_stream():
    data_store = app.config['data']
    training = data_store['training']

    def generate():
        last_dump = None
        while True:
            current_status = training.get('status', 'idle')
            current_result = training.get('result', {})

            payload = {
                'status': current_status,
                'progress': current_result.get('percent', 0),
                'epoch': current_result.get('current_epoch', 0),
                'total_epochs': current_result.get('total_epochs', 0),
                'remaining': current_result.get('remaining', {}),
                'message': current_result.get('message', '')
            }

            current_dump = json.dumps(payload)

            if current_dump != last_dump:
                yield f"data: {current_dump}\n\n"
                last_dump = current_dump

            if current_status in ['completed', 'error', 'stopped']:
                yield f"data: {current_dump}\n\n"
                break

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/detect/config', methods=['GET', 'POST'])
def api_detect_config():
    if request.method == 'POST':
        req_data = request.get_json()
        new = {}
        model = req_data.get('model')
        epochs = req_data.get('epochs')
        imgsz = req_data.get('imgsz')

        if model: new['model/value'] = model
        if epochs: new['epochs/value'] = epochs
        if imgsz: new['imgsz/value'] = imgsz

        if new:
            Path('YOLO_detect').mkdir(exist_ok=True)
            json_update('YOLO_detect/config.json', new, deep='/')

    config = json_load('YOLO_detect/config.json', {
        '1': {'value': "detect", 'option': ["detect"]},
        '2': {'value': "train", 'option': ["train"]},
        'model': {'value': "yolo11m.pt",
                  'option': ["yolo11n.pt", "yolo11m.pt", "yolo11l.pt", "yolo11x.pt"]},
        'epochs': {'value': 100},
        'imgsz': {'value': 640}
    })

    return jsonify({'status': 'success', 'config': config})


def run():
    from hexss.pyconfig import Config
    cfg = Config('config.py', '''
from pathlib import Path

ipv4 = '0.0.0.0'
port = 2003
open_browser = True
data_store = {
    'running': True,
    'open_browser': True,

    'media_dir': Path('media_source'),
    'media': None,

    'export_dataset': {
        'status': 'idle',  # idle, running, completed, error, stopped
        'threading': None,  # threading.Thread object
        'parameters': {
            'folder_name': 'export_result',
            'all': False,
            'input_path': '',
            'valid_ratio': 0.2,
            'workers': 8
        },
        'result': {  # JSON-serializable status
            'percent': 0,  # 0-100
            'message': ''
        }
    },

    'training': {
        'status': 'idle',  # idle, running, completed, error, stopped
        'threading': None,  # threading.Thread object
        'process': None,
        'parameters': {
            'folder_name': 'export_result',
        },
        'result': {  # JSON-serializable status
            'current_epoch': 0,
            'total_epochs': 0,
            'epoch_percent': 0,
            'remaining': {'hours': 0, 'minutes': 0, 'seconds': 0},
            'percent': 0,  # 0-100
            'message': ''
        }
    },
    'predict': {
        'threading': None,
        'result': None
    }
}
''')

    if cfg.open_browser is True:
        from hexss.network import open_url
        url = '127.0.0.1' if cfg.ipv4 == '0.0.0.0' else cfg.ipv4
        open_url(f'http://{url}:{cfg.port}')

    cfg.data_store['media_dir'].mkdir(parents=True, exist_ok=True)
    app.config['data'] = cfg.data_store

    pprint(cfg.data_store)
    app.run(host=cfg.ipv4, port=cfg.port, debug=True, use_reloader=False, threaded=True)


if __name__ == '__main__':
    run()
