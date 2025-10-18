from hexss.env import set_proxy; set_proxy()
from hexss.image import Image
from hexss.image.detector import Detector

detector = Detector()
img = Image("image.jpg")
detections = detector.detect(img)
for det in detections:
    print(f"Class: {det.name:15}, Confidence: {det.conf:.2f}, Box: {det.box}")
img.show()
img_with_boxes = detector.draw_boxes(img)
img_with_boxes.show()