from typing import Union
import hexss
from hexss.image import Image

hexss.check_packages(
    'ultralytics', 'numpy', 'opencv-python',
    auto_install=True
)

import numpy as np

class Detector:
    def __init__(self, model_path: str | None = None):
        from ultralytics import YOLO

        if model_path is None:
            self.model = YOLO()
        else:
            self.model = YOLO(model_path)
        self.class_names = None
        self.detections = []

    def detect(self, image: Union[Image, np.ndarray]) -> list[dict]:
        if isinstance(image, Image):
            arr = image.numpy()
        elif isinstance(image, np.ndarray):
            arr = image
        else:
            raise TypeError(
                f"Unsupported image type: {type(image)}. "
                "Provide an Image or NumPy array."
            )
        results = self.model(source=arr, verbose=False)[0]
        self.class_names = results.names

        class_counts = {}
        boxes = results.boxes
        self.detections = []
        for cls, conf, xywhn, xywh, xyxyn, xyxy in zip(
                boxes.cls, boxes.conf, boxes.xywhn, boxes.xywh, boxes.xyxyn, boxes.xyxy
        ):
            cls_int = int(cls)
            class_counts[cls_int] = class_counts.get(cls_int, 0) + 1
            self.detections.append({
                'class_index': cls_int,
                'class_name': self.class_names[cls_int],
                'confidence': float(conf),
                'xywhn': xywhn.numpy(),
                'xywh': xywh.numpy(),
                'xyxyn': xyxyn.numpy(),
                'xyxy': xyxy.numpy(),
                'img': Image(arr[int(xyxy[1]):int(xyxy[3]), int(xyxy[0]):int(xyxy[2])]),
            })

        return self.detections
