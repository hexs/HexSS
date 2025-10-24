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

_Ink = Union[float, Tuple[int, ...], str]
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
        elif isinstance(source, str) and source.startswith(("http://", "https://")):
            self.image = self._from_url(source)
        elif isinstance(source, (Path, str)):
            if Path(source).is_file():
                self.image = self._from_file(source)
            else:
                raise FileNotFoundError(f"File does not exist: {source}")
        elif isinstance(source, bytes):
            self.image = self._from_bytes(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        self._publisher = None

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

    def pil(self):
        return self.image

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

    def shift(self, dx: int, dy: int) -> Self:
        """
        Shift the image by (dx, dy) pixels.
        Positive dx -> shift right
        Positive dy -> shift down
        """
        # Affine transform matrix for translation
        matrix = (1, 0, dx,  # x' = x + dx
                  0, 1, dy)  # y' = y + dy
        self.image = self.image.transform(self.image.size, PILImage.AFFINE, matrix)
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
            box = Box(size=self.size, xyxy=xyxy, xywh=xywh, xyxyn=xyxyn, xywhn=xywhn, points=points, pointsn=pointsn)
        box.move(*shift, normalized=False)
        if box.type == 'polygon':
            img = self.numpy()
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [box.points.astype(np.int32)], 255)
            masked = cv2.bitwise_and(img, img, mask=mask)
            x, y, w, h = cv2.boundingRect(box.points.astype(np.int32))
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

    def best_match_location(
            self,
            template_im: "Image",
            *,
            # --- ROI selectors (choose at most one) ---
            xyxy: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xywh: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xyxyn: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            xywhn: Optional[Union[Tuple[float, float, float, float], List[float], np.ndarray]] = None,
            # --- options ---
            gray: bool = False,
            canny: bool = False,
            blur_ksize: int = 3,
            method: int = cv2.TM_CCOEFF_NORMED,
    ) -> Tuple[Optional[np.ndarray], Optional[float]]:

        # Source array (BGR)
        src_bgr = self.numpy()

        # Determine ROI (absolute integers, clipped to image)
        h_s, w_s = src_bgr.shape[:2]
        if any(v is not None for v in (xyxy, xywh, xyxyn, xywhn)):
            x1, y1, x2, y2 = self.to_xyxy(xyxy=xyxy, xywh=xywh, xyxyn=xyxyn, xywhn=xywhn)
            x1 = max(0, min(int(round(x1)), w_s - 1))
            y1 = max(0, min(int(round(y1)), h_s - 1))
            x2 = max(x1 + 1, min(int(round(x2)), w_s))
            y2 = max(y1 + 1, min(int(round(y2)), h_s))
            roi_x, roi_y, roi_w, roi_h = x1, y1, x2 - x1, y2 - y1
            src_roi = src_bgr[y1:y2, x1:x2]
        else:
            roi_x, roi_y, roi_w, roi_h = 0, 0, w_s, h_s
            src_roi = src_bgr

        # Template array (BGR)
        tpl_bgr = template_im.numpy()

        # Convert to working images
        if gray:
            g_s = cv2.cvtColor(src_roi, cv2.COLOR_BGR2GRAY)
            g_t = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
        else:
            g_s = src_roi
            g_t = tpl_bgr

        # Optional blur
        if blur_ksize:
            g_s = cv2.GaussianBlur(g_s, (blur_ksize, blur_ksize), 0)
            g_t = cv2.GaussianBlur(g_t, (blur_ksize, blur_ksize), 0)

        # Optional edges
        if canny:
            e_s = cv2.Canny(g_s, 50, 150)
            e_t = cv2.Canny(g_t, 50, 150)
            kernel = np.ones((3, 3), np.uint8)
            e_s = cv2.dilate(e_s, kernel, iterations=1)
            e_t = cv2.dilate(e_t, kernel, iterations=1)
            work_s, work_t = e_s, e_t
        else:
            work_s, work_t = g_s, g_t

        h_t, w_t = work_t.shape[:2]
        h_r, w_r = work_s.shape[:2]

        # sanity checks
        if h_t < 5 or w_t < 5 or h_t >= h_r or w_t >= w_r:
            return (None, None), None

        # Template matching within ROI
        res = cv2.matchTemplate(work_s, work_t, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # Choose best (for TM_CCOEFF_NORMED higher is better)
        if method in (cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED):
            tl = min_loc
            score = 1.0 - float(min_val)  # convert to "higher is better"
        else:
            tl = max_loc
            score = float(max_val)

        # Convert top-left + center back to full-image coords
        tl_abs = (tl[0] + roi_x, tl[1] + roi_y)
        center = (tl_abs[0] + w_t / 2.0, tl_abs[1] + h_t / 2.0)
        return np.array(center, dtype=np.float32), score

    def align_image(
            self,
            pts_src: np.ndarray, pts_dst: np.ndarray,

    ) -> Dict[str, Any]:
        """
        Align `image` (source) to match `pts_dst` using corresponding points (pts_src -> pts_dst).

        Notes:
            - If 2 points: uses Similarity (rotation + uniform scale + translation)
            - If 3 points: uses exact Affine transform
            - If >=4 points: uses Homography with RANSAC
        """

        def _triangle_area(p0, p1, p2) -> float:
            p0 = np.asarray(p0, dtype=np.float64)
            p1 = np.asarray(p1, dtype=np.float64)
            p2 = np.asarray(p2, dtype=np.float64)
            return abs(0.5 * np.cross(p1 - p0, p2 - p0))

        def _rmse_points(p_pred: np.ndarray, p_true: np.ndarray) -> float:
            p_pred = np.asarray(p_pred, dtype=np.float64)
            p_true = np.asarray(p_true, dtype=np.float64)
            return float(np.sqrt(np.mean((p_pred - p_true) ** 2)))

        pts_src = np.asarray(pts_src, dtype=np.float32)
        pts_dst = np.asarray(pts_dst, dtype=np.float32)
        assert pts_src.shape == pts_dst.shape, "Source and destination points must have same shape"
        assert pts_src.ndim == 2 and pts_src.shape[1] == 2, "Points must have shape (N, 2)"
        N = pts_src.shape[0]
        assert N >= 2, "Need at least 2 points"

        w, h = self.size
        out_w, out_h = w, h

        method = None
        M = None
        inliers = None

        if N == 2:
            # Similarity (rotation + uniform scale + translation)
            method = "estimateAffinePartial2D (Similarity)"
            M, inliers = cv2.estimateAffinePartial2D(pts_src, pts_dst)  # 2x3
            if M is None:
                raise RuntimeError("Failed to compute estimateAffinePartial2D, check point order/accuracy")
            self.image = Image(cv2.warpAffine(self.numpy(), M, (out_w, out_h), flags=cv2.INTER_LINEAR))

            pts_src_h = np.hstack([pts_src, np.ones((N, 1), dtype=np.float32)])  # (N,3)
            pts_src_warp = (M @ pts_src_h.T).T  # (N,2)
            rmse = _rmse_points(pts_src_warp, pts_dst)

        elif N == 3:
            # Exact Affine
            area_src = _triangle_area(pts_src[0], pts_src[1], pts_src[2])
            area_dst = _triangle_area(pts_dst[0], pts_dst[1], pts_dst[2])
            if area_src < 1e-6 or area_dst < 1e-6:
                raise ValueError("3 points (src/dst) are collinear, cannot compute stable affine")

            method = "getAffineTransform (Affine exact)"
            M = cv2.getAffineTransform(pts_src, pts_dst)  # 2x3
            self.image = Image(cv2.warpAffine(self.numpy(), M, (out_w, out_h), flags=cv2.INTER_LINEAR))

            pts_src_h = np.hstack([pts_src, np.ones((N, 1), dtype=np.float32)])
            pts_src_warp = (M @ pts_src_h.T).T
            rmse = _rmse_points(pts_src_warp, pts_dst)

        else:  # N >= 4
            # Homography + RANSAC
            method = "findHomography (Perspective, RANSAC)"
            H, mask = cv2.findHomography(
                pts_src, pts_dst,
                method=cv2.RANSAC,
                ransacReprojThreshold=3.0,
                maxIters=2000,
                confidence=0.995
            )
            if H is None:
                raise RuntimeError("Failed to compute findHomography, check points or quality")
            M = H
            self.image = Image(cv2.warpPerspective(self.numpy(), H, (out_w, out_h), flags=cv2.INTER_LINEAR))
            inliers = mask

            pts_src_h = np.hstack([pts_src, np.ones((N, 1), dtype=np.float32)])  # (N,3)
            warp_h = (H @ pts_src_h.T).T  # (N,3)
            pts_src_warp = warp_h[:, :2] / warp_h[:, 2:3]
            rmse = _rmse_points(pts_src_warp, pts_dst)

        info = {
            "method": method,
            "matrix": M,
            "rmse": rmse,
            "inliers": inliers,
            "used_points": N,
            "output_size": (out_w, out_h),
        }
        return info

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

    def publish(self, winname: str = "window", **kwargs):
        if self._publisher is None:
            from hexss.frame_publisher import FramePublisher
            self._publisher: FramePublisher = FramePublisher(open_browser=True, jpeg_quality=100, **kwargs)

        self._publisher.show(winname, self.pil())

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

    def circle(
            self,
            xy: Sequence[float],
            radius: float,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
    ) -> Self:
        self.draw().circle(xy, radius=radius, fill=fill, outline=outline, width=width)
        return self

    def rectangle(
            self,
            xy: Union[Coords, Box] = None,
            fill: _Ink = None,
            outline: _Ink = None,
            width: int = 1,
            xyxy=None,
            xywh=None,
            xyxyn=None,
            xywhn=None
    ) -> Self:
        self.draw().rectangle(
            xy=xy, fill=fill, outline=outline, width=width,
            xyxy=xyxy, xywhn=xywhn, xyxyn=xyxyn, xywh=xywh
        )
        return self


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
            if not xy._size:
                xy.set_size(self.im.size)
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


if __name__ == '__main__':
    img = Image(r"C:\PythonProjects\auto_inspection_data__QM7-3474\img_full\250828 123928 - Copy.png")
    img2 = Image(r"C:\PythonProjects\auto_inspection_data__QM7-3474\img_full\250909 141810.png")

    marks = {
        'm1': {"xywhn": [0.057543, 0.048778, 0.016425, 0.024453], "k": 3},
        'm2': {"xywhn": [0.340268, 0.063564, 0.016587, 0.026718], "k": 3},
        'm3': {"xywhn": [0.047226, 0.778535, 0.017604, 0.025659], "k": 3},
        'm4': {"xywhn": [0.340291, 0.778185, 0.020316, 0.028431], "k": 3},
    }
    for mark in marks.values():
        box = Box(xywhn=mark['xywhn'])
        box.set_size(img.size)
        mark['im'] = img.crop(box)
        scale_xywhn = box.scale(mark.get('k', 3)).xywhn
        mark['scale_xywhn'] = scale_xywhn

    pts_src = []
    pts_dst = []
    for mark in marks.values():
        xywhn_mark_area = mark['scale_xywhn']
        mark_im = mark['im']
        xy, score = img2.best_match_location(mark_im, xywhn=xywhn_mark_area)
        pts_dst.append(Box(size=img2.size, xywhn=mark['xywhn']).xy)
        pts_src.append(xy)
        print("location:", xy, "score:", score)
        img2.rectangle(xywhn=xywhn_mark_area, outline=(255, 0, 0), width=5)
        if xy is not None:
            img2.rectangle(xywh=(*xy, *mark_im.size), outline=(255, 0, 0), width=5)

    img2.align_image(pts_src, pts_dst)
    img2.show()
