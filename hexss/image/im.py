import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import ImageFilter
import PIL.Image
from PIL.Image import Transpose, Resampling, Dither, Palette
from typing import Union, Tuple, Optional, Self


class Image:
    """
    Wrapper around PIL.Image with convenient utilities, OpenCV interoperability,
    and support for loading from URLs.
    """

    def __init__(
            self,
            source: Union[str, np.ndarray, PIL.Image.Image],
            mode: Optional[str] = "RGB"
    ):
        if isinstance(source, str) and not source.lower().startswith(("http://", "https://")):
            img = PIL.Image.open(source)

        elif isinstance(source, str) and source.lower().startswith(("http://", "https://")):
            resp = requests.get(source)
            resp.raise_for_status()
            img = PIL.Image.open(BytesIO(resp.content))

        elif isinstance(source, np.ndarray):
            rgb = cv2.cvtColor(source, cv2.COLOR_BGR2RGB)
            img = PIL.Image.fromarray(rgb)

        elif isinstance(source, PIL.Image.Image):
            img = source.copy()

        else:
            raise TypeError(
                f"Unsupported source type: {type(source)}. "
                "Provide a file path, URL string, NumPy array, or PIL.Image."
            )

        if mode is not None:
            img = img.convert(mode)
        self.image = img

    @property
    def size(self) -> Tuple[int, int]:
        return self.image.size

    @property
    def mode(self) -> str:
        return self.image.mode

    @property
    def format(self) -> Optional[str]:
        return self.image.format

    def numpy(self, mode='RGB') -> np.ndarray:
        arr = np.array(self.image)
        if mode == 'RGB':
            return arr
        elif mode == 'BGR':
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError(f"Unsupported mode: {mode}. Use 'RGB' or 'BGR'.")

    def detect(self, model) -> list[dict]:
        return model.detect(self.image)

    def classify(self, model) -> tuple[str, float]:
        return model.classify(self.image)

    def show(self) -> None:
        self.image.show()

    def save(self, path: str, **kwargs) -> None:
        self.image.save(path, **kwargs)

    def __repr__(self) -> str:
        name = self.image.__class__.__name__
        return f"<Image {name} mode={self.mode} size={self.size}>"

    def filter(self, filter: ImageFilter.Filter | type[ImageFilter.Filter]) -> Self:
        return self.image.filter(filter)

    def convert(
            self,
            mode: str | None = None,
            matrix: tuple[float, ...] | None = None,
            dither: Dither | None = None,
            palette: Palette = Palette.WEB,
            colors: int = 256,
    ) -> Self:
        return self.image.convert(mode, matrix, dither, palette, colors)

    def rotate(
            self,
            angle: float,
            resample: Resampling = Resampling.NEAREST,
            expand: Union[int, bool] = False,
            center: Optional[Tuple[float, float]] = None,
            translate: Optional[Tuple[int, int]] = None,
            fillcolor: Optional[Union[float, Tuple[float, ...], str]] = None
    ) -> Self:
        return self.image.rotate(angle, resample, expand, center, translate, fillcolor)

    def transpose(self, method: Transpose) -> Self:
        return self.image.transpose(method)

    def crop(self, box: Tuple[int, int, int, int]) -> Self:
        return self.image.crop(box)

    def resize(
            self,
            size: tuple[int, int],
            resample: int | None = None,
            box: tuple[float, float, float, float] | None = None,
            reducing_gap: float | None = None,
    ) -> Self:
        return self.image.resize(size, resample, box, reducing_gap)
