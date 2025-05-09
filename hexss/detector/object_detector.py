from ultralytics import YOLO


class ObjectDetector:
    def __init__(self, model_path):
        self.model = YOLO(model_path)
        self.names = {}
        self.count = {}

    def detect(self, image):
        results = self.model(source=image, verbose=False)[0]
        self.names = results.names

        class_counts = {}
        boxes = results.boxes
        detections = []

        for cls, conf, xywhn, xywh, xyxyn, xyxy in zip(
                boxes.cls, boxes.conf, boxes.xywhn, boxes.xywh, boxes.xyxyn, boxes.xyxy
        ):
            cls_int = int(cls)
            class_counts[cls_int] = class_counts.get(cls_int, 0) + 1
            detections.append({
                'cls': cls_int,
                'class_name': self.names[cls_int],
                'confidence': float(conf),
                'xywhn': xywhn.numpy(),
                'xywh': xywh.numpy(),
                'xyxyn': xyxyn.numpy(),
                'xyxy': xyxy.numpy()
            })

        self.count = {self.names[i]: {'count': class_counts.get(i, 0)} for i in self.names}
        return detections
