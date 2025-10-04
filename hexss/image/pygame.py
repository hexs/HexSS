import os

import cv2
import numpy as np

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
import pygame


def numpy_to_pygame_surface(arr: "np.ndarray") -> "pygame.Surface":
    if arr.ndim == 3 and arr.shape[2] == 4:
        rgba = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA)
        h, w = rgba.shape[:2]
        return pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA")
    else:
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def pygame_surface_to_numpy(surface: "pygame.Surface") -> "np.ndarray":
    has_alpha = surface.get_masks()[3] != 0
    rgb_wh3 = pygame.surfarray.array3d(surface)
    rgb_hw3 = np.swapaxes(rgb_wh3, 0, 1)

    if not has_alpha:
        return cv2.cvtColor(rgb_hw3, cv2.COLOR_RGB2BGR)

    alpha_wh = pygame.surfarray.array_alpha(surface)
    alpha_hw = np.swapaxes(alpha_wh, 0, 1)
    rgba_hw4 = np.dstack((rgb_hw3, alpha_hw))
    return cv2.cvtColor(rgba_hw4, cv2.COLOR_RGBA2BGRA)
