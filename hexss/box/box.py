from __future__ import annotations
from typing import Optional, Sequence, Tuple, Union, List
import numpy as np

Coord2 = Union[Tuple[float, float], List[float], Sequence[float]]
Coord4 = Union[Tuple[float, float, float, float], List[float], Sequence[float]]
PointSeq = Sequence[Tuple[float, float]]
Array2 = np.ndarray


def to_xyxy(boxes: np.ndarray, out: np.ndarray = None) -> np.ndarray:
    """
    Convert [cx, cy, w, h] -> [x1, y1, x2, y2] for any shape (..., 4).
    """
    a = np.asarray(boxes, dtype=np.float64)
    if a.shape[-1] != 4:
        raise ValueError("Expected shape (..., 4) for boxes.")
    if out is None:
        out = np.empty_like(a)
    cx, cy, w, h = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    hw, hh = w * 0.5, h * 0.5
    out[..., 0] = cx - hw
    out[..., 1] = cy - hh
    out[..., 2] = cx + hw
    out[..., 3] = cy + hh
    return out


def to_xywh(boxes: np.ndarray, out: np.ndarray = None) -> np.ndarray:
    """
    Convert [x1, y1, x2, y2] -> [cx, cy, w, h] for any shape (..., 4).
    Handles reversed corners safely.
    """
    a = np.asarray(boxes, dtype=np.float64)
    if a.shape[-1] != 4:
        raise ValueError("Expected shape (..., 4) for boxes.")
    if out is None:
        out = np.empty_like(a)
    x1, y1, x2, y2 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w = np.abs(x2 - x1)
    h = np.abs(y2 - y1)
    x_min = np.minimum(x1, x2)
    y_min = np.minimum(y1, y2)
    out[..., 0] = x_min + w * 0.5
    out[..., 1] = y_min + h * 0.5
    out[..., 2] = w
    out[..., 3] = h
    return out


class Box:
    """
    Unified box/polygon holder with lazy conversions between:
      - xywh / xyxy  (absolute pixels)
      - xywhn / xyxyn (normalized, relative to size)
      - points / pointsn (polygon absolute/normalized)

    Authoritative storage is whichever form was provided first.
    If normalized data is provided but no size, absolute properties
    requiring pixels will raise until you set size.
    """

    # -------- construction --------
    def __init__(
            self,
            size: Optional[Coord2] = None,
            xywhn: Optional[Coord4] = None,
            xywh: Optional[Coord4] = None,
            xyxyn: Optional[Coord4] = None,
            xyxy: Optional[Coord4] = None,
            points: Optional[PointSeq] = None,
            pointsn: Optional[PointSeq] = None
    ):
        self._size: Optional[np.ndarray] = (
            np.asarray(size, dtype=np.float64) if size is not None else None
        )
        self._kind: Optional[str] = None  # "box" | "polygon"

        self._xywhn: Optional[np.ndarray] = None
        self._xywh: Optional[np.ndarray] = None
        self._xyxyn: Optional[np.ndarray] = None
        self._xyxy: Optional[np.ndarray] = None
        self._pointsn: Optional[np.ndarray] = None  # shape (N,2)
        self._points: Optional[np.ndarray] = None

        self._setup(xywhn, xywh, xyxyn, xyxy, points, pointsn)

    def _setup(self, xywhn, xywh, xyxyn, xyxy, points, pointsn):
        if xywhn is not None:
            self._xywhn = np.asarray(xywhn, dtype=np.float64)
            self._xyxyn = to_xyxy(self._xywhn)
            self._kind = "box"
            return

        if xyxyn is not None:
            self._xyxyn = np.asarray(xyxyn, dtype=np.float64)
            self._xywhn = to_xywh(self._xyxyn)
            self._kind = "box"
            return

        if xywh is not None:
            self._xywh = np.asarray(xywh, dtype=np.float64)
            self._xyxy = to_xyxy(self._xywh)
            self._kind = "box"
            return

        if xyxy is not None:
            self._xyxy = np.asarray(xyxy, dtype=np.float64)
            self._xywh = to_xywh(self._xyxy)
            self._kind = "box"
            return

        if pointsn is not None:
            p = np.asarray(pointsn, dtype=np.float64)
            if p.ndim != 2 or p.shape[1] != 2:
                raise ValueError("pointsn must have shape (N, 2).")
            self._pointsn = p
            self._set_from_pointsn(p)
            self._kind = "polygon"
            return

        if points is not None:
            p = np.asarray(points, dtype=np.float64)
            if p.ndim != 2 or p.shape[1] != 2:
                raise ValueError("points must have shape (N, 2).")
            self._points = p
            self._set_from_points(p)
            self._kind = "polygon"
            return

        raise ValueError("Provide one of: xywhn, xywh, xyxyn, xyxy, points, pointsn.")

    @staticmethod
    def _require(value, msg: str):
        if value is None:
            raise AttributeError(msg)
        return value

    def _require_size(self) -> np.ndarray:
        return self._require(self._size, "Unknown size; set size first.")

    def _set_from_pointsn(self, pts: Array2) -> None:
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self._xywhn = np.array([cx, cy, w, h], dtype=np.float64)
        self._xyxyn = to_xyxy(self._xywhn)

    def _set_from_points(self, pts: Array2) -> None:
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self._xywh = np.array([cx, cy, w, h], dtype=np.float64)
        self._xyxy = to_xyxy(self._xywh)

    def set_size(self, size: Coord2) -> "Box":
        self._size = np.asarray(size, dtype=np.float64)
        return self

    def move(self, dx: float, dy: float, *, normalized: bool = False) -> "Box":
        """
        Translate the geometry.
        - If normalized=True, interpret dx, dy in normalized units.
        - Otherwise in absolute pixels.
        Centers and polygon points move together.
        """
        if self._kind == "box":
            if normalized:
                self._xywhn = self.xywhn.copy()
                self._xywhn[:2] += [dx, dy]
                self._xyxyn = to_xyxy(self._xywhn)
                # invalidate absolute (they’ll be recomputed on demand)
                self._xywh = None
                self._xyxy = None
            else:
                self._xywh = self.xywh.copy()
                self._xywh[:2] += [dx, dy]
                self._xyxy = to_xyxy(self._xywh)
                # invalidate normalized
                self._xywhn = None
                self._xyxyn = None
        else:  # polygon
            if normalized:
                self._pointsn = self.pointsn.copy()
                self._pointsn += [dx, dy]
                self._xywhn = None
                self._xyxyn = None
                # absolute invalid
                self._points = None
                self._xywh = None
                self._xyxy = None
            else:
                self._points = self.points.copy()
                self._points += [dx, dy]
                self._xywh = None
                self._xyxy = None
                # normalized invalid
                self._pointsn = None
                self._xywhn = None
                self._xyxyn = None
        return self

    def scale(self, fx: float, fy: Optional[float] = None, *, normalized: bool = True) -> "Box":
        """
        Scale *about the center* (for boxes) or polygon centroid.
        - If normalized=True (default), scaling occurs in normalized space
          (no size needed), e.g. w,h *= f. Your example hits this path.
        - If normalized=False, scaling occurs in absolute pixels.

        For polygons, points are scaled about their centroid.
        """
        if fy is None:
            fy = fx

        if self._kind == "box":
            if normalized:
                b = self.xywhn.copy()
                # scale around center: cx,cy fixed; w,h multiplied
                b[2] *= fx
                b[3] *= fy
                self._xywhn = b
                self._xyxyn = to_xyxy(self._xywhn)
                # absolute invalid (recompute when asked)
                self._xywh = None
                self._xyxy = None
            else:
                b = self.xywh.copy()
                b[2] *= fx
                b[3] *= fy
                self._xywh = b
                self._xyxy = to_xyxy(self._xywh)
                # normalized invalid
                self._xywhn = None
                self._xyxyn = None
        else:  # polygon
            if normalized:
                pts = self.pointsn.copy()
                c = pts.mean(axis=0, keepdims=True)
                pts = (pts - c) * np.array([fx, fy]) + c
                self._pointsn = pts
                # invalidate derived
                self._points = None
                self._xywhn = None
                self._xyxyn = None
                self._xywh = None
                self._xyxy = None
            else:
                pts = self.points.copy()
                c = pts.mean(axis=0, keepdims=True)
                pts = (pts - c) * np.array([fx, fy]) + c
                self._points = pts
                # invalidate derived
                self._pointsn = None
                self._xywhn = None
                self._xyxyn = None
                self._xywh = None
                self._xyxy = None
        return self

    def points_int32(self) -> np.ndarray:
        return self.points.astype(np.int32)

    @property
    def type(self) -> Optional[str]:
        return self._kind

    @property
    def size(self) -> np.ndarray:
        return self._require_size()

    @property
    def xywhn(self) -> np.ndarray:
        if self._xywhn is not None:
            return self._xywhn
        if self._xywh is not None:
            s = self.size
            return self._xywh / np.array([s[0], s[1], s[0], s[1]])
        if self._pointsn is not None:
            self._set_from_pointsn(self._pointsn)
            return self._xywhn
        if self._points is not None:
            s = self.size
            self._pointsn = self._points / s
            self._set_from_pointsn(self._pointsn)
            return self._xywhn
        raise AttributeError("No geometry available to compute xywhn.")

    @property
    def xyxyn(self) -> np.ndarray:
        if self._xyxyn is not None:
            return self._xyxyn
        return to_xyxy(self.xywhn)

    @property
    def xywh(self) -> np.ndarray:
        if self._xywh is not None:
            return self._xywh
        s = self.size
        return self.xywhn * np.array([s[0], s[1], s[0], s[1]])

    @property
    def xyxy(self) -> np.ndarray:
        if self._xyxy is not None:
            return self._xyxy
        return to_xyxy(self.xywh)

    @property
    def pointsn(self) -> np.ndarray:
        if self._pointsn is not None:
            return self._pointsn
        if self._points is not None:
            s = self.size
            return self._points / s
        # derive from box if polygon was not the authoritative kind
        # represent rectangle corners in normalized coords
        x1, y1, x2, y2 = self.xyxyn
        return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float64)

    @property
    def points(self) -> np.ndarray:
        if self._points is not None:
            return self._points
        s = self.size
        return self.pointsn * s

    @property
    def x1y1n(self):
        return self.xyxyn[0:2]

    @property
    def x1y2n(self):
        return self.xyxyn[[0, 3]]

    @property
    def x2y1n(self):
        return self.xyxyn[[2, 1]]

    @property
    def x2y2n(self):
        return self.xyxyn[2:4]

    @property
    def x1y1(self):
        return self.xyxy[0:2]

    @property
    def x1y2(self):
        return self.xyxy[[0, 3]]

    @property
    def x2y1(self):
        return self.xyxy[[2, 1]]

    @property
    def x2y2(self):
        return self.xyxy[2:4]

    @property
    def xyn(self):
        return self.xywhn[0:2]

    @property
    def xy(self):
        return self.xywh[0:2]

    # --- utils ---
    def copy(self) -> "Box":
        return Box(
            size=None if self._size is None else self._size.copy(),
            xywhn=self._xywhn.copy() if self._xywhn is not None else None,
            xywh=self._xywh.copy() if self._xywh is not None else None,
            xyxyn=self._xyxyn.copy() if self._xyxyn is not None else None,
            xyxy=self._xyxy.copy() if self._xyxy is not None else None,
            points=self._points.copy() if self._points is not None else None,
            pointsn=self._pointsn.copy() if self._pointsn is not None else None,
        )

    def asdict(self) -> dict:
        return {
            "type": self._kind,
            "size": None if self._size is None else self._size.tolist(),
            "xywhn": self._xywhn.tolist() if self._xywhn is not None else None,
            "xywh": self._xywh.tolist() if self._xywh is not None else None,
            "xyxyn": self._xyxyn.tolist() if self._xyxyn is not None else None,
            "xyxy": self._xyxy.tolist() if self._xyxy is not None else None,
            "pointsn": None if self._pointsn is None else self._pointsn.tolist(),
            "points": None if self._points is None else self._points.tolist(),
        }

    def __repr__(self) -> str:
        return f"<Box type={self._kind} size={None if self._size is None else tuple(self._size)}>"


def test_1():
    def show(box):
        try:
            print('xywhn  ', box.xywhn)
        except AttributeError as e:
            print('xywhn  ', e)
        try:
            print('xywh   ', box.xywh)
        except AttributeError as e:
            print('xywh   ', e)
        try:
            print('xyxyn  ', box.xyxyn)
        except AttributeError as e:
            print('xyxyn  ', e)
        try:
            print('xyxy   ', box.xyxy)
        except AttributeError as e:
            print('xyxy   ', e)
        try:
            print('pointsn', box.pointsn)
        except AttributeError as e:
            print('pointsn', e)
        try:
            print('points ', box.points)
        except AttributeError as e:
            print('points ', e)

    def show2(box):
        try:
            print('x1y1n  ', box.x1y1n)
        except AttributeError as e:
            print('x1y1n  ', e)
        try:
            print('x1y1   ', box.x1y1)
        except AttributeError as e:
            print('x1y1   ', e)
        try:
            print('x1y2n  ', box.x1y2n)
        except AttributeError as e:
            print('x1y2n  ', e)
        try:
            print('x1y2   ', box.x1y2)
        except AttributeError as e:
            print('x1y2   ', e)
        try:
            print('x2y1n  ', box.x2y1n)
        except AttributeError as e:
            print('x2y1n  ', e)
        try:
            print('x2y1   ', box.x2y1)
        except AttributeError as e:
            print('x2y1   ', e)
        try:
            print('x2y2n  ', box.x2y2n)
        except AttributeError as e:
            print('x2y2n  ', e)
        try:
            print('x2y2   ', box.x2y2)
        except AttributeError as e:
            print('x2y2   ', e)
        try:
            print('xyn    ', box.xyn)
        except AttributeError as e:
            print('xyn    ', e)
        try:
            print('xy     ', box.xy)
        except AttributeError as e:
            print('xy     ', e)

    print('\nbox1 set xywhn and size')
    box1 = Box(xywhn=[0.3, 0.3, 0.2, 0.2], size=(100, 100))
    show(box1)

    print('\nbox2 set xywhn')
    box2 = Box(xywhn=[0.3, 0.3, 0.2, 0.2])
    show(box2)

    print('\nbox3 set xywh')
    box3 = Box(xywh=[3, 3, 2, 2])
    show(box3)

    print('\nbox4 set pointsn')
    box4 = Box(pointsn=[(0.1, 0.1), (0.5, 0.05), (0.3, 0.1), (0.1, 0.2)])
    show(box4)

    print('\nbox5 set points')
    box5 = Box(points=[(50, 50), (100, 20), (150, 100), (100, 200)])
    show(box5)

    print('\nbox6 set pointsn')
    box6 = Box(pointsn=[(0.1, 0.1), (0.5, 0.05), (0.3, 0.1), (0.1, 0.2)])
    box6.set_size((100, 100))
    show(box6)
    show2(box6)


def test_2():
    import cv2

    W, H = 500, 500
    img = np.zeros((H, W, 3), dtype=np.uint8)

    examples = [
        ("xywh", dict(xywh=(300, 300, 100, 100))),
        ("xyxy", dict(xyxy=(200, 50, 400, 150))),
        ("xywhn", dict(xywhn=(0.7, 0.9, 0.1, 0.1))),
        ("xyxyn", dict(xyxyn=(0.2, 0.4, 0.3, 0.6))),
        ("points", dict(points=[(50, 50), (100, 20), (150, 100), (100, 200)])),
        ("pointsn", dict(pointsn=[(0.1, 0.1), (0.5, 0.05), (0.3, 0.1), (0.1, 0.2)])),
    ]

    for desc, kw in examples:
        box = Box((W, H), **kw)
        print(f"{desc:10} → {box}")
        color = tuple(int(c) for c in np.random.randint(50, 256, 3))

        if box.type == 'polygon':
            cv2.polylines(img, [box.points.astype(np.int32)], isClosed=True, color=color, thickness=2)
            for point in box.points:
                cv2.circle(img, tuple(map(int, point)), 5, color, -1)
        cv2.rectangle(img, tuple(map(int, box.x1y1)), tuple(map(int, box.x2y2)), color, 2)

    cv2.imshow("All Modes", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    print('=== test 1 ===')
    test_1()
    print()

    print('=== test 2 ===')
    test_2()
    print()

    b = Box(xywhn=(0.3, 0.8, 0.2, 0.1))
    print(b.xywhn)  # [0.3 0.8 0.2 0.1]
    b.scale(3)  # normalized scaling (default)
    print(b.xywhn)  # -> [0.3 0.8 0.6 0.3]

    b = Box(xywh=(30, 40, 10, 10))
    print(b)
    print(b.xywh)
    b.move(10,20)
    print(b.xywh)


