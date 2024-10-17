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
    from hexss.detector import ObjectDetector

    detector = ObjectDetector("best.pt")
    while data['play']:
        if data.get('img') is not None:
            results = detector.detect(data['img'])
            data['results'] = results
            data['count'] = detector.count


def show(data):
    import pygame
    from pygame import Rect
    from pygame_gui import UIManager
    from pygame_gui.elements import UITextBox

    pygame.init()
    pygame.display.set_caption('Count QR Code')
    display = pygame.display.set_mode((640 + 200, 480))
    manager = UIManager((640 + 200, 480))
    background = pygame.Surface((640 + 200, 480))
    background.fill(manager.ui_theme.get_colour('dark_bg'))

    res_text_box = UITextBox(
        html_text="res_text_box",
        relative_rect=Rect(640, 0, 200, 480),
        manager=manager
    )

    clock = pygame.time.Clock()
    colors = [(255, 0, 255), (0, 255, 255), (255, 255, 0)]

    while data['play']:
        time_delta = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                data['play'] = False

            manager.process_events(event)

        manager.update(time_delta)

        display.blit(background, (0, 0))

        if data.get('img') is not None:
            img = data['img'].copy()
            for result in data['results']:
                xyxy = result['xyxy']
                cls = result['cls']
                x1y1 = xyxy[:2].astype(int)
                x2y2 = xyxy[2:].astype(int)
                cv2.rectangle(img, tuple(x1y1), tuple(x2y2), colors[int(cls)], 2)

            res_text_box.set_text(json.dumps(data['count'], indent=4))
            display.blit(numpy_to_pygame_surface(img), (0, 0))

        manager.draw_ui(display)
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
