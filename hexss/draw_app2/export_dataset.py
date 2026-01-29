import threading
import random
import time
import cv2
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from hexss import json_update
from media_dataset import MediaDataset

# --- Configuration ---
DEFAULT_SOURCE_DIR = Path('media_source')


def get_media_list(data_dir: Path):
    items = []
    if not data_dir.exists():
        return items

    for path in data_dir.glob('*'):
        if path.is_dir():
            if '_detections' in path.name:
                continue
            items.append(path.name)

        if path.is_file():
            if path.suffix.lower() in ['.mp4', '.avi', '.mkv', '.mov']:
                items.append(path.name)
    return sorted(items)


def convert_to_detection_datasets(input_paths, output_path: Path, valid_ratio=0.2, workers=4, progress_data=None):
    output_path = Path(output_path)
    global_names = []
    names_lock = threading.Lock()
    cnt_lock = threading.Lock()

    def update_status(msg=None, percent=None, status=None):
        if progress_data:
            if msg is not None:
                progress_data['result']['message'] = msg
            if percent is not None:
                progress_data['result']['percent'] = round(percent, 2)
            if status is not None:
                progress_data['status'] = status

    def is_stopped():
        return progress_data and progress_data.get('status') == 'stopped'

    update_status("Scanning sources...", 0, "running")
    sources = []
    total_frames = 0

    for p in input_paths:
        if is_stopped(): return  # Early exit

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
        if not is_stopped():
            update_status("No frames found", 0, "error")
        return

    update_status(f"Processing {total_frames} frames...", 0)
    processed_count = 0

    def process_source(source_info):
        nonlocal processed_count
        src_path, keys = source_info

        if is_stopped(): return

        ds = MediaDataset(src_path)
        prefix = "_".join(src_path.parts[-2:])

        for frame_key in keys:
            if is_stopped():
                break

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
                        fname = f"{prefix}_{frame_key}"  # Underscore is safer than space

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
                if is_stopped(): break
                f.result()
    except Exception as e:
        update_status(f"Error during processing: {e}", None, "error")
        return

    if is_stopped():
        update_status("Export Stopped by User", None, "stopped")
        return

    update_status("Saving config...", 99)
    output_path.mkdir(parents=True, exist_ok=True)
    json_update(output_path / 'config.json', {"names": global_names})
    update_status("Export Completed", 100, "completed")


def export(data):
    export_dataset = data['export_dataset']
    params = export_dataset['parameters']

    # Resolve Input Paths
    input_list = []

    if params.get('all', False):
        # Scan the default directory for all valid media
        media_names = get_media_list(DEFAULT_SOURCE_DIR)
        input_list = [DEFAULT_SOURCE_DIR / name for name in media_names]
    else:
        # Use the specific single file/folder provided
        p = params.get('input_path')
        if p:
            input_list = [DEFAULT_SOURCE_DIR / p]

    if not input_list:
        export_dataset['status'] = 'error'
        export_dataset['result']['message'] = 'No input paths found'
        return

    try:
        convert_to_detection_datasets(
            input_list,  # Pass list directly
            output_path=params['output_path'],
            valid_ratio=params.get('valid_ratio', 0.2),
            workers=params.get('workers', 4),
            progress_data=export_dataset
        )
    except Exception as e:
        export_dataset['status'] = 'error'
        export_dataset['result']['message'] = str(e)


def start(data):
    if data['export_dataset']['status'] == 'running':
        print("Job already running.")
        return

    # Reset State
    data['export_dataset']['status'] = 'idle'
    data['export_dataset']['result']['percent'] = 0
    data['export_dataset']['result']['message'] = 'Starting...'

    # Start Thread
    t = threading.Thread(target=export, args=(data,))
    data['export_dataset']['threading'] = t
    t.start()


def stop(data):
    if data['export_dataset']['status'] == 'running':
        data['export_dataset']['status'] = 'stopped'
        print("\nStopping command sent...")


def show(data):
    try:
        while True:
            time.sleep(0.5)
            status = data['export_dataset']['status']
            result = data['export_dataset']['result']

            bar_len = 20
            filled = int(result['percent'] / 100 * bar_len)
            bar = '█' * filled + '-' * (bar_len - filled)

            print(f"\r[{bar}] {result['percent']:5.1f}% | Status: {status:10s} | {result['message']}", end='')

            if status in ['completed', 'error', 'stopped']:
                print(f"\nProcess finished with status: {status}")
                break
    except KeyboardInterrupt:
        stop(data)


if __name__ == '__main__':
    data = {
        'export_dataset': {
            'status': 'idle',
            'threading': None,
            'parameters': {
                'output_path': 'export_result',
                'all': False,
                'input_path': 'video01.mp4',
                'valid_ratio': 0.2,
                'workers': 8
            },
            'result': {
                'percent': 0,
                'message': 'Waiting to start'
            }
        }
    }

    data['export_dataset']['parameters']['all'] = True
    data['export_dataset']['parameters']['output_path'] = 'export_result'

    start(data)
    show(data)