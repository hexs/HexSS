import cv2
import pygame
from hexss.image import get_image


def test_np():
    while True:
        img = get_image(source)
        cv2.imshow('img', img)
        key = cv2.waitKey(1)
        if key == 27:
            break


def test_pygame():
    pygame.init()
    screen = pygame.display.set_mode((640, 480))
    clock = pygame.time.Clock()

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise SystemExit

            img = get_image(source, output='pygame')
            if img is not None:
                screen.blit(img, (0, 0))
                pygame.display.flip()
            else:
                print("Failed to retrieve image. Retrying...")

            clock.tick(30)
    finally:
        if isinstance(source, cv2.VideoCapture):
            source.release()
        pygame.quit()


if __name__ == "__main__":
    source = cv2.VideoCapture(0)
    # source = "http://192.168.225.137:2000/image?source=video_capture&id=0"

    test_np()
    # test_pygame()
