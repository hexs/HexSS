from hexss import check_packages

check_packages('numpy', 'opencv-python', 'pygame', 'pillow', auto_install=True)

from .func import get_image, get_image_from_cam, get_image_from_url, \
    take_screenshot, rotate, overlay, crop_img, controller

from .im import Image, ImageFilter, Transpose
from .detector import Detector
from .classifier import Classifier

