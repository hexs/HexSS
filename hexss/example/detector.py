import json
import time
import cv2
from hexss.image import get_image
from hexss.image.func import numpy_to_pygame_surface
from hexss.multiprocessing import Multicore


def capture(data):
    url = 'http://192.168.123.122:2000/image?source=video_capture&id=0'
    while data['play']:
        img = get_image(url)
        data['img'] = img.copy()
        time.sleep(1 / 30)


def predict(data):
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

    detector = ObjectDetector("best.pt")
    while data['play']:
        if data.get('img') is not None:
            results = detector.detect(data['img'])
            data['results'] = results

            data['count'] = detector.count


def show(data):
    import pygame
    from pygame import Rect
    from pygame_gui import UIManager, UI_BUTTON_PRESSED
    from pygame_gui.elements import UIButton, UITextBox

    pygame.init()
    pygame.display.set_caption('Count QR Code')
    window_surface = pygame.display.set_mode((900, 600))
    manager = UIManager((900, 600))
    background = pygame.Surface((900, 600))
    background.fill(manager.ui_theme.get_colour('dark_bg'))

    hello_button = UIButton(Rect(0, 0, 100, 30), 'Hello', manager=manager)
    res_text_box = UITextBox(
        html_text="res_text_box",
        relative_rect=Rect(700, 30, 200, 500),
        manager=manager
    )

    clock = pygame.time.Clock()
    colors = [(255, 0, 255), (0, 255, 255)]

    while data['play']:
        time_delta = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                data['play'] = False
            if event.type == UI_BUTTON_PRESSED and event.ui_element == hello_button:
                print('Hello World!')
            manager.process_events(event)

        manager.update(time_delta)
        window_surface.blit(background, (0, 0))

        if data.get('img') is not None:
            img = data['img'].copy()
            for result in data['results']:
                xyxy = result['xyxy']
                cls = result['cls']
                x1y1 = xyxy[:2].astype(int)
                x2y2 = xyxy[2:].astype(int)
                cv2.rectangle(img, tuple(x1y1), tuple(x2y2), colors[int(cls)], 1)

            res_text_box.set_text(json.dumps(data['count'], indent=4))
            window_surface.blit(numpy_to_pygame_surface(img), (0, 30))

        manager.draw_ui(window_surface)
        pygame.display.update()

    pygame.quit()


if __name__ == '__main__':
    m = Multicore()
    m.set_data({
        'play': True,
        'img': None,
        'results': [],
        'count': None
    })
    m.add_func(show)
    m.add_func(predict)
    m.add_func(capture)

    m.start()
    m.join()
