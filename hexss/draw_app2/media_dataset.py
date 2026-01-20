import random
from typing import Dict, List, Any, Optional
from pathlib import Path

import cv2

from hexss.box import Box
from hexss.json import json_load, json_update, json_remove, json_rename


class MediaDataset:
    def __init__(self, source_path: Path | str) -> None:
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise FileNotFoundError(f"Path does not exist: {self.source_path}")

        self.is_dir = self.source_path.is_dir()
        self.annotation_path = self.source_path.with_suffix('.json')
        self.annotations = json_load(self.annotation_path, default={})
        self.detection_dir = self.source_path.parent / (self.source_path.name + "_detections")

        self.cap: Optional[cv2.VideoCapture] = None
        if not self.is_dir:
            self.cap = cv2.VideoCapture(str(self.source_path))
            if not self.cap.isOpened():
                raise ValueError(f"Failed to open video file: {self.source_path}")

        self.frame = None

    def get_frame_keys(self) -> List[str]:
        if self.is_dir:
            return sorted([p.name for p in self.source_path.glob('*.png')])
        else:
            if self.cap is None: return []
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            return [str(i) for i in range(frame_count)]

    def read_frame(self, frame_key: str) -> cv2.Mat:
        if self.is_dir:
            img_path = self.source_path / frame_key
            self.frame = cv2.imread(str(img_path))
        else:
            if self.cap is None:
                raise RuntimeError("Video capture is not initialized")
            frame_idx = int(frame_key)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame

        return self.frame

    def get_annotation(self, frame_key: str) -> Dict[str, Any]:
        data = self.annotations.get(frame_key, {}).copy()
        det_file = self.detection_dir / f"{frame_key}.json"
        if det_file.exists():
            try:
                det_data = json_load(det_file)
                data['detections'] = det_data
            except Exception as e:
                print(f"Error loading detection for {frame_key}: {e}")
        return data

    def set(self, k, v):
        self.annotations = json_update(self.annotation_path, {k: v}, deep="/")

    def update_box(self, frame_key: str, box_id: str, xywhn: list | tuple,
                   detection_label=None, classification_label=None):
        new_data = {f"{frame_key}/boxes/{box_id}/xywhn": xywhn}
        if detection_label:
            new_data[f"{frame_key}/boxes/{box_id}/detection/label"] = detection_label
        if classification_label:
            new_data[f"{frame_key}/boxes/{box_id}/classification/label"] = classification_label
        self.annotations = json_update(self.annotation_path, new_data, deep="/")

    def set_classification_label(self, frame_key: str, box_id: str, label):
        self.set(f"{frame_key}/boxes/{box_id}/classification/label", label)

    def set_detection_label(self, frame_key: str, box_id: str, label):
        self.set(f"{frame_key}/boxes/{box_id}/detection/label", label)

    def rename_box(self, frame_key: str, box_id: str, new_box_id: str):
        self.annotations = json_rename(
            self.annotation_path,
            f'{frame_key}/boxes/{box_id}',
            f'{frame_key}/boxes/{new_box_id}', deep="/"
        )

    def remove_box(self, frame_key: str, box_id: str):
        self.annotations = json_remove(self.annotation_path, f"{frame_key}/boxes/{box_id}", deep="/")

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def convert_to_detection_dataset(self, output_path: Path | str, valid=0.2, progress_callback=None):
        output_path = Path(output_path)
        config = json_load(output_path / 'config.json', {
            "names": []
        })
        names = config["names"]

        frame_keys = self.get_frame_keys()
        total_frames = len(frame_keys)

        for idx, frame_key in enumerate(frame_keys):
            if progress_callback:
                progress_callback(idx, total_frames)

            frame_data = self.get_annotation(frame_key)
            if not frame_data:
                continue
            img = self.read_frame(frame_key)
            boxes_data = frame_data.get('boxes')

            folder = 'valid' if random.random() <= valid else 'train'
            comp = list(self.source_path.parts)[-2:]
            img_path = output_path / 'datasets' / folder / 'images' / f'{'_'.join(comp)} {frame_key}.png'
            txt_path = output_path / 'datasets' / folder / 'labels' / f'{'_'.join(comp)} {frame_key}.txt'
            txt = ''

            if boxes_data:
                for box_id, box_info in boxes_data.items():
                    label = box_info.get('detection', {}).get('label')
                    if label not in names:
                        names.append(label)
                    if label:
                        names.index(label)
                        txt += f"{names.index(label)} {' '.join(map(str, box_info['xywhn']))}\n"

            if txt:
                img_path.parent.mkdir(parents=True, exist_ok=True)
                txt_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(img_path), img)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(txt)

        json_update(output_path / 'config.json', {"names": names})

        if progress_callback:
            progress_callback(total_frames, total_frames)

        train_path = output_path / 'train.py'
        if train_path.exists():
            return
        text = rf'''import hexss

hexss.check_packages('PyYAML', 'ultralytics', auto_install=True)

from pathlib import Path
import yaml
from ultralytics import YOLO

path = Path(hexss.path.get_script_dir())
model_name = 'm1-'
names = {names}
epochs = 200
imgsz = 640
device = 'cpu'
device_name = None

try:
    import torch

    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        device = 0
except:
    ...

if __name__ == '__main__':
    print(f"✅ GPU Detected: {{device_name}}")
    yaml_path = Path("temp_data.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump({{
            'path': str(path / 'datasets'),
            'train': 'train/images',
            'val': 'valid/images',
            'nc': len(names),
            'names': names
        }}, f)

    # Load model and train
    # model = YOLO("yolo12n.yaml")
    # model = YOLO("yolo12s.yaml")
    model = YOLO("yolo11m.pt")

    # model = YOLO("yolo12m-seg.yaml")

    results = model.train(
        data=str(yaml_path),
        epochs=epochs,
        imgsz=imgsz,
        device=device,
        project=str(Path(path) / "model"),
        name=model_name
    )

    if yaml_path.exists():
        yaml_path.unlink()

    print("✅ Training Completed Successfully.")
'''

        train_path.parent.mkdir(parents=True, exist_ok=True)
        train_path.write_text(text, encoding='utf-8')

    def __del__(self):
        self.release()


if __name__ == '__main__':
    from ultralytics import YOLO
    from hexss.env import set_proxy

    set_proxy()

    model = YOLO("export_result/model/m1-/weights/best.pt")
    yolo_classes = list(model.names.values())
    print(yolo_classes)
    classes_ids = [yolo_classes.index(clas) for clas in yolo_classes]

    # example
    # path = Path('data01/img01')
    path = Path('data01/video01.mp4')

    dataset = MediaDataset(path)
    # dataset.convert_to_detection_dataset('model training 1')

    print(f"Annotation Path: {dataset.annotation_path}")

    frame_keys = dataset.get_frame_keys()
    print(f"Total Frames: {len(frame_keys)}")
    for frame_key in frame_keys:
        frame_data = dataset.get_annotation(frame_key)
        # if not frame_data:
        #     continue
        print(f"Frame Key: {frame_key}")
        img = dataset.read_frame(frame_key)
        boxes_data = frame_data.get('boxes')

        if boxes_data:
            for box_id, box_info in boxes_data.items():
                # dataset.set(f"{frame_key}/boxes/{box_id}/detection/label", "a1")
                label = box_info.get('detection', {}).get('label')
                box = Box(xywhn=box_info['xywhn'], size=img.shape[1::-1])
                p1 = box.x1y1.astype(int)
                p2 = box.x2y2.astype(int)
                cv2.rectangle(img, p1, p2, (0, 0, 255), 2)

                if label:
                    cv2.putText(img, str(label), (p1[0], p1[1] - 10),
                                0, 0.5, (0, 0, 255), 1)

        results = model.predict(img, conf=0.5, verbose=False, device=0)
        result = results[0]
        for box in result.boxes:
            print(box)
            color_number = classes_ids.index(int(box.cls[0]))
            x1, y1, x2, y2 = box.xyxy[0]
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

        cv2.imshow('img', cv2.resize(img, None, fx=0.5, fy=0.5))
        key = cv2.waitKey(0) & 0xFF
        # if key == ord('q'):
        #     break
        # if key == ord('a'):
        #     print(boxes_data.keys())
        #     box_id = list(boxes_data.keys())[0]
        #     box_info = boxes_data[box_id]
        #     xn, yn, wn, hn = box_info['xywhn']
        #     xn = 1.1 * xn
        #     dataset.update_box(frame_key, box_id, [xn, yn, wn, hn], detection_label='a', classification_label='b')

#
#                 )
