from datetime import datetime

from hexss.image import ImageDraw
from hexss.image.capture import WindowCapture, DisplayCapture

if __name__ == '__main__':
    import cv2

    window_list = (WindowCapture.list_windows())  # [(<hwnd>, '<title_name>'),...]

    # WindowCapture()
    t1 = datetime.now()
    cap = WindowCapture(hwnd=window_list[0][0])  # or WindowCapture(title_name='Task Manager')
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
        if (datetime.now() - t1).total_seconds() > 10:
            cv2.destroyAllWindows()
            break

    # DisplayCapture()
    t1 = datetime.now()
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
        if (datetime.now() - t1).total_seconds() > 10:
            cv2.destroyAllWindows()
            break
