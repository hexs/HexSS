from pathlib import Path
from typing import Optional, List
import hexss
from hexss.image2 import Image
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    hexss.check_packages('ultralytics', auto_install=True)
    from ultralytics import YOLO


class Detection:
    def __init__(self, class_index: int, class_name: str, confidence: float,
                 xywhn: np.ndarray, xywh: np.ndarray, xyxyn: np.ndarray, xyxy: np.ndarray):
        """
        Args:
            class_index (int): Index of the detected class.
            class_name (str): Name of the detected class.
            confidence (float): Confidence score of the detection.
            xywhn (np.ndarray): Bounding box in normalized (x, y, width, height) format.
            xywh (np.ndarray): Bounding box in pixel (x, y, width, height) format.
            xyxyn (np.ndarray): Bounding box in normalized (x1, y1, x2, y2) format.
            xyxy (np.ndarray): Bounding box in pixel (x1, y1, x2, y2) format.
        """
        self.class_index = class_index
        self.class_name = class_name
        self.confidence = confidence
        self.xywhn = xywhn
        self.xywh = xywh
        self.xyxyn = xyxyn
        self.xyxy = xyxy
        self.image: Optional[Image] = None


class Detector:
    def __init__(
            self,
            model_path: str | Path | None = None,
            device: str = "cpu",
            conf_thresh: float = 0.25,
            iou_thresh: float = 0.45
    ):
        """
        Args:
            model_path: Path to a .pt file or None for default YOLO
            device: "cpu" or "cuda"
            conf_thresh: Minimum confidence for detections
            iou_thresh: IoU threshold for NMS
        """
        if model_path is None:
            self.model = YOLO()
        else:
            self.model_path = Path(model_path)
            self.model = YOLO(self.model_path)
        self.model.conf = conf_thresh
        self.model.iou = iou_thresh
        self.model.to(device)
        self.class_names: List[str] = list(self.model.names.values())  # {0: 'person', 1: 'bicycle', 2: 'car', ...}

    def detect(self, image: Image) -> List[Detection]:
        detections = []
        result = self.model(source=image.im, verbose=False)[0]
        boxes = result.boxes
        for cls, conf, xywhn, xywh, xyxyn, xyxy in zip(
                boxes.cls, boxes.conf, boxes.xywhn, boxes.xywh, boxes.xyxyn, boxes.xyxy
        ):
            cls_int = int(cls)
            if self.model.device == "cpu":
                detection = Detection(
                    class_index=cls_int,
                    class_name=self.class_names[cls_int],
                    confidence=float(conf),
                    xywhn=xywhn.cpu().numpy(),
                    xywh=xywh.cpu().numpy(),
                    xyxyn=xyxyn.cpu().numpy(),
                    xyxy=xyxy.cpu().numpy()
                )
            else:
                detection = Detection(
                    class_index=cls_int,
                    class_name=self.class_names[cls_int],
                    confidence=float(conf),
                    xywhn=xywhn.numpy(),
                    xywh=xywh.numpy(),
                    xyxyn=xyxyn.numpy(),
                    xyxy=xyxy.numpy()
                )
            detections.append(detection)
        return detections
