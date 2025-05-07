from typing import Union, Tuple, Optional, Self
from io import BytesIO
import hexss

hexss.check_packages('numpy', 'opencv-python', 'requests', 'pillow', auto_install=True)

import numpy as np
import cv2
import requests
from PIL import Image as PILImage, ImageFilter
from PIL.Image import Transpose, Resampling, Dither, Palette


class Image:
    def __init__(
            self,
            source: Union[str, bytes, np.ndarray, PILImage.Image],
            size: Tuple[int, int] = (0, 0),
            color: Union[float, Tuple[float, ...], str, None] = 0,
    ) -> None:
        if isinstance(source, str):
            mode = source.upper()
            if mode in {"RGB", "RGBA", "L", "1"}:
                self.image = PILImage.new(mode, size, color)
            elif source.startswith(('http://', 'https://')):
                resp = requests.get(source)
                resp.raise_for_status()
                self.image = PILImage.open(BytesIO(resp.content))
            else:
                self.image = PILImage.open(source)
        elif isinstance(source, bytes):
            self.image = PILImage.open(BytesIO(source))
        elif isinstance(source, np.ndarray):
            rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
            self.image = PILImage.fromarray(rgb)
        elif isinstance(source, PILImage.Image):
            self.image = source.copy()
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

    @property
    def size(self) -> Tuple[int, int]:
        return self.image.size

    @property
    def mode(self) -> str:
        return self.image.mode

    @property
    def format(self) -> Optional[str]:
        return self.image.format

    def numpy(self, mode: str = 'BGR') -> np.ndarray:
        arr = np.array(self.image)
        if mode == 'RGB':
            return arr
        elif mode == 'BGR':
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        raise ValueError("mode must be 'RGB' or 'BGR'")

    def overlay(self, overlay_img: Union[Self, np.ndarray, PILImage.Image], box: Tuple[int, int]) -> Self:
        if isinstance(overlay_img, Image):
            img = overlay_img.image
        elif isinstance(overlay_img, np.ndarray):
            img = PILImage.fromarray(cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB))
        elif isinstance(overlay_img, PILImage.Image):
            img = overlay_img
        else:
            raise TypeError(f"Unsupported overlay image type: {type(overlay_img)}")

        if img.mode == 'RGBA':
            self.image.paste(img, box, mask=img.split()[3])
        else:
            self.image.paste(img, box)
        return self

    def filter(self, filter: ImageFilter.Filter | type[ImageFilter.Filter]) -> Self:
        return Image(self.image.filter(filter))

    def convert(
            self,
            mode: str,
            **kwargs
    ) -> Self:
        if self.mode == 'RGBA' and mode == 'RGB':
            bg = PILImage.new('RGB', self.size, (255, 255, 255))
            bg.paste(self.image, mask=self.image.split()[3])
            return Image(bg)
        return Image(self.image.convert(mode, **kwargs))

    def rotate(self, angle: float, expand: bool = False, **kwargs) -> Self:
        return Image(self.image.rotate(angle, expand=expand, **kwargs))

    def transpose(self, method: Transpose) -> Self:
        return Image(self.image.transpose(method))

    def crop(self, box: Tuple[int, int, int, int]) -> Self:
        return Image(self.image.crop(box))

    def resize(self, size: Tuple[int, int], **kwargs) -> Self:
        return Image(self.image.resize(size, **kwargs))

    def save(self, path: str, **kwargs) -> Self:
        self.image.save(path, **kwargs)
        return self

    def show(self) -> Self:
        self.image.show()
        return self

    def __repr__(self) -> str:
        name = self.image.__class__.__name__
        return f"<Image {name} mode={self.mode} size={self.size[0]}x{self.size[1]}>"
