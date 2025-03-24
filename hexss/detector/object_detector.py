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


from keras import models
import numpy as np
import cv2


class Classifier:
    def __init__(self, model_path, class_names):
        self.model = models.load_model(model_path)
        self.class_names = class_names
        self.resize = None

    def classify(self, image):
        if self.resize:
            image = cv2.resize(image, self.resize)

        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img_array = np.expand_dims(image, axis=0)
        predictions = self.model.predict_on_batch(img_array)
        exp_x = [2.7 ** x for x in predictions[0]]
        percent_score_list = [round(x * 100 / sum(exp_x)) for x in exp_x]
        highest_score_index = np.argmax(predictions[0])
        highest_score_name = self.class_names[highest_score_index]
        highest_score_percent = percent_score_list[highest_score_index]
        return highest_score_name, highest_score_percent
