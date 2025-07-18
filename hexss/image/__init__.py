import hexss

hexss.check_packages('numpy', 'opencv-python', 'pygame', 'pillow', 'matplotlib', auto_install=True)

from .func import get_image, get_image_from_cam, get_image_from_url, \
    take_screenshot, rotate, overlay, crop_img, controller

from .im import PILImage, PILImageDraw
from .im import Image, ImageDraw, ImageFilter, ImageFont, Transpose, Transform, Resampling, Dither, Palette, Quantize

# from .detector import Detector
# from .classifier import Classifier, MultiClassifier
