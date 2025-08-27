import hexss

hexss.check_packages('numpy', 'opencv-python', auto_install=True)

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Union, Optional, overload
import numpy as np
import cv2

ArrayLike = np.ndarray
PathLike = Union[str, Path]


def _ensure_uint8_c(img: ArrayLike) -> ArrayLike:
    if img.dtype != np.uint8:
        raise TypeError(f"Expected dtype=uint8, got {img.dtype}")
    return np.ascontiguousarray(img)


@dataclass
class Image:
    img: ArrayLike  # BGR, BGRA, or grayscale (uint8)

    @overload
    def __init__(self, source: ArrayLike) -> None:
        ...

    @overload
    def __init__(self, source: PathLike) -> None:
        ...

    def __init__(self, source: Union[ArrayLike, PathLike]) -> None:
        if isinstance(source, np.ndarray):
            if source.ndim not in (2, 3):
                raise ValueError(f"Unsupported array shape {source.shape}; expected HxW or HxWxC.")
            self.img = _ensure_uint8_c(source)
        elif isinstance(source, (str, Path)):
            loaded = self.from_file(source, flags=cv2.IMREAD_UNCHANGED)
            self.img = loaded.img
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

    @classmethod
    def from_file(cls, path: PathLike, flags: int = cv2.IMREAD_COLOR) -> "Image":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"File does not exist: {p}")
        arr = cv2.imread(str(p), flags)
        if arr is None:
            raise ValueError(f"cv2.imread failed to load: {p}")
        if arr.ndim not in (2, 3):
            raise ValueError(f"Unsupported image shape after load: {arr.shape}")
        return cls(_ensure_uint8_c(arr))

    # --------- Properties ---------
    @property
    def shape(self) -> Tuple[int, int, Optional[int]]:
        if self.img.ndim == 2:
            h, w = self.img.shape
            return h, w, None
        h, w, c = self.img.shape
        return h, w, c

    @property
    def height(self) -> int:
        return self.img.shape[0]

    @property
    def width(self) -> int:
        return self.img.shape[1]

    @property
    def channels(self) -> int:
        return 1 if self.img.ndim == 2 else self.img.shape[2]

    @property
    def size(self) -> Tuple[int, int]:
        """(width, height)"""
        return self.width, self.height

    def copy(self) -> "Image":
        return Image(self.img.copy())

    def save(self, filename: PathLike) -> "Image":
        path = Path(filename)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(path), self.img)
        if not ok:
            raise IOError(f"Failed to write image to: {path}")
        return self

    def show(self, winname: str = "window", wait_ms: int = 0, destroy: bool = False) -> "Image":
        cv2.imshow(winname, self.img)
        cv2.waitKey(wait_ms)
        if destroy:
            cv2.destroyWindow(winname)
        return self

    def __repr__(self) -> str:
        h, w, c = self.shape
        ch = c if c is not None else 1
        return f"<Image {w}x{h}x{ch} dtype={self.img.dtype}>"

    def __str__(self) -> str:
        return repr(self)


if __name__ == "__main__":
    # Example usage
    img = Image(r"C:\Users\c026730\Desktop\Camera mount\img1.png")
    print(img)  # <Image np.ndarray WxHxC dtype=uint8>
    img2 = img.copy()
    img2.show(wait_ms=1000).save("test_copy.jpg")
    print(img2.channels)
