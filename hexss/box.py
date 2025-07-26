import numpy as np
from typing import Optional, Sequence, Tuple, Union

Array2 = np.ndarray
Coord4 = Union[Tuple[float, float, float, float], Sequence[float]]


class Box:
    """
    Represents an axis-aligned rectangle (or polygon’s bounding box).
    Supports single-mode init (xywh, xyxy, xywhn, xyxyn, points, pointsn)
    or dual-mode init: one origin (xy, xyn, x1y1, x1y1n) plus one size (wh, whn).
    """

    def __init__(
            self,
            size: Tuple[float, float],
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
            whn: Optional[Tuple[float, float]] = None,
    ) -> None:
        self.width, self.height = map(float, size)
        self.points = None

        # Track provided arguments
        provided = {
            'xywh': xywh, 'xyxy': xyxy,
            'xywhn': xywhn, 'xyxyn': xyxyn,
            'points': points, 'pointsn': pointsn,
            'xy': xy, 'xyn': xyn,
            'x1y1': x1y1, 'x1y1n': x1y1n,
            'wh': wh, 'whn': whn,
        }
        keys = [k for k, v in provided.items() if v is not None]

        # Single-mode
        single_modes = {'xywh', 'xyxy', 'xywhn', 'xyxyn', 'points', 'pointsn'}
        if len(keys) == 1 and keys[0] in single_modes:
            scale4 = np.array([self.width, self.height, self.width, self.height], dtype=float)
            if xywh is not None:
                self._set_xywh(np.asarray(xywh, dtype=float))
                self.type = "box"
            elif xyxy is not None:
                self._set_xyxy(np.asarray(xyxy, dtype=float))
                self.type = "box"
            elif xywhn is not None:
                arr = np.asarray(xywhn, dtype=float) * scale4
                self._set_xywh(arr)
                self.type = "box"
            elif xyxyn is not None:
                arr = np.asarray(xyxyn, dtype=float) * scale4
                self._set_xyxy(arr)
                self.type = "box"
            elif points is not None:
                self.points = np.asarray(points, dtype=float)
                self._set_from_points(self.points)
                self.type = "polygon"
            elif pointsn is not None:
                self.points = np.asarray(pointsn, dtype=float) * [self.width, self.height]
                self._set_from_points(self.points)
                self.type = "polygon"

        # Dual-mode (origin + size)
        else:
            origins = {'xy': xy, 'xyn': xyn, 'x1y1': x1y1, 'x1y1n': x1y1n}
            sizes = {'wh': wh, 'whn': whn}
            used_o = [k for k in origins if origins[k] is not None]
            used_s = [k for k in sizes if sizes[k] is not None]

            if len(used_o) != 1 or len(used_s) != 1 or len(keys) != 2:
                raise ValueError(
                    "Provide exactly one origin (xy,xyn,x1y1,x1y1n) "
                    "and one size (wh,whn), or use one single-mode argument."
                )
            o_key, s_key = used_o[0], used_s[0]
            o = np.asarray(origins[o_key], dtype=float)
            s = np.asarray(sizes[s_key], dtype=float)

            if o_key.endswith('n'):
                o *= [self.width, self.height]
            if s_key.endswith('n'):
                s *= [self.width, self.height]

            if o_key in ('xy', 'xyn'):
                cx, cy = o
                w, h = s
            else:
                x1, y1 = o
                w, h = s
                cx, cy = x1 + w / 2, y1 + h / 2

            self._set_xywh(np.array([cx, cy, w, h], dtype=float))
            self.type = "box"

        self._update_all()

    def _set_xywh(self, xywh: Array2) -> None:
        if xywh.shape != (4,):
            raise ValueError("xywh must be length 4: (cx,cy,w,h)")
        self.xywh = xywh

    def _set_xyxy(self, xyxy: Array2) -> None:
        if xyxy.shape != (4,):
            raise ValueError("xyxy must be length 4: (x1,y1,x2,y2)")
        x1, y1, x2, y2 = xyxy
        if x2 < x1 or y2 < y1:
            raise ValueError("Invalid corners: x2<x1 or y2<y1")
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self.xywh = np.array([cx, cy, w, h], dtype=float)

    def _set_from_points(self, pts: Array2) -> None:
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError("Points must be an (N, 2) array")
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        w, h = x2 - x1, y2 - y1
        cx, cy = x1 + w / 2, y1 + h / 2
        self.xywh = np.array([cx, cy, w, h], dtype=float)

    def _update_all(self) -> None:
        cx, cy, w, h = self.xywh
        x1, y1 = cx - w / 2, cy - h / 2
        x2, y2 = cx + w / 2, cy + h / 2

        self.xyxy = np.array([x1, y1, x2, y2], dtype=float)
        self.x1y1 = np.array([x1, y1], dtype=float)
        self.x2y2 = np.array([x2, y2], dtype=float)
        self.wh = np.array([w, h], dtype=float)
        self.xy = np.array([cx, cy], dtype=float)

        denom4 = np.array([self.width, self.height] * 2, dtype=float)
        denom2 = np.array([self.width, self.height], dtype=float)

        self.xyxyn = self.xyxy / denom4
        self.xywhn = self.xywh / np.concatenate([denom2, denom2])
        self.whn = self.wh / denom2
        self.xyn = self.xy / denom2
        self.x1y1n = self.x1y1 / denom2
        self.x2y2n = self.x2y2 / denom2

    def move(self, dx: float, dy: float, normalized: bool = False) -> None:
        if normalized:
            dx *= self.width
            dy *= self.height
        self.xywh[:2] += [dx, dy]
        if self.points is not None:
            self.points += [dx, dy]
        self._update_all()

    def scale(self, sx: float, sy: Optional[float] = None) -> None:
        sy = sx if sy is None else sy
        self.xywh[2:] *= [sx, sy]
        self._update_all()

    def clip_to_image(self) -> None:
        x1, y1, x2, y2 = self.xyxy
        x1 = np.clip(x1, 0, self.width)
        y1 = np.clip(y1, 0, self.height)
        x2 = np.clip(x2, 0, self.width)
        y2 = np.clip(y2, 0, self.height)
        self._set_xyxy(np.array([x1, y1, x2, y2], dtype=float))
        self._update_all()

    def __repr__(self) -> str:
        cx, cy, w, h = self.xywh
        return (
            f"Box(type={self.type!r}, size=({self.width:.0f},{self.height:.0f}), "
            f"xywh=({cx:.0f},{cy:.0f},{w:.0f},{h:.0f}))"
        )

    def points_int32(self):
        return self.points.astype(np.int32)


# === Demo ===
if __name__ == "__main__":
    import cv2

    W, H = 500, 500
    img = np.zeros((H, W, 3), dtype=np.uint8)

    examples = [
        ("abs center + abs size", dict(xy=(50, 50), wh=(50, 50))),
        ("norm center + abs size", dict(xyn=(0.3, 0.1), wh=(50, 50))),
        ("abs center + norm size", dict(xy=(200, 300), whn=(0.2, 0.1))),
        ("norm center + norm size", dict(xyn=(0.4, 0.6), whn=(0.2, 0.1))),
        ("abs TL + abs size", dict(x1y1=(150, 275), wh=(100, 50))),
        ("norm TL + abs size", dict(x1y1n=(0.3, 0.55), wh=(100, 50))),
        ("abs TL + norm size", dict(x1y1=(150, 275), whn=(0.2, 0.1))),
        ("norm TL + norm size", dict(x1y1n=(0.3, 0.55), whn=(0.2, 0.1))),
        ("xywh", dict(xywh=(300, 300, 100, 100))),
        ("xyxy", dict(xyxy=(200, 50, 400, 150))),
        ("xywhn", dict(xywhn=(0.7, 0.9, 0.1, 0.1))),
        ("xyxyn", dict(xyxyn=(0.2, 0.4, 0.3, 0.6))),
        ("points", dict(points=[(50, 50), (100, 20), (150, 100), (100, 200)])),
        ("pointsn", dict(pointsn=[(0.1, 0.1), (0.5, 0.05), (0.3, 0.1), (0.1, 0.2)])),
    ]

    for desc, kw in examples:
        box = Box((W, H), **kw)
        box.move(20, 20)
        print(f"{desc:30} → {box}")
        color = tuple(int(c) for c in np.random.randint(50, 256, 3))

        if box.type == 'polygon':
            cv2.polylines(img, [box.points.astype(np.int32)], isClosed=True, color=color, thickness=2)
            for point in box.points:
                cv2.circle(img, tuple(map(int, point)), 5, color, -1)
        cv2.rectangle(img, tuple(map(int, box.x1y1)), tuple(map(int, box.x2y2)), color, 2)

    cv2.imshow("All Modes", img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
