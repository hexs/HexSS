import time
import cv2
import numpy as np
from random import randint
from datetime import datetime
from hexss.frame_publisher import FramePublisher

f = FramePublisher(jpeg_quality=100)

xy1 = [300, 300]
xy2 = [300, 300]
xy3 = [300, 300]
W = H = 600
last2 = datetime.now()
last3 = datetime.now()

def update1():
    xy1[0] = max(0, min(W, xy1[0] + randint(-10, 10)))
    xy1[1] = max(0, min(H, xy1[1] + randint(-10, 10)))
    img = np.full((H, W, 3), 200, np.uint8)
    cv2.circle(img, tuple(xy1), 10, (255, 0, 0), -1)
    f.imshow("Image1", img)

def update2():
    xy2[0] = max(0, min(W, xy2[0] + randint(-10, 10)))
    xy2[1] = max(0, min(H, xy2[1] + randint(-10, 10)))
    img = np.full((H, W, 3), 200, np.uint8)
    cv2.circle(img, tuple(xy2), 10, (0, 255, 0), -1)
    f.imshow("Image2", img)

def update3():
    xy3[0] = max(0, min(W, xy3[0] + randint(-10, 10)))
    xy3[1] = max(0, min(H, xy3[1] + randint(-10, 10)))
    img = np.full((H, W, 3), 200, np.uint8)
    cv2.circle(img, tuple(xy3), 10, (0, 0, 255), -1)
    f.imshow("Image3", img)

while True:
    update1()
    if (datetime.now() - last2).total_seconds() > 1:
        last2 = datetime.now(); update2()
    if (datetime.now() - last3).total_seconds() > 5:
        last3 = datetime.now(); update3()
    time.sleep(1/30)
