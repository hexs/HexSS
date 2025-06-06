from pathlib import Path
from typing import Union, Optional, Tuple, List, Self, IO, Type, Literal, Any, Sequence
from io import BytesIO

import hexss

hexss.check_packages('numpy', 'opencv-python', 'requests', 'pillow', auto_install=True)

import numpy as np
import cv2
import requests
from PIL._typing import Coords
from PIL import Image as PILImage
from PIL import ImageDraw as PILImageDraw
from PIL import ImageFilter, ImageGrab, ImageWin, ImageFont
from PIL.Image import Transpose, Transform, Resampling, Dither, Palette, Quantize, SupportsArrayInterface
from PIL.ImageDraw import _Ink


class Image:
    """
    A wrapper class for handling images with various sources and operations.
    Supports formats like Path, URL, bytes, numpy arrays, and PIL images.
    """

    def __init__(
            self,
            source: Union[Path, str, bytes, np.ndarray, PILImage.Image],
            session: Optional[requests.Session] = None,
    ) -> None:
        self._session = session or requests.Session()
        # type(self.image) is PIL Image

        if isinstance(source, PILImage.Image):
            self.image = source.copy()
        elif isinstance(source, Image):
            self.image = source.image.copy()
        elif isinstance(source, np.ndarray):
            self.image = self._from_numpy_array(source)
        elif isinstance(source, (Path, str)) and Path(source).is_file():
            self.image = self._from_file(source)
        elif isinstance(source, str) and source.startswith(("http://", "https://")):
            self.image = self._from_url(source)
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
            raise IOError(f"Cannot open image file {source!r}: {e}") from e

    def _from_url(self, url: str) -> PILImage.Image:
        resp = self._session.get(url, timeout=(3.05, 27))
        resp.raise_for_status()
        try:
            return PILImage.open(BytesIO(resp.content))
        except Exception as e:
            raise IOError(f"Downloaded data from {url!r} is not a valid image: {e}") from e

    @staticmethod
    def _from_bytes(data: bytes) -> PILImage.Image:
        return PILImage.open(BytesIO(data))

    @classmethod
    def new(
            cls,
            mode: str,
            size: Tuple[int, int],
            color: float | tuple[float, ...] | str | None = 0,
    ) -> Self:
        pil_im = PILImage.new(mode, size, color)
        return cls(pil_im)

    @classmethod
    def open(
            cls,
            fp: Union[str, Path, IO[bytes]],
            mode: Literal["r"] = "r",
            formats: Optional[Union[List[str], Tuple[str, ...]]] = None,
    ) -> Self:
        pil_im = PILImage.open(fp, mode, formats)
        return cls(pil_im)

    @classmethod
    def frombuffer(
            cls,
            mode: str,
            size: Tuple[int, int],
            data: bytes | SupportsArrayInterface,
            decoder_name: str = "raw",
            *args: Any
    ):
        pil_im = PILImage.frombuffer(mode, size, data, decoder_name, *args)
        return cls(pil_im)

    @classmethod
    def screenshot(
            cls,
            bbox: Optional[Tuple[int, int, int, int]] = None,
            include_layered_windows: bool = False,
            all_screens: bool = False,
            xdisplay: Optional[str] = None,
            window: Optional[Union[int, "ImageWin.HWND"]] = None,
    ) -> Self:
        pil_im = ImageGrab.grab(bbox, include_layered_windows, all_screens, xdisplay, window)
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

    def numpy(self, mode: Literal['RGB', 'BGR'] = 'BGR') -> np.ndarray:
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
            pil_im = overlay_img.image
        elif isinstance(overlay_img, np.ndarray):
            pil_im = PILImage.fromarray(cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB))
        elif isinstance(overlay_img, PILImage.Image):
            pil_im = overlay_img
        else:
            raise TypeError(f"Unsupported overlay image type: {type(overlay_img)}")

        # Convert overlay to RGBA if not already
        if pil_im.mode != 'RGBA':
            pil_im = pil_im.convert('RGBA')

        # Apply opacity to the overlay alpha channel
        if opacity < 1.0:
            alpha = pil_im.split()[3]
            alpha = alpha.point(lambda px: int(px * opacity))
            pil_im.putalpha(alpha)

        # Create a base image in RGBA
        base = self.image.convert('RGBA')

        # Paste overlay onto base
        base.paste(pil_im, box, mask=pil_im)
        self.image = base.convert(self.mode)
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
        elif img.mode == 'L':
            inverted = img.point(lambda px: 255 - px)
        else:
            raise NotImplementedError(f"Inversion not implemented for mode {img.mode!r}")
        return Image(inverted)

    def filter(self, filter: Union[ImageFilter.Filter, Type[ImageFilter.Filter]]) -> Self:
        return Image(self.image.filter(filter))

    def convert(self, mode: str, **kwargs) -> Self:
        if self.mode == 'RGBA' and mode == 'RGB':
            bg = PILImage.new('RGB', self.size, (255, 255, 255))
            bg.paste(self.image, mask=self.image.split()[3])
            return Image(bg)
        return Image(self.image.convert(mode, **kwargs))

    def rotate(self, angle: float, expand: bool = False, **kwargs) -> Self:
        return Image(self.image.rotate(angle, expand=expand, **kwargs))

    def transpose(self, method: PILImage.Transpose) -> Self:
        return Image(self.image.transpose(method))

    def crop(self,
             xyxy: Tuple[float, float, float, float] | np.ndarray = None,
             xywh: Tuple[float, float, float, float] | np.ndarray = None,
             xyxyn: Tuple[float, float, float, float] | np.ndarray = None,
             xywhn: Tuple[float, float, float, float] | np.ndarray = None,
             ) -> Self:
        if xyxy is not None:
            pass
        elif xywh is not None:
            xyxy = (xywh[0] - xywh[2] / 2, xywh[1] - xywh[3] / 2,
                    xywh[0] + xywh[2] / 2, xywh[1] + xywh[3] / 2)
        elif xyxyn is not None:
            xyxy = (xyxyn[0] * self.size[0], xyxyn[1] * self.size[1],
                    xyxyn[2] * self.size[0], xyxyn[3] * self.size[1])
        elif xywhn is not None:
            xyxy = (xywhn[0] * self.size[0] - xywhn[2] * self.size[0] / 2,
                    xywhn[1] * self.size[1] - xywhn[3] * self.size[1] / 2,
                    xywhn[0] * self.size[0] + xywhn[2] * self.size[0] / 2,
                    xywhn[1] * self.size[1] + xywhn[3] * self.size[1] / 2)
        else:
            raise ValueError("At least one of xyxy, xywh, xyxyn, or xywhn must be provided")

        return Image(self.image.crop(xyxy))

    def resize(
            self,
            size: Union[Tuple[int, int], str],
            resample: int | None = None,
            box: tuple[float, float, float, float] | None = None,
            reducing_gap: float | None = None
    ) -> Self:
        '''
        example:
        resize((600,400))
        resize('80%')
        '''
        if isinstance(size, str):
            if size.endswith('%'):
                percent = float(size[:-1]) / 100.0
                size = (int(self.size[0] * percent), int(self.size[1] * percent))
            else:
                raise ValueError(f"Invalid size string: {size!r}. Use format like '80%'")
        return Image(self.image.resize(size=size, resample=resample, box=box, reducing_gap=reducing_gap))

    def copy(self) -> Self:
        return Image(self.image.copy())

    def save(self, fp: Union[str, Path, IO[bytes]], format: Optional[str] = None, **params: Any) -> Self:
        self.image.save(fp, format, **params)
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

    def draw(self, origin: Union[str, Tuple[float, float]] = 'topleft') -> "ImageDraw":
        return ImageDraw(self, origin)


class ImageDraw:
    def __init__(self, im: Image, origin: Union[str, Tuple[float, float]] = 'topleft') -> None:
        self.im = im
        self.draw = PILImageDraw.Draw(self.im.image)
        self.origin = np.zeros(2, dtype=float)
        self.set_origin(origin)

    def set_origin(self, origin: Union[str, Tuple[float, float]]) -> Self:
        if isinstance(origin, str):
            mapping = {
                'topleft': (0.0, 0.0),
                'topright': (1.0, 0.0),
                'bottomleft': (0.0, 1.0),
                'bottomright': (1.0, 1.0),
                'center': (0.5, 0.5),
            }
            if origin not in mapping:
                raise ValueError(f"Unknown origin string: {origin}")
            self.set_abs_origin(mapping[origin])
        else:
            self.origin = np.array(origin, dtype=float)
        return self

    def set_abs_origin(self, abs_origin: Tuple[float, float]) -> Self:
        self.origin = np.array(abs_origin) * self.im.size
        return self

    def move_origin(self, xy: Tuple[float, float]):
        self.origin += np.array(xy)
        return self

    def _translate(self, xy: Any) -> Any:
        arr_xy = np.array(xy, dtype=float)
        origin_broadcast = np.resize(self.origin, arr_xy.shape)
        return (arr_xy + origin_broadcast).tolist()

    def point(
            self,
            xy: Coords,
            fill: _Ink
    ) -> Self:
        self.draw.point(self._translate(xy), fill=fill)
        return self

    def line(
            self,
            xy,
            fill=None,
            width: int = 0,
    ) -> Self:
        self.draw.line(self._translate(xy), fill=fill, width=width)
        return self

    def rectangle(
            self,
            xy: Coords,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        self.draw.rectangle(self._translate(xy), fill=fill, outline=outline, width=width)
        return self

    def circle(
            self,
            xy: Sequence[float],
            radius: float,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        self.draw.circle(self._translate(xy), radius=radius, fill=fill, outline=outline, width=width)
        return self

    def ellipse(
            self,
            xy: Coords,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        self.draw.ellipse(self._translate(xy), fill=fill, outline=outline, width=width)
        return self

    def text(
            self,
            xy: tuple[float, float],
            text,
            fill: _Ink = None,
            font=None,
            anchor: str = None,
            spacing: float = 4,
            align: str = "left",
            direction: str = None,
            features: list[str] = None,
            language: str = None,
            stroke_width: float = 0,
            stroke_fill: _Ink = None,
            embedded_color: bool = False,
            *args: Any,
            **kwargs: Any,
    ) -> Self:
        xy = self._translate(xy)
        self.draw.text(
            xy, text, fill=fill, font=font, anchor=anchor, spacing=spacing, align=align, direction=direction,
            features=features, language=language, stroke_width=stroke_width, stroke_fill=stroke_fill,
            embedded_color=embedded_color, *args, **kwargs
        )
        return self

    def line_abs(
            self,
            xy,
            fill=None,
            width: int = 0,
    ) -> Self:
        arr_xy = np.array(xy, dtype=float)
        origin_broadcast = np.resize(self.im.size, arr_xy.shape)
        xy = (arr_xy * origin_broadcast).tolist()
        self.line(xy, fill=fill, width=width)
        return self

    def rectangle_abs(
            self,
            xy: Coords,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        xy = np.array(xy, dtype=float) * self.im.size
        self.rectangle(xy, fill=fill, outline=outline, width=width)
        return self
