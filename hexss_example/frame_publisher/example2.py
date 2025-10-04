import time
import cv2
import numpy as np
from random import randint
from hexss.frame_publisher import FramePublisher
from hexss.string import random_str

f = FramePublisher(jpeg_quality=100, open_browser=True)

H, W = 2000, 2000
img1 = np.full((H, W, 3), 200, np.uint8)
cv2.circle(img1, (randint(0, W - 1), randint(0, H - 1)), 100, (255, 0, 0), -1)
f.publish(random_str(4), img1)

time.sleep(1)

img2 = np.full((H, W, 3), 200, np.uint8)
cv2.circle(img2, (randint(0, W - 1), randint(0, H - 1)), 100, (255, 255, 0), -1)
f.publish(random_str(4), img2)
