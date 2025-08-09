from pathlib import Path
from typing import Union, Optional, Tuple, List, Self, IO, Type, Literal, Any, Sequence, Dict
from io import BytesIO

import hexss
from hexss import json_load
from hexss.box import Box

hexss.check_packages('numpy', 'opencv-python', 'requests', 'pillow', auto_install=True)

import numpy as np
import cv2
import requests
from PIL._typing import Coords
from PIL import Image as PILImage
from PIL import ImageDraw as PILImageDraw
from PIL import ImageFilter, ImageGrab, ImageWin, ImageFont, ImageEnhance
from PIL.Image import Transpose, Transform, Resampling, Dither, Palette, Quantize, SupportsArrayInterface
from PIL.ImageDraw import _Ink

Array2 = np.ndarray
Coord4 = Union[Tuple[float, float, float, float], Sequence[float]]


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
        elif isinstance(source, (Path, str)):
            if Path(source).is_file():
                self.image = self._from_file(source)
            else:
                raise FileNotFoundError(f"File does not exist: {source}")
        elif isinstance(source, str) and source.startswith(("http://", "https://")):
            self.image = self._from_url(source)
        elif isinstance(source, bytes):
            self.image = self._from_bytes(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        self.boxes = [],
        '''
        self.boxes = [
            Box(name='x1', xywhn=xywhn, pointn=pointn),
            Box(name='x2', xywhn=xywhn, pointn=pointn),
        ]
        '''
        self.classification = None
        self.detections = None

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

    def to_xyxy(
            self,
            xyxy: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xywh: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xyxyn: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xywhn: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None
    ) -> Tuple[float, float, float, float]:
        """
        Converts various bounding box formats to (x1, y1, x2, y2) format.

        Args:
            xyxy: (x1, y1, x2, y2) absolute coordinates.
            xywh: (x_center, y_center, width, height) absolute coordinates.
            xyxyn: (x1, y1, x2, y2) normalized [0,1] coordinates.
            xywhn: (x_center, y_center, width, height) normalized [0,1] coordinates.

        Returns:
            (x1, y1, x2, y2) absolute coordinates.

        Raises:
            ValueError: If not exactly one format is provided or if input is invalid.
        """

        # inputs = [xyxy, xywh, xyxyn, xywhn]
        # provided = [v is not None for v in inputs]

        # if sum(provided) != 1:
        #     raise ValueError("Exactly one of xyxy, xywh, xyxyn, or xywhn must be provided.")

        def as_tuple(val):
            if isinstance(val, np.ndarray):
                val = val.flatten()
                if val.shape[0] != 4:
                    raise ValueError("Input array must be of shape (4,) or (4,1)")
                return tuple(map(float, val))
            elif isinstance(val, (list, tuple)):
                if len(val) != 4:
                    raise ValueError("Input must be a tuple or list of length 4")
                return tuple(map(float, val))
            else:
                raise ValueError("Input must be a tuple, list, or numpy ndarray of length 4")

        if xyxy is not None:
            result = as_tuple(xyxy)
        elif xywh is not None:
            xc, yc, w, h = as_tuple(xywh)
            result = (xc - w / 2, yc - h / 2, xc + w / 2, yc + h / 2)
        elif xyxyn is not None:
            x1n, y1n, x2n, y2n = as_tuple(xyxyn)
            w, h = self.size
            result = (x1n * w, y1n * h, x2n * w, y2n * h)
        elif xywhn is not None:
            xcn, ycn, wn, hn = as_tuple(xywhn)
            w, h = self.size
            result = (
                xcn * w - wn * w / 2,
                ycn * h - hn * h / 2,
                xcn * w + wn * w / 2,
                ycn * h + hn * h / 2,
            )
        else:
            raise RuntimeError("Unknown error in to_xyxy")

        return result

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
        self.image = inverted
        return self

    def filter(self, filter: Union[ImageFilter.Filter, Type[ImageFilter.Filter]]) -> Self:
        self.image = self.image.filter(filter)
        return self

    def convert(self, mode: str, **kwargs) -> Self:
        if self.mode == 'RGBA' and mode == 'RGB':
            bg = PILImage.new('RGB', self.size, (255, 255, 255))
            bg.paste(self.image, mask=self.image.split()[3])
            self.image = bg
        self.image = self.image.convert(mode, **kwargs)
        return self

    def rotate(
            self,
            angle: float,
            resample: Resampling = Resampling.NEAREST,
            expand: Union[int, bool] = False,
            center: Tuple[float, float] | None = None,
            translate: Tuple[int, int] | None = None,
            fillcolor: Union[float, Tuple[float, ...], str] | None = None,
    ) -> Self:
        self.image = self.image.rotate(angle, resample, expand, center, translate, fillcolor)
        return self

    def transpose(self, method: PILImage.Transpose) -> Self:
        self.image = self.image.transpose(method)
        return self

    def crop(
            self,
            box: Tuple[float, float, float, float] | None = None,
            xyxy: Tuple[float, float, float, float] | np.ndarray = None,
            xywh: Tuple[float, float, float, float] | np.ndarray = None,
            xyxyn: Tuple[float, float, float, float] | np.ndarray = None,
            xywhn: Tuple[float, float, float, float] | np.ndarray = None,
            points: Optional[Sequence[Tuple[float, float]]] = None,
            pointsn: Optional[Sequence[Tuple[float, float]]] = None,
            shift: Tuple[float, float] = (0, 0),
    ) -> Self:
        if box is not None:
            if not isinstance(box, Box):
                return Image(self.image.crop(box))
        else:
            box = Box(self.size, xyxy=xyxy, xywh=xywh, xyxyn=xyxyn, xywhn=xywhn, points=points, pointsn=pointsn)
        box.move(*shift, normalized=False)
        if box.type == 'polygon':
            img = self.numpy()
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [box.points_int32()], 255)
            masked = cv2.bitwise_and(img, img, mask=mask)
            x, y, w, h = cv2.boundingRect(box.points_int32())
            cropped = masked[y:y + h, x:x + w]
            return Image(cropped)
        elif box.type == 'box':
            return Image(self.image.crop(box.xyxy))

    def brightness(self, factor):
        '''
        (factor > 1), e.g., 1.5 means 50% brighter
        (factor < 1), e.g., 0.5 means 50% darker
        '''
        if factor == 1.0:
            return self
        enhancer = ImageEnhance.Brightness(self.image)
        self.image = enhancer.enhance(factor)
        return self

    def contrast(self, factor):
        '''
        (factor > 1), e.g., 2.0 means double the contrast
        (factor < 1), e.g., 0.5 means half the contrast
        '''
        if factor == 1.0:
            return self
        enhancer = ImageEnhance.Contrast(self.image)
        self.image = enhancer.enhance(factor)
        return self

    def sharpness(self, factor):
        '''
        (factor > 1), e.g., 2.0 means double the sharpness
        (factor < 1), e.g., 0.0 means a blurred image
        '''
        if factor == 1.0:
            return self
        enhancer = ImageEnhance.Sharpness(self.image)
        self.image = enhancer.enhance(factor)
        return self

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
        self.image = self.image.resize(size=size, resample=resample, box=box, reducing_gap=reducing_gap)
        return self

    def copy(self) -> Self:
        return Image(self.image.copy())

    def save(self, fp: Union[str, Path, IO[bytes]], format: Optional[str] = None, **params: Any) -> Self:
        if isinstance(fp, str) or isinstance(fp, Path):
            Path(fp).parent.mkdir(parents=True, exist_ok=True)
        self.image.save(fp, format, **params)
        return self

    def show(self, title: Optional[str] = None) -> Self:
        self.image.show(title=title)
        return self

    def detect(self, model):
        self.detections = model.detect(self)
        return self.detections

    def classify(self, model):
        self.classification = model.classify(self)
        return self.classification

    def __repr__(self) -> str:
        name = self.image.__class__.__name__
        return f"<Image {name} mode={self.mode} size={self.size[0]}x{self.size[1]}>"

    def draw(self, origin: Union[str, Tuple[float, float]] = 'topleft') -> "ImageDraw":
        return ImageDraw(self, origin)

    def draw_box(self, box: Box) -> None:
        if box.size is None:
            box.set_size(self.size)
        draw = self.draw()

        if box.type == 'polygon':
            draw.polygon(box, outline=box.color, width=box.width)
            draw.text(xy=box.points[0], text=box.name, font=box.font,
                      fill=box.text_color, stroke_width=box.width, stroke_fill=box.text_stroke_color)
        elif box.type == 'box':
            draw.rectangle(box, outline=box.color, width=box.width)
            draw.text(xyn=box.x1y1n, text=box.name, font=box.font,
                      fill=box.text_color, stroke_width=box.width, stroke_fill=box.text_stroke_color)


class ImageDraw:
    def __init__(self, im: Image, origin: Union[str, Tuple[float, float]] = 'topleft') -> None:
        self.im = im
        self.draw = PILImageDraw.Draw(self.im.image)
        self.origin = np.zeros(2, dtype=float)
        self.set_origin(origin)

    def set_origin(self, origin: str | tuple[float, float] | list[float]) -> Self:
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

    def set_abs_origin(self, abs_origin: tuple[float, float] | list[float]) -> Self:
        self.origin = np.array(abs_origin) * self.im.size
        return self

    def move_origin(self, xy: tuple[float, float] | list[float]):
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
            xy=None,
            fill=None,
            width: int = 0,
            xyxy=None,
            xyxyn=None,
    ) -> Self:
        xy = xy or self.im.to_xyxy(xyxy, xyxyn)
        self.draw.line(self._translate(xy), fill=fill, width=width)
        return self

    def rectangle(
            self,
            xy: Union[Coords, Box] = None,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
            xyxy: tuple[float, float, float, float] | list[float] | np.ndarray | None = None,
            xywh: tuple[float, float, float, float] | list[float] | np.ndarray | None = None,
            xyxyn: tuple[float, float, float, float] | list[float] | np.ndarray | None = None,
            xywhn: tuple[float, float, float, float] | list[float] | np.ndarray | None = None,
    ) -> Self:
        if isinstance(xy, Box):
            xy = xy.xyxy.tolist()
        if xy is None:
            xy = self.im.to_xyxy(xyxy, xywh, xyxyn, xywhn)
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

    def polygon(
            self,
            xy: Union[Sequence[float], Box],
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        if isinstance(xy, Box):
            xy = xy.points
        xy = [tuple(map(int, pt)) for pt in self._translate(xy)]
        self.draw.polygon(xy, fill=fill, outline=outline, width=width)
        return self

    def text(
            self,
            xy: tuple[float, float] | list[float] | None = None,
            text='',
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
            xyn=None,
            *args: Any,
            **kwargs: Any,
    ) -> Self:
        if xyn is not None:
            xy = np.array(xyn) * self.im.size
        xy = self._translate(xy)
        self.draw.text(
            xy, text, fill=fill, font=font, anchor=anchor, spacing=spacing, align=align, direction=direction,
            features=features, language=language, stroke_width=stroke_width, stroke_fill=stroke_fill,
            embedded_color=embedded_color, *args, **kwargs
        )
        return self


class Boxes:
    def __init__(
            self,
            size: Optional[Tuple[float, float]] = None,
            image: Image = None,
            boxes: Optional[Dict[str, Box]] = None
    ) -> None:
        if size is not None:
            self.width, self.height = map(float, size)
            self.image = None
        if image is not None:
            self.width, self.height = image.size
            self.image = image
        self.boxes = boxes or {}

    def add(
            self,
            name: str,
            *,
            xywh: Optional[Coord4] = None,
            xyxy: Optional[Coord4] = None,
            xywhn: Optional[Coord4] = None,
            xyxyn: Optional[Coord4] = None,
            points: Optional[Sequence[Tuple[float, float]]] = None,
            pointsn: Optional[Sequence[Tuple[float, float]]] = None,
            xy: Optional[Tuple[float, float]] = None,
            xyn: Optional[Tuple[float, float]] = None,
            x1y1: Optional[Tuple[float, float]] = None,
            x1y1n: Optional[Tuple[float, float]] = None,
            wh: Optional[Tuple[float, float]] = None,
            whn: Optional[Tuple[float, float]] = None, ) -> None:
        self.boxes[name] = Box(
            (self.width, self.height),
            xywh=xywh, xyxy=xyxy, xywhn=xywhn, xyxyn=xyxyn, points=points, pointsn=pointsn, xy=xy,
            xyn=xyn, x1y1=x1y1, x1y1n=x1y1n, wh=wh, whn=whn
        )
