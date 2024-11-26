from .func import get_image, get_image_from_cam, get_image_from_url
import cv2
import numpy as np


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
