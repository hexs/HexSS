from typing import Union, Optional, List, Dict
import hexss
from hexss.image import Image
from PIL import Image as PILImage
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

    def set_image(self, image: Union[PILImage.Image, np.ndarray], xyxy: np.ndarray) -> None:
        """
        Crop and assign the corresponding bounding box image.

        Args:
            image (Union[PILImage.Image, np.ndarray]): Original image.
            xyxy (np.ndarray): Bounding box in pixel (x1, y1, x2, y2) format.
        """
        if isinstance(image, np.ndarray):
            self.image = Image(image[int(xyxy[1]):int(xyxy[3]), int(xyxy[0]):int(xyxy[2])])
        else:
            self.image = Image(image.crop(xyxy.tolist()))


class Detector:
    def __init__(self, model_path: Optional[str] = None):
        """
        Args:
            model_path (Optional[str]): Path to the YOLO model. If None, loads the default YOLO model.
        """
        # Load YOLO model
        self.model = YOLO(model_path) if model_path else YOLO()
        self.class_names: List[str] = []  # {0: 'person', 1: 'bicycle', 2: 'car', ...}
        self.class_counts: Dict[int, int] = {}
        self.detections: List[Detection] = []

    def detect(self, image: Union[Image, PILImage.Image, np.ndarray]) -> List[Detection]:
        """
        Perform object detection on an image.

        Args:
            image (Union[Image, PILImage.Image, np.ndarray]): Input image for detection.

        Returns:
            List[Detection]: List of detection results.

        Raises:
            TypeError: If the input image type is unsupported.
        """
        # Convert hexss.Image to numpy array if needed
        if isinstance(image, Image):
            image = image.image
        elif isinstance(image, PILImage.Image):
            pass
        elif isinstance(image, np.ndarray):
            pass
        else:
            raise TypeError(
                f"Unsupported image type: {type(image)}. Supported types: hexss.Image, PIL.Image, np.ndarray.")

        results = self.model(source=image, verbose=False)[0]
        self.class_names = results.names

        self.detections = []
        class_counts = {}

        boxes = results.boxes
        for cls, conf, xywhn, xywh, xyxyn, xyxy in zip(
                boxes.cls, boxes.conf, boxes.xywhn, boxes.xywh, boxes.xyxyn, boxes.xyxy
        ):
            cls_int = int(cls)
            class_counts[cls_int] = class_counts.get(cls_int, 0) + 1
            detection = Detection(
                class_index=cls_int,
                class_name=self.class_names[cls_int],
                confidence=float(conf),
                xywhn=xywhn.numpy(),
                xywh=xywh.numpy(),
                xyxyn=xyxyn.numpy(),
                xyxy=xyxy.numpy()
            )

            detection.set_image(image, xyxy)
            self.detections.append(detection)
            self.class_counts = class_counts  # {<class index>: <number of detections>, 0: 4, 41: 1, 56: 1}

        return self.detections
