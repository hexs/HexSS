import cv2
import numpy as np
import urllib.request
from typing import Optional, Union, Literal
import pygame


def get_image_from_cam(cap: cv2.VideoCapture) -> Optional[np.ndarray]:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture frame from camera")
        return None
    return frame


def get_image_from_url(url: str) -> Optional[np.ndarray]:
    try:
        with urllib.request.urlopen(url, timeout=5) as req:
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Error loading image from URL: {e}")
        return None


def numpy_to_pygame_surface(arr: np.ndarray) -> pygame.Surface:
    arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    return pygame.surfarray.make_surface(arr.swapaxes(0, 1))


def get_image(source: Union[cv2.VideoCapture, str], output: Literal['numpy', 'pygame'] = 'numpy') -> Optional[
    Union[np.ndarray, pygame.Surface]]:
    if isinstance(source, str):
        img = get_image_from_url(source)
    elif isinstance(source, cv2.VideoCapture):
        img = get_image_from_cam(source)
    else:
        raise ValueError("Invalid source type. Expected cv2.VideoCapture or str (URL).")

    if img is None:
        return None

    if output == 'pygame':
        return numpy_to_pygame_surface(img)
    return img
