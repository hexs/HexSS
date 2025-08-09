from typing import Optional, Sequence, Tuple, Union, List
import numpy as np

Coord2 = Union[Tuple[float, float], List[float], Sequence[float]]
Coord4 = Union[Tuple[float, float, float, float], List[float], Sequence[float]]
PointSeq = Sequence[Tuple[float, float]]
Array2 = np.ndarray


def to_xyxy(boxes: np.ndarray, out: np.ndarray = None) -> np.ndarray:
    boxes_arr = np.asarray(boxes)
    if out is None:
        out = np.empty_like(boxes_arr)
    cx, cy, w, h = boxes_arr[..., 0], boxes_arr[..., 1], boxes_arr[..., 2], boxes_arr[..., 3]
    hw, hh = w * 0.5, h * 0.5
    out[..., 0] = cx - hw
    out[..., 1] = cy - hh
    out[..., 2] = cx + hw
    out[..., 3] = cy + hh
    return out


def to_xywh(boxes: np.ndarray, out: np.ndarray = None) -> np.ndarray:
    boxes_arr = np.asarray(boxes)
    if out is None:
        out = np.empty_like(boxes_arr)
    x1, y1, x2, y2 = boxes_arr[..., 0], boxes_arr[..., 1], boxes_arr[..., 2], boxes_arr[..., 3]
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
        self._size = np.array(size, dtype=np.float32) if size else None
        self.type = None
        self._setup(xywhn, xywh, xyxyn, xyxy, points, pointsn)

    def _setup(self, xywhn, xywh, xyxyn, xyxy, points, pointsn):
        if xywhn is not None:
            self._xywhn = np.array(xywhn)
            self._xyxyn = to_xyxy(self._xywhn)
            self.type = "box"
        elif xyxyn is not None:
            self._xyxyn = np.array(xyxyn)
            self._xywhn = to_xywh(self._xyxyn)
            self.type = "box"
        elif xywh is not None:
            self._xywh = np.array(xywh)
            self._xyxy = to_xyxy(self._xywh)
            self.type = "box"
        elif xyxy is not None:
            self._xyxy = np.array(xyxy)
            self._xywh = to_xywh(self._xyxy)
            self.type = "box"
        elif pointsn is not None:
            self._pointsn = np.array(pointsn)
            self._set_from_pointsn(self._pointsn)
            self.type = "polygon"
        elif points is not None:
            self._points = np.array(points)
            self._set_from_points(self._points)
            self.type = "polygon"

    def _set_from_pointsn(self, pts: Array2) -> None:
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self._xywhn = np.array([cx, cy, w, h], dtype=float)
        self._xyxyn = to_xyxy(self._xywhn)

    def _set_from_points(self, pts: Array2) -> None:
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self._xywh = np.array([cx, cy, w, h], dtype=float)
        self._xyxy = to_xyxy(self._xywh)

    def set_size(self, size):
        self._size = size

    def move(self, dx: float, dy: float, normalized: bool = False) -> None:
        delta = np.array([dx, dy])
        if normalized:
            delta *= self.size
        self.xywh[:2] += delta
        if hasattr(self, '_points'):
            self._points += delta

    def points_int32(self):
        return self.points.astype(np.int32)

    @property
    def size(self):
        if self._size is None:
            raise AttributeError("Unknown size")
        return self._size

    @property
    def xywhn(self):
        return self._xywhn if hasattr(self, '_xywhn') else self._xywh / np.tile(self.size, 2)

    @property
    def xywh(self):
        return self._xywh if hasattr(self, '_xywh') else self._xywhn * np.tile(self.size, 2)

    @property
    def xyxyn(self):
        return self._xyxyn if hasattr(self, '_xyxyn') else self._xyxy / np.tile(self.size, 2)

    @property
    def xyxy(self):
        return self._xyxy if hasattr(self, '_xyxy') else self._xyxyn * np.tile(self.size, 2)

    @property
    def points(self):
        return self._points if hasattr(self, '_points') else self._pointsn * self.size

    @property
    def pointsn(self):
        return self._pointsn if hasattr(self, '_pointsn') else self._points / self.size

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

    def __repr__(self):
        return f"<Box type={self.type}>"


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
