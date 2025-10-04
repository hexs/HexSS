from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union, overload

import hexss

hexss.check_packages('numpy', 'opencv-python', 'Pillow', auto_install=True)

import numpy as np
import cv2
from PIL import Image as PILImage

ArrayLike = np.ndarray
PathLike = Union[str, Path]


def _as_uint8_c(img: ArrayLike) -> ArrayLike:
    """
    Ensure a contiguous uint8 ndarray (view or copy).
    Accepts 2D (H,W) or 3D (H,W,C).
    """
    if not isinstance(img, np.ndarray):
        raise TypeError(f"Expected numpy.ndarray, got {type(img)}")

    if img.dtype != np.uint8:
        raise TypeError(f"Expected dtype=uint8, got {img.dtype}")

    if img.ndim not in (2, 3):
        raise ValueError(f"Unsupported array shape {img.shape}; expected HxW or HxWxC.")

    return np.ascontiguousarray(img)


def _imread_strict(path: PathLike, flags: int) -> ArrayLike:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File does not exist: {p}")

    arr = cv2.imread(str(p), flags)
    if arr is None:
        raise ValueError(f"cv2.imread failed to load: {p}")

    if arr.ndim not in (2, 3):
        raise ValueError(f"Unsupported image shape after load: {arr.shape}")

    return _as_uint8_c(arr)


@dataclass(init=False, repr=False)
class Image:
    """
    Immutable container around a uint8 image in GRAY | BGR | BGRA.
    """
    __slots__ = ("_im", "_publisher")

    _im: ArrayLike  # uint8, 2D or 3D
    _publisher: Optional[object]

    @overload
    def __init__(self, source: ArrayLike) -> None:
        ...

    @overload
    def __init__(self, source: PathLike) -> None:
        ...

    def __init__(self, source: Union[ArrayLike, PathLike]) -> None:
        if isinstance(source, np.ndarray):
            im = _as_uint8_c(source)
        elif isinstance(source, (str, Path)):
            im = _imread_strict(source, flags=cv2.IMREAD_UNCHANGED)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        # Validate channels: gray | BGR | BGRA
        if im.ndim == 3 and im.shape[2] not in (3, 4):
            raise ValueError(
                f"Unsupported channel count {im.shape[2]}; expected 3 (BGR) or 4 (BGRA)."
            )

        object.__setattr__(self, "_im", im)
        object.__setattr__(self, "_publisher", None)

    @classmethod
    def from_file(cls, path: PathLike, flags: int = cv2.IMREAD_COLOR) -> "Image":
        """
        Load via OpenCV with an explicit flag:
          - IMREAD_COLOR -> BGR
          - IMREAD_GRAYSCALE -> GRAY
          - IMREAD_UNCHANGED -> GRAY/BGR/BGRA (keeps alpha)
        """
        return cls(_imread_strict(path, flags))

    @classmethod
    def from_bytes(cls, data: bytes, flags: int = cv2.IMREAD_UNCHANGED) -> "Image":
        """
        Decode from encoded image bytes (PNG/JPEG/etc.)
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("from_bytes expects bytes-like data")
        buf = np.frombuffer(data, dtype=np.uint8)
        im = cv2.imdecode(buf, flags)
        if im is None:
            raise ValueError("cv2.imdecode failed")
        return cls(_as_uint8_c(im))

    @property
    def im(self) -> ArrayLike:
        """Read-only ndarray (uint8). Modify via .copy() if you need to edit."""
        return self._im

    @property
    def shape(self) -> Tuple[int, int, Optional[int]]:
        if self._im.ndim == 2:
            h, w = self._im.shape
            return h, w, None
        h, w, c = self._im.shape
        return h, w, c

    @property
    def height(self) -> int:
        return int(self._im.shape[0])

    @property
    def width(self) -> int:
        return int(self._im.shape[1])

    @property
    def channels(self) -> int:
        return 1 if self._im.ndim == 2 else int(self._im.shape[2])

    @property
    def size(self) -> Tuple[int, int]:
        """(width, height)"""
        return self.width, self.height

    # --------- conversions (explicit, never implicit) ---------
    def to_bgr(self) -> "Image":
        if self.channels == 3:
            return self
        if self.channels == 4:
            return Image(cv2.cvtColor(self._im, cv2.COLOR_BGRA2BGR))
        # gray -> bgr
        return Image(cv2.cvtColor(self._im, cv2.COLOR_GRAY2BGR))

    def to_bgra(self) -> "Image":
        if self.channels == 4:
            return self
        if self.channels == 3:
            return Image(cv2.cvtColor(self._im, cv2.COLOR_BGR2BGRA))
        # gray -> bgra
        return Image(cv2.cvtColor(self._im, cv2.COLOR_GRAY2BGRA))

    def to_gray(self) -> "Image":
        if self.channels == 1:
            return self
        code = cv2.COLOR_BGR2GRAY if self.channels == 3 else cv2.COLOR_BGRA2GRAY
        return Image(cv2.cvtColor(self._im, code))

    def to_rgb(self) -> "Image":
        if self.channels == 3:
            return Image(cv2.cvtColor(self._im, cv2.COLOR_BGR2RGB))
        if self.channels == 4:
            return Image(cv2.cvtColor(self._im, cv2.COLOR_BGRA2RGB))
        # gray -> rgb
        return Image(cv2.cvtColor(self._im, cv2.COLOR_GRAY2RGB))

    # --------- utilities ---------
    def copy(self) -> "Image":
        return Image(self._im.copy())

    def save(self, filename: PathLike) -> "Image":
        path = Path(filename)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        ok = cv2.imwrite(str(path), self._im)
        if not ok:
            raise IOError(f"Failed to write image to: {path}")
        return self

    def show(self, title: Optional[str] = None) -> "Image":
        PILImage.fromarray(self._im).show(title)
        return self

    def publish(self, winname: str = "window", **kwargs) -> "Image":
        if self._publisher is None:
            from hexss.frame_publisher import FramePublisher
            self._publisher: FramePublisher = FramePublisher(open_browser=True, jpeg_quality=100, **kwargs)

        self._publisher.show(winname, self._im)
        return self

    # Allow np.array(img) to get the underlying buffer without copying when possible.
    def __array__(self, dtype=None):
        arr = self._im
        return arr.astype(dtype, copy=False) if dtype is not None else arr

    def __repr__(self) -> str:
        h, w, c = self.shape
        ch = c if c is not None else 1
        return f"<Image {w}x{h}x{ch}"


if __name__ == "__main__":
    # Example usage
    rng = np.random.default_rng(123)
    img = rng.integers(0, 256, size=(1080, 1920, 3), dtype=np.uint8)
    im = Image(img)
    print(im)  # <Image 1920x1080x3>
    im.show("im").save("copy_im.jpg")
    print(im.channels)  # 3

    copy_im = Image("copy_im.jpg")
    copy_im.show("copy_im")

    while True:
        img = rng.integers(0, 256, size=(1080, 1920, 3), dtype=np.uint8)
        Image(img).publish("im")
