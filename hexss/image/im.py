from pathlib import Path
from typing import Union, Optional, Tuple, List, Self
from io import BytesIO
import hexss

hexss.check_packages('numpy', 'opencv-python', 'requests', 'pillow', auto_install=True)

import numpy as np
import cv2
import requests
from PIL import Image as PILImage, ImageFilter
from PIL.Image import Transpose, Resampling, Dither, Palette


class Image:
    """
    A wrapper class for handling images with various sources and operations.
    Supports formats like Path, URL, bytes, numpy arrays, and PIL images.
    """
    _MODES = {"RGB", "RGBA", "L", "1"}  # Supported image modes

    def __init__(
            self,
            source: Union[Path, str, bytes, np.ndarray, PILImage.Image],
            size: Tuple[int, int] = (0, 0),
            color: Union[float, Tuple[float, ...], str, None] = 0,
            session: Optional[requests.Session] = None,
    ) -> None:
        self._session = session or requests.Session()
        # type(self.image) is PIL Image

        if isinstance(source, PILImage.Image):
            self.image = source.copy()
        elif isinstance(source, np.ndarray):
            self.image = self._from_numpy_array(source)
        elif isinstance(source, (Path, str)) and Path(source).is_file():
            self.image = self._from_file(source)
        elif isinstance(source, str) and source.startswith(("http://", "https://")):
            self.image = self._from_url(source)
        elif isinstance(source, str) and source.upper() in self._MODES:
            self.image = self._blank_from_mode(source.upper(), size, color)
        elif isinstance(source, bytes):
            self.image = self._from_bytes(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

    @staticmethod
    def _from_numpy_array(arr: np.ndarray) -> PILImage.Image:
        if arr.ndim == 3 and arr.shape[-1] == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        elif arr.ndim == 3 and arr.shape[-1] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGBA)
        elif arr.ndim == 2:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
        return PILImage.fromarray(arr)

    @staticmethod
    def _from_file(source: Union[Path, str]) -> PILImage.Image:
        try:
            return PILImage.open(source)
        except Exception as e:
            raise IOError(f"Cannot open image file {source!r}") from e

    def _from_url(self, url: str) -> PILImage.Image:
        resp = self._session.get(url, timeout=(3.05, 27))
        resp.raise_for_status()
        try:
            return PILImage.open(BytesIO(resp.content))
        except Exception as e:
            raise IOError(f"Downloaded data from {url!r} is not a valid image") from e

    @staticmethod
    def _from_bytes(data: bytes) -> PILImage.Image:
        return PILImage.open(BytesIO(data))

    @classmethod
    def _blank_from_mode(
            cls,
            mode: str,
            size: Tuple[int, int],
            color: Union[float, Tuple[float, ...], str, None]
    ) -> PILImage.Image:
        return PILImage.new(mode, size, color)

    @classmethod
    def open(cls, fp, mode="r", formats=None) -> Self:
        pil_im = PILImage.open(fp, mode, formats)
        return cls(pil_im)

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
        raise ValueError("Mode must be 'RGB' or 'BGR'")

    def overlay(
            self,
            overlay_img: Union[Self, np.ndarray, PILImage.Image],
            box: Tuple[int, int],
            opacity: float = 1.0
    ) -> Self:
        """
        Overlay another image on top of this image at the given box with the specified opacity.

        Args:
            overlay_img: The image to overlay (Image, np.ndarray, or PILImage.Image).
            box: The (x, y) position to place the overlay.
            opacity: Opacity of the overlay image (0.0 transparent - 1.0 opaque).

        Returns:
            Self: The modified image object.
        """
        if not (0.0 <= opacity <= 1.0):
            raise ValueError("Opacity must be between 0.0 and 1.0")

        # Prepare the overlay image as PIL Image
        if isinstance(overlay_img, Image):
            img = overlay_img.image
        elif isinstance(overlay_img, np.ndarray):
            img = PILImage.fromarray(cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB))
        elif isinstance(overlay_img, PILImage.Image):
            img = overlay_img
        else:
            raise TypeError(f"Unsupported overlay image type: {type(overlay_img)}")

        # Convert overlay to RGBA if not already
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Apply opacity to the overlay alpha channel
        if opacity < 1.0:
            alpha = img.split()[3]
            alpha = alpha.point(lambda px: int(px * opacity))
            img.putalpha(alpha)

        # Create a base image in RGBA
        base = self.image.convert('RGBA')

        # Paste overlay onto base
        base.paste(img, box, mask=img)
        self.image = base.convert(self.image.mode)
        return self

    def invert_colors(self) -> Self:
        img = self.image
        if img.mode == 'RGBA':
            r, g, b, a = img.split()
            inverted = PILImage.merge('RGBA', (
                # PILImage.eval(r, lambda px: 255 - px),
                # PILImage.eval(g, lambda px: 255 - px),
                # PILImage.eval(b, lambda px: 255 - px),
                r.point(lambda px: 255 - px),
                g.point(lambda px: 255 - px),
                b.point(lambda px: 255 - px),
                a
            ))
        elif img.mode == 'RGB':
            r, g, b = img.split()
            inverted = PILImage.merge('RGB', (
                # PILImage.eval(r, lambda px: 255 - px),
                # PILImage.eval(g, lambda px: 255 - px),
                # PILImage.eval(b, lambda px: 255 - px)
                r.point(lambda px: 255 - px),
                g.point(lambda px: 255 - px),
                b.point(lambda px: 255 - px)
            ))
        else:
            raise NotImplementedError(f"Inversion not implemented for mode {img.mode!r}")
        return Image(inverted)

    def filter(self, filter: ImageFilter.Filter | type[ImageFilter.Filter]) -> Self:
        return Image(self.image.filter(filter))

    def convert(self, mode: str, **kwargs) -> Self:
        if self.mode == 'RGBA' and mode == 'RGB':
            bg = PILImage.new('RGB', self.size, (255, 255, 255))
            bg.paste(self.image, mask=self.image.split()[3])
            return Image(bg)
        return Image(self.image.convert(mode, **kwargs))

    def rotate(self, angle: float, expand: bool = False, **kwargs) -> Self:
        return Image(self.image.rotate(angle, expand=expand, **kwargs))

    def transpose(self, method: Transpose) -> Self:
        return Image(self.image.transpose(method))

    def crop(self, box: Tuple[float, float, float, float]) -> Self:
        return Image(self.image.crop(box))

    def resize(self, size: Tuple[int, int], **kwargs) -> Self:
        return Image(self.image.resize(size, **kwargs))

    def copy(self) -> Self:
        return Image(self.image.copy())

    def save(self, path: str, **kwargs) -> Self:
        self.image.save(path, **kwargs)
        return self

    def show(self, title: Optional[str] = None) -> Self:
        self.image.show(title=title)
        return self

    def detect(self, model):
        return model.detect(self)

    def classify(self, model):
        return model.classify(self)

    def __repr__(self) -> str:
        name = self.image.__class__.__name__
        return f"<Image {name} mode={self.mode} size={self.size[0]}x{self.size[1]}>"
