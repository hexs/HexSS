import cv2
import time
from hexss.image import ImageDraw
from hexss.image.capture import WindowCapture, DisplayCapture

available_windows = WindowCapture.list_available_windows()

# WindowCapture()
t1 = time.time()
cap = WindowCapture(hwnd=available_windows[0][0])  # or WindowCapture(title_name='Task Manager')
while True:
    im = cap.capture()
    im = im.resize('80%')
    draw = ImageDraw(im)
    draw.text((10, 10), f'FPS: {cap.fps:.2f}', fill=(255, 255, 255), stroke_width=2, stroke_fill='black')
    draw.text((10, 30), f'hwnd: {cap.hwnd}', fill=(255, 255, 255), stroke_width=2, stroke_fill='black')

    cv2.imshow('WindowCapture', im.numpy())
    if cv2.waitKey(1) & 0xFF == ord('q'):
        cv2.destroyAllWindows()
        break
    if time.time() - t1 > 10:
        cv2.destroyAllWindows()
        break

# DisplayCapture()
t1 = time.time()
cap = DisplayCapture(0)
while True:
    im = cap.capture()
    im = im.resize('80%')
    draw = ImageDraw(im)
    draw.text((10, 10), f'FPS: {cap.fps:.2f}', fill=(255, 255, 255), stroke_width=2, stroke_fill='black')

    cv2.imshow('DisplayCapture', im.numpy())
    if cv2.waitKey(1) & 0xFF == ord('q'):
        cv2.destroyAllWindows()
        break
    if time.time() - t1 > 10:
        cv2.destroyAllWindows()
        break
