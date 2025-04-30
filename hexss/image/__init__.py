from typing import Optional, Tuple
from hexss import check_packages

check_packages('numpy', 'opencv-python', 'pygame', 'pillow', auto_install=True)

from .func import get_image, get_image_from_cam, get_image_from_url
import cv2
import numpy as np
from PIL import ImageGrab


def take_screenshot(
        region: Optional[Tuple[int, int, int, int]] = None,
        color: str = "RGB",
) -> np.ndarray:
    img = np.array(ImageGrab.grab(region))
    if color == "RGB":
        return img.copy()
    else:  # "BGR"
        img[:, :, ::-1].copy()


def rotate(image, angle, center=None, scale=1):
    if isinstance(center, np.ndarray):
        center = center.tolist()
    h, w = image.shape[:2]
    if center is None:
        center = (w // 2, h // 2)
    rotate_matrix = cv2.getRotationMatrix2D(center, angle, scale)
    image = cv2.warpAffine(src=image, M=rotate_matrix, dsize=(w, h))
    return image


def overlay(main_img, overlay_img, pos: tuple = (0, 0)):
    '''
    Overlay function to blend an overlay image onto a main image at a specified position.

    :param main_img (numpy.ndarray): The main image onto which the overlay will be applied.
    :param overlay_img (numpy.ndarray): The overlay image to be blended onto the main image.
                                        *** for rgba can use `cv2.imread('path',cv2.IMREAD_UNCHANGED)`
    :param pos (tuple): A tuple (x, y) representing the position where the overlay should be applied.

    :return: main_img (numpy.ndarray): The main image with the overlay applied in the specified position.
    '''

    if main_img.shape[2] == 4:
        main_img = cv2.cvtColor(main_img, cv2.COLOR_RGBA2RGB)

    x, y = pos
    h_overlay, w_overlay, _ = overlay_img.shape
    h_main, w_main, _ = main_img.shape

    x_start = max(0, x)
    x_end = min(x + w_overlay, w_main)
    y_start = max(0, y)
    y_end = min(y + h_overlay, h_main)

    img_main_roi = main_img[y_start:y_end, x_start:x_end]
    img_overlay_roi = overlay_img[(y_start - y):(y_end - y), (x_start - x):(x_end - x)]

    if overlay_img.shape[2] == 4:
        img_a = img_overlay_roi[:, :, 3] / 255.0
        img_rgb = img_overlay_roi[:, :, :3]
        img_overlay_roi = img_rgb * img_a[:, :, np.newaxis] + img_main_roi * (1 - img_a[:, :, np.newaxis])

    img_main_roi[:, :] = img_overlay_roi

    return main_img


def crop_img(image, xywhn, shift=(0, 0), resize=None):
    wh_ = np.array(image.shape[1::-1])
    xyn = np.array(xywhn[:2])
    whn = np.array(xywhn[2:])
    x1y1_ = ((xyn - whn / 2) * wh_).astype(int)
    x2y2_ = ((xyn + whn / 2) * wh_).astype(int)

    x1_, y1_ = x1y1_ + shift
    x2_, y2_ = x2y2_ + shift

    image_crop = image[y1_:y2_, x1_:x2_]

    if resize:
        return cv2.resize(image_crop, resize)
    return image_crop


def controller(img, brightness=0, contrast=0):
    """Adjust brightness and contrast of an image."""

    if brightness != 0:
        shadow = brightness if brightness > 0 else 0
        max_val = 255 if brightness > 0 else 255 + brightness
        alpha = (max_val - shadow) / 255
        gamma = shadow
        img = cv2.addWeighted(img, alpha, img, 0, gamma)

    if contrast != 0:
        alpha = float(131 * (contrast + 127)) / (127 * (131 - contrast))
        gamma = 127 * (1 - alpha)
        img = cv2.addWeighted(img, alpha, img, 0, gamma)

    return img
