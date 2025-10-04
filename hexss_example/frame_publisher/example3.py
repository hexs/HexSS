import cv2
import numpy as np
from hexss.frame_publisher import FramePublisher

f = FramePublisher(jpeg_quality=100, open_browser=True, unset_proxy=True)
x, y = 50, 50
vx, vy = 5, 4
W = 640
H = 480
while True:
    x += vx
    y += vy
    if x < 10 or x > W - 10: vx = -vx
    if y < 10 or y > H - 10: vy = -vy
    img = np.full((H, W, 3), 30, np.uint8)
    cv2.circle(img, (int(x), int(y)), 12, (0, 255, 0), -1)
    f.publish("Demo", img)
