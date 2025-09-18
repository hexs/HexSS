from __future__ import annotations
from typing import Iterable, Optional, Tuple, Sequence, List, Union
import numpy as np

Number2 = Tuple[float, float]
Number4 = Tuple[float, float, float, float]
Size = Tuple[int, int]
PointSeq = Sequence[Tuple[float, float]]
Array2 = np.ndarray


class Box:  # Box and Polygon
    """
    Canonical storage:
      - Box (absolute):   _a = (cx, cy, w, h)
      - Box (normalized): _n = (cxn, cyn, wn, hn)  in [0..1] w.r.t. .size
      - Polygon: points  (absolute) or pointsn (normalized)

    Base forms (mutually exclusive at construction): xywh, xyxy, xywhn, xyxyn, points, pointsn

    Convenience:
      - Absolute:   xy, wh, anchors x1y1, x1y2, x2y1, x2y2, x1y, x2y, xy1, xy2
      - Normalized: xyn, whn, anchors x1y1n, x1y2n, x2y1n, x2y2n, x1yn, x2yn, xy1n, xy2n
      - Anchor+size (read/write):
          Absolute:   x1y1wh, x1y2wh, x2y1wh, x2y2wh, x1ywh, x2ywh, xy1wh, xy2wh
          Normalized: x1y1whn, x1y2whn, x2y1whn, x2y2whn, x1ywhn, x2ywhn, xy1whn, xy2whn
    """

    __slots__ = ("_mode", "_a", "_n", "_size", "_kind", "_points", "_pointsn")

    _KW_ORDER = (
        "size",
        # base forms (at most one)
        "xywhn", "xyxyn", "xywh", "xyxy", "pointsn", "points",
        # simple components
        "xy", "wh", "xyn", "whn",
        # anchor points (setters move box keeping w/h)
        "x1y1n", "x1y2n", "x2y1n", "x2y2n", "x1yn", "x2yn", "xy1n", "xy2n",
        "x1y1", "x1y2", "x2y1", "x2y2", "x1y", "x2y", "xy1", "xy2",
        # anchor + size
        "x1y1whn", "x1y2whn", "x2y1whn", "x2y2whn",
        "x1ywhn", "x2ywhn", "xy1whn", "xy2whn",
        "x1y1wh", "x1y2wh", "x2y1wh", "x2y2wh",
        "x1ywh", "x2ywh", "xy1wh", "xy2wh",
    )
    _BASE_FORMS = ("xywhn", "xyxyn", "xywh", "xyxy", "pointsn", "points")

    # --------------------- init ---------------------
    def __init__(
            self,
            *,
            xywhn: Optional[Iterable[float]] = None,
            xyxyn: Optional[Iterable[float]] = None,
            xywh: Optional[Iterable[float]] = None,
            xyxy: Optional[Iterable[float]] = None,
            pointsn: Optional[PointSeq] = None,
            points: Optional[PointSeq] = None,
            size: Optional[Size] = None,
            **kw
    ):
        self._mode: Optional[str] = None  # "a" or "n" (for boxes only)
        self._a: Optional[Number4] = None
        self._n: Optional[Number4] = None
        self._size: Optional[Size] = None
        self._kind: Optional[str] = None  # "box" or "polygon"
        self._points: Optional[np.ndarray] = None
        self._pointsn: Optional[np.ndarray] = None

        # fold explicit args into kw so one path handles everything
        if size is not None: kw.setdefault("size", size)
        if xywhn is not None: kw.setdefault("xywhn", xywhn)
        if xyxyn is not None: kw.setdefault("xyxyn", xyxyn)
        if xywh is not None: kw.setdefault("xywh", xywh)
        if xyxy is not None: kw.setdefault("xyxy", xyxy)
        if pointsn is not None: kw.setdefault("pointsn", pointsn)
        if points is not None: kw.setdefault("points", points)

        self._apply_kwargs(**kw)

    # --------------------- utils ---------------------
    @staticmethod
    def _np2(vals: Sequence[float]) -> np.ndarray:
        return np.array(vals, dtype=float)

    @staticmethod
    def _np4(vals: Sequence[float]) -> np.ndarray:
        return np.array(vals, dtype=float)

    def _need_size(self):
        if self._size is None:
            raise ValueError("Image size is required (set .size = (W, H)).")

    def _apply_kwargs(self, **kw):
        if not kw: return
        allowed = set(self._KW_ORDER)
        unknown = [k for k in kw if k not in allowed]
        if unknown:
            raise TypeError(f"Unknown init keyword(s): {unknown}. Allowed: {sorted(allowed)}")

        # at most one base form
        base_in_kw = [k for k in self._BASE_FORMS if k in kw and kw[k] is not None]
        if len(base_in_kw) > 1:
            raise ValueError(f"Provide at most one base form, got {base_in_kw}.")

        for k in self._KW_ORDER:
            if k in kw and kw[k] is not None:
                setattr(self, k, kw[k])

    # --------------------- helpers ---------------------
    def _poly_bbox_abs(self) -> Tuple[float, float, float, float]:
        """Polygon AABB in absolute coords."""
        if self._points is not None:
            pts = self._points
        elif self._pointsn is not None:
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            pts = self._pointsn * np.array([W, H], dtype=float)
        else:
            raise ValueError("No polygon points available.")
        x1, y1 = pts.min(axis=0)
        x2, y2 = pts.max(axis=0)
        return float(x1), float(y1), float(x2), float(y2)

    def _poly_bbox_norm(self) -> Tuple[float, float, float, float]:
        """Polygon AABB in normalized coords."""
        if self._pointsn is not None:
            ptsn = self._pointsn
        elif self._points is not None:
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            ptsn = self._points / np.array([W, H], dtype=float)
        else:
            raise ValueError("No polygon points available.")
        x1, y1 = ptsn.min(axis=0)
        x2, y2 = ptsn.max(axis=0)
        return float(x1), float(y1), float(x2), float(y2)

    def _abs_xywh_box(self) -> Tuple[float, float, float, float]:
        if self._mode == "a":
            cx, cy, w, h = self._a  # type: ignore[misc]
            return float(cx), float(cy), float(w), float(h)
        if self._mode == "n":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cxn, cyn, wn, hn = self._n  # type: ignore[misc]
            return float(cxn * W), float(cyn * H), float(wn * W), float(hn * H)
        # polygon → bbox
        x1, y1, x2, y2 = self._poly_bbox_abs()
        w, h = x2 - x1, y2 - y1
        return (x1 + w * 0.5, y1 + h * 0.5, w, h)

    def _norm_xywh_box(self) -> Tuple[float, float, float, float]:
        if self._mode == "n":
            cxn, cyn, wn, hn = self._n  # type: ignore[misc]
            return float(cxn), float(cyn), float(wn), float(hn)
        if self._mode == "a":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cx, cy, w, h = self._a  # type: ignore[misc]
            return float(cx / W), float(cy / H), float(w / W), float(h / H)
        # polygon → bbox
        x1n, y1n, x2n, y2n = self._poly_bbox_norm()
        wn, hn = x2n - x1n, y2n - y1n
        return (x1n + wn * 0.5, y1n + hn * 0.5, wn, hn)

    # --------------------- size ---------------------
    @property
    def size(self) -> Optional[Size]:
        return self._size

    @size.setter
    def size(self, wh: Size):
        W, H = wh
        if not (W > 0 and H > 0): raise ValueError("size must be positive integers (W, H).")
        self._size = (int(W), int(H))

    def set_size(self, wh: Size) -> "Box":
        self.size = wh
        return self

    # --------------------- polygon properties ---------------------
    @property
    def points(self) -> np.ndarray:
        if self._points is not None:
            return self._points
        if self._pointsn is not None:
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            return self._pointsn * np.array([W, H], dtype=float)
        # derive from bbox (rectangle) if we're a box
        x1, y1, x2, y2 = self.xyxy
        return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=float)

    @points.setter
    def points(self, pts: PointSeq):
        arr = np.asarray(pts, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("points must have shape (N,2).")
        self._points = arr
        self._pointsn = None
        self._mode = None
        self._kind = "polygon"

    @property
    def pointsn(self) -> np.ndarray:
        if self._pointsn is not None:
            return self._pointsn
        if self._points is not None:
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            return self._points / np.array([W, H], dtype=float)
        # derive from bbox in normalized space
        x1n, y1n, x2n, y2n = self.xyxyn
        return np.array([[x1n, y1n], [x2n, y1n], [x2n, y2n], [x1n, y2n]], dtype=float)

    @pointsn.setter
    def pointsn(self, ptsn: PointSeq):
        arr = np.asarray(ptsn, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("pointsn must have shape (N,2).")
        self._pointsn = arr
        self._points = None
        self._mode = None
        self._kind = "polygon"

    # --------------------- base forms ---------------------
    @property
    def xywh(self) -> np.ndarray:
        cx, cy, w, h = self._abs_xywh_box()
        return self._np4((cx, cy, w, h))

    @xywh.setter
    def xywh(self, vals: Iterable[float]):
        cx, cy, w, h = map(float, vals)
        self._a = (cx, cy, w, h)
        self._mode = "a"
        self._kind = "box"
        # clear polygon views
        self._points = None;
        self._pointsn = None

    @property
    def xywhn(self) -> np.ndarray:
        cxn, cyn, wn, hn = self._norm_xywh_box()
        return self._np4((cxn, cyn, wn, hn))

    @xywhn.setter
    def xywhn(self, vals: Iterable[float]):
        cxn, cyn, wn, hn = map(float, vals)
        self._n = (cxn, cyn, wn, hn)
        self._mode = "n"
        self._kind = "box"
        self._points = None;
        self._pointsn = None

    @property
    def xyxy(self) -> np.ndarray:
        cx, cy, w, h = self._abs_xywh_box()
        return self._np4((cx - w * 0.5, cy - h * 0.5, cx + w * 0.5, cy + h * 0.5))

    @xyxy.setter
    def xyxy(self, vals: Iterable[float]):
        x1, y1, x2, y2 = map(float, vals)
        self.xywh = ((x1 + x2) * 0.5, (y1 + y2) * 0.5, (x2 - x1), (y2 - y1))

    @property
    def xyxyn(self) -> np.ndarray:
        cxn, cyn, wn, hn = self._norm_xywh_box()
        return self._np4((cxn - wn * 0.5, cyn - hn * 0.5, cxn + wn * 0.5, cyn + hn * 0.5))

    @xyxyn.setter
    def xyxyn(self, vals: Iterable[float]):
        x1n, y1n, x2n, y2n = map(float, vals)
        self.xywhn = ((x1n + x2n) * 0.5, (y1n + y2n) * 0.5, (x2n - x1n), (y2n - y1n))

    # --------------------- simple components ---------------------
    @property
    def xy(self) -> np.ndarray:
        cx, cy, _, _ = self.xywh
        return self._np2((cx, cy))

    @xy.setter
    def xy(self, vals: Iterable[float]):
        x, y = map(float, vals)
        if self._kind == "polygon":
            # move polygon so that bbox center becomes (x, y)
            cx0, cy0, _, _ = self._abs_xywh_box()
            self.move(x - cx0, y - cy0, normalized=False)
            return
        if self._mode == "a":
            cx, cy, w, h = self._a  # type: ignore[misc]
            self._a = (x, y, w, h)
        elif self._mode == "n":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cxn, cyn, wn, hn = self._n  # type: ignore[misc]
            self._n = (x / W, y / H, wn, hn)
        else:
            self._a = (x, y, 0.0, 0.0)
            self._mode = "a"
            self._kind = "box"

    @property
    def wh(self) -> np.ndarray:
        _, _, w, h = self.xywh
        return self._np2((w, h))

    @wh.setter
    def wh(self, vals: Iterable[float]):
        w, h = map(float, vals)
        if self._kind == "polygon":
            # scale polygon to achieve this bbox size (about center)
            cx, cy, w0, h0 = self._abs_xywh_box()
            sx = 0.0 if w0 == 0 else (w / w0)
            sy = 0.0 if h0 == 0 else (h / h0)
            self.scale(sx, sy, normalized=False)
            self.xy = (cx, cy)
            return
        if self._mode == "a":
            cx, cy, _, _ = self._a  # type: ignore[misc]
            self._a = (cx, cy, w, h)
        elif self._mode == "n":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cxn, cyn, _, _ = self._n  # type: ignore[misc]
            self._n = (cxn, cyn, w / W, h / H)
        else:
            self._a = (0.0, 0.0, w, h)
            self._mode = "a"
            self._kind = "box"

    @property
    def xyn(self) -> np.ndarray:
        cxn, cyn, _, _ = self.xywhn
        return self._np2((cxn, cyn))

    @xyn.setter
    def xyn(self, vals: Iterable[float]):
        cxn, cyn = map(float, vals)
        if self._mode == "n":
            _, _, wn, hn = self._n  # type: ignore[misc]
            self._n = (cxn, cyn, wn, hn)
            self._kind = "box"
        elif self._mode == "a":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            _, _, w, h = self._a  # type: ignore[misc]
            self._a = (cxn * W, cyn * H, w, h)
        else:
            # empty → start a normalized box with zero size
            self._n = (cxn, cyn, 0.0, 0.0)
            self._mode = "n"
            self._kind = "box"

    @property
    def whn(self) -> np.ndarray:
        _, _, wn, hn = self.xywhn
        return self._np2((wn, hn))

    @whn.setter
    def whn(self, vals: Iterable[float]):
        wn, hn = map(float, vals)
        if self._kind == "polygon":
            cxn, cyn, wn0, hn0 = self._norm_xywh_box()
            sx = 0.0 if wn0 == 0 else (wn / wn0)
            sy = 0.0 if hn0 == 0 else (hn / hn0)
            self.scale(sx, sy, normalized=True)
            self.xyn = (cxn, cyn)
            return
        if self._mode == "n":
            cxn, cyn, _, _ = self._n  # type: ignore[misc]
            self._n = (cxn, cyn, wn, hn)
        elif self._mode == "a":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cx, cy, _, _ = self._a  # type: ignore[misc]
            self._a = (cx, cy, wn * W, hn * H)
        else:
            raise ValueError("Box is empty; cannot set whn.")

    # --------------------- anchor points (get/set) ---------------------
    # getters use bbox (works for boxes & polygons)
    def _get_anchor_abs(self, name: str) -> np.ndarray:
        x1, y1, x2, y2 = self.xyxy
        cx, cy, _, _ = self.xywh
        if name == "x1y1": return self._np2((x1, y1))
        if name == "x1y2": return self._np2((x1, y2))
        if name == "x2y1": return self._np2((x2, y1))
        if name == "x2y2": return self._np2((x2, y2))
        if name == "x1y":  return self._np2((x1, cy))
        if name == "x2y":  return self._np2((x2, cy))
        if name == "xy1":  return self._np2((cx, y1))
        if name == "xy2":  return self._np2((cx, y2))
        raise ValueError(name)

    def _get_anchor_norm(self, name: str) -> np.ndarray:
        cxn, cyn, wn, hn = self.xywhn  # uses polygon bbox if needed
        half_w, half_h = wn * 0.5, hn * 0.5
        if name == "x1y1": return self._np2((cxn - half_w, cyn - half_h))
        if name == "x1y2": return self._np2((cxn - half_w, cyn + half_h))
        if name == "x2y1": return self._np2((cxn + half_w, cyn - half_h))
        if name == "x2y2": return self._np2((cxn + half_w, cyn + half_h))
        if name == "x1y":  return self._np2((cxn - half_w, cyn))
        if name == "x2y":  return self._np2((cxn + half_w, cyn))
        if name == "xy1":  return self._np2((cxn, cyn - half_h))
        if name == "xy2":  return self._np2((cxn, cyn + half_h))
        raise ValueError(name)

    # setters (move geometry keeping current w/h)
    def _set_anchor_abs(self, name: str, p: Iterable[float]):
        x, y = map(float, p)
        w, h = self.wh
        if name == "x1y1":
            cx, cy = x + w * 0.5, y + h * 0.5
        elif name == "x1y2":
            cx, cy = x + w * 0.5, y - h * 0.5
        elif name == "x2y1":
            cx, cy = x - w * 0.5, y + h * 0.5
        elif name == "x2y2":
            cx, cy = x - w * 0.5, y - h * 0.5
        elif name == "x1y":
            cx, cy = x + w * 0.5, y
        elif name == "x2y":
            cx, cy = x - w * 0.5, y
        elif name == "xy1":
            cx, cy = x, y + h * 0.5
        elif name == "xy2":
            cx, cy = x, y - h * 0.5
        else:
            raise ValueError(name)
        cx0, cy0, _, _ = self._abs_xywh_box()
        self.move(cx - cx0, cy - cy0, normalized=False)

    def _set_anchor_norm(self, name: str, pn: Iterable[float]):
        self._need_size()
        W, H = self._size  # type: ignore[assignment]
        xn, yn = map(float, pn)
        self._set_anchor_abs(name, (xn * W, yn * H))

    # absolute anchor properties
    @property
    def x1y1(self) -> np.ndarray:
        return self._get_anchor_abs("x1y1")

    @x1y1.setter
    def x1y1(self, p):
        self._set_anchor_abs("x1y1", p)

    @property
    def x1y2(self) -> np.ndarray:
        return self._get_anchor_abs("x1y2")

    @x1y2.setter
    def x1y2(self, p):
        self._set_anchor_abs("x1y2", p)

    @property
    def x2y1(self) -> np.ndarray:
        return self._get_anchor_abs("x2y1")

    @x2y1.setter
    def x2y1(self, p):
        self._set_anchor_abs("x2y1", p)

    @property
    def x2y2(self) -> np.ndarray:
        return self._get_anchor_abs("x2y2")

    @x2y2.setter
    def x2y2(self, p):
        self._set_anchor_abs("x2y2", p)

    @property
    def x1y(self) -> np.ndarray:
        return self._get_anchor_abs("x1y")

    @x1y.setter
    def x1y(self, p):
        self._set_anchor_abs("x1y", p)

    @property
    def x2y(self) -> np.ndarray:
        return self._get_anchor_abs("x2y")

    @x2y.setter
    def x2y(self, p):
        self._set_anchor_abs("x2y", p)

    @property
    def xy1(self) -> np.ndarray:
        return self._get_anchor_abs("xy1")

    @xy1.setter
    def xy1(self, p):
        self._set_anchor_abs("xy1", p)

    @property
    def xy2(self) -> np.ndarray:
        return self._get_anchor_abs("xy2")

    @xy2.setter
    def xy2(self, p):
        self._set_anchor_abs("xy2", p)

    # normalized anchor properties
    @property
    def x1y1n(self) -> np.ndarray:
        return self._get_anchor_norm("x1y1")

    @x1y1n.setter
    def x1y1n(self, pn):
        self._set_anchor_norm("x1y1", pn)

    @property
    def x1y2n(self) -> np.ndarray:
        return self._get_anchor_norm("x1y2")

    @x1y2n.setter
    def x1y2n(self, pn):
        self._set_anchor_norm("x1y2", pn)

    @property
    def x2y1n(self) -> np.ndarray:
        return self._get_anchor_norm("x2y1")

    @x2y1n.setter
    def x2y1n(self, pn):
        self._set_anchor_norm("x2y1", pn)

    @property
    def x2y2n(self) -> np.ndarray:
        return self._get_anchor_norm("x2y2")

    @x2y2n.setter
    def x2y2n(self, pn):
        self._set_anchor_norm("x2y2", pn)

    @property
    def x1yn(self) -> np.ndarray:
        return self._get_anchor_norm("x1y")

    @x1yn.setter
    def x1yn(self, pn):
        self._set_anchor_norm("x1y", pn)

    @property
    def x2yn(self) -> np.ndarray:
        return self._get_anchor_norm("x2y")

    @x2yn.setter
    def x2yn(self, pn):
        self._set_anchor_norm("x2y", pn)

    @property
    def xy1n(self) -> np.ndarray:
        return self._get_anchor_norm("xy1")

    @xy1n.setter
    def xy1n(self, pn):
        self._set_anchor_norm("xy1", pn)

    @property
    def xy2n(self) -> np.ndarray:
        return self._get_anchor_norm("xy2")

    @xy2n.setter
    def xy2n(self, pn):
        self._set_anchor_norm("xy2", pn)

    # --------------------- anchor + size (read/write) ---------------------
    @staticmethod
    def _unpack2(v: Iterable[float]) -> Tuple[float, float]:
        a, b = v
        return float(a), float(b)

    # absolute anchors + absolute wh
    @property
    def x1y1wh(self):
        x1, y1, x2, y2 = self.xyxy
        w, h = self.wh
        return self._np4((x1, y1, w, h))

    @x1y1wh.setter
    def x1y1wh(self, vals):
        (x1, y1), (w, h) = map(self._unpack2, vals);
        self.xywh = (x1 + w * 0.5, y1 + h * 0.5, w, h)

    @property
    def x1y2wh(self):
        x1, y1, x2, y2 = self.xyxy
        w, h = self.wh
        return self._np4((x1, y2, w, h))

    @x1y2wh.setter
    def x1y2wh(self, vals):
        (x1, y2), (w, h) = map(self._unpack2, vals);
        self.xywh = (x1 + w * 0.5, y2 - h * 0.5, w, h)

    @property
    def x2y1wh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        return self._np4((x2, y1, w, h))

    @x2y1wh.setter
    def x2y1wh(self, vals):
        (x2, y1), (w, h) = map(self._unpack2, vals);
        self.xywh = (x2 - w * 0.5, y1 + h * 0.5, w, h)

    @property
    def x2y2wh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        return self._np4((x2, y2, w, h))

    @x2y2wh.setter
    def x2y2wh(self, vals):
        (x2, y2), (w, h) = map(self._unpack2, vals);
        self.xywh = (x2 - w * 0.5, y2 - h * 0.5, w, h)

    @property
    def x1ywh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        _, cy, _, _ = self.xywh;
        return self._np4((x1, cy, w, h))

    @x1ywh.setter
    def x1ywh(self, vals):
        (x1, y), (w, h) = map(self._unpack2, vals);
        self.xywh = (x1 + w * 0.5, y, w, h)

    @property
    def x2ywh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        _, cy, _, _ = self.xywh;
        return self._np4((x2, cy, w, h))

    @x2ywh.setter
    def x2ywh(self, vals):
        (x2, y), (w, h) = map(self._unpack2, vals);
        self.xywh = (x2 - w * 0.5, y, w, h)

    @property
    def xy1wh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        cx, _, _, _ = self.xywh;
        return self._np4((cx, y1, w, h))

    @xy1wh.setter
    def xy1wh(self, vals):
        (x, y1), (w, h) = map(self._unpack2, vals);
        self.xywh = (x, y1 + h * 0.5, w, h)

    @property
    def xy2wh(self):
        x1, y1, x2, y2 = self.xyxy;
        w, h = self.wh;
        cx, _, _, _ = self.xywh;
        return self._np4((cx, y2, w, h))

    @xy2wh.setter
    def xy2wh(self, vals):
        (x, y2), (w, h) = map(self._unpack2, vals);
        self.xywh = (x, y2 - h * 0.5, w, h)

    def _anchor_norm_get_pair(self, name: str):
        """
        Return [xn, yn, wn, hn] (all normalized). If we're in absolute mode,
        we convert via size; in normalized mode, no size is required.
        """
        # If normalized (or polygon with normalized points), no size needed
        if self._mode == "n" or (self._kind == "polygon" and self._pointsn is not None):
            a = getattr(self, name + "n")  # uses xywhn internally
            wn, hn = self.whn
            return self._np4((float(a[0]), float(a[1]), float(wn), float(hn)))

        # Absolute or polygon-absolute → requires size to compute normalized
        self._need_size()
        a = getattr(self, name + "n")
        wn, hn = self.whn
        return self._np4((float(a[0]), float(a[1]), float(wn), float(hn)))

    @property
    def x1y1whn(self):
        return self._anchor_norm_get_pair("x1y1")

    @x1y1whn.setter
    def x1y1whn(self, vals):
        (x1n, y1n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x1y1", (x1n, y1n));
        self.wh = (w, h)

    @property
    def x1y2whn(self):
        return self._anchor_norm_get_pair("x1y2")

    @x1y2whn.setter
    def x1y2whn(self, vals):
        (x1n, y2n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x1y2", (x1n, y2n));
        self.wh = (w, h)

    @property
    def x2y1whn(self):
        return self._anchor_norm_get_pair("x2y1")

    @x2y1whn.setter
    def x2y1whn(self, vals):
        (x2n, y1n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x2y1", (x2n, y1n));
        self.wh = (w, h)

    @property
    def x2y2whn(self):
        return self._anchor_norm_get_pair("x2y2")

    @x2y2whn.setter
    def x2y2whn(self, vals):
        (x2n, y2n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x2y2", (x2n, y2n));
        self.wh = (w, h)

    @property
    def x1ywhn(self):
        return self._anchor_norm_get_pair("x1y")

    @x1ywhn.setter
    def x1ywhn(self, vals):
        (x1n, yn), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x1y", (x1n, yn));
        self.wh = (w, h)

    @property
    def x2ywhn(self):
        return self._anchor_norm_get_pair("x2y")

    @x2ywhn.setter
    def x2ywhn(self, vals):
        (x2n, yn), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("x2y", (x2n, yn));
        self.wh = (w, h)

    @property
    def xy1whn(self):
        return self._anchor_norm_get_pair("xy1")

    @xy1whn.setter
    def xy1whn(self, vals):
        (xn, y1n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("xy1", (xn, y1n));
        self.wh = (w, h)

    @property
    def xy2whn(self):
        return self._anchor_norm_get_pair("xy2")

    @xy2whn.setter
    def xy2whn(self, vals):
        (xn, y2n), (w, h) = map(self._unpack2, vals);
        self._set_anchor_norm("xy2", (xn, y2n));
        self.wh = (w, h)

    # --------------------- ops & stats ---------------------
    def move(self, dx: float, dy: float, *, normalized: Optional[bool] = None) -> "Box":
        """Translate geometry. If normalized is None, infer from current storage."""
        if self._kind == "polygon":
            # choose unit for translation
            if normalized is None:
                normalized = (self._pointsn is not None and self._points is None)
            if normalized:
                if self._pointsn is None:
                    # need size to convert absolute → normalized delta
                    self._need_size()
                    W, H = self._size  # type: ignore[assignment]
                    dxn, dyn = float(dx), float(dy)
                    if self._points is not None:
                        # convert polygon to normalized then move
                        self._pointsn = self._points / np.array([W, H], dtype=float)
                        self._points = None
                    self._pointsn = self._pointsn + np.array([dxn, dyn], dtype=float)
                else:
                    self._pointsn = self._pointsn + np.array([dx, dy], dtype=float)
            else:
                if self._points is None:
                    self._need_size()
                    W, H = self._size  # type: ignore[assignment]
                    pts = self._pointsn * np.array([W, H], dtype=float)  # type: ignore[operator]
                    self._points = pts
                    self._pointsn = None
                self._points = self._points + np.array([dx, dy], dtype=float)  # type: ignore[operator]
            return self

        # box
        if self._mode == "a":
            cx, cy, w, h = self._a  # type: ignore[misc]
            self._a = (cx + float(dx), cy + float(dy), w, h)
        elif self._mode == "n":
            self._need_size()
            W, H = self._size  # type: ignore[assignment]
            cxn, cyn, wn, hn = self._n  # type: ignore[misc]
            self._n = (cxn + dx / W, cyn + dy / H, wn, hn)
        else:
            raise ValueError("Box is empty; cannot move.")
        return self

    def scale(self, fx: float, fy: Optional[float] = None, *, normalized: Optional[bool] = None) -> "Box":
        """Scale about center (box) or polygon centroid."""
        if fy is None: fy = fx
        fx = float(fx);
        fy = float(fy)

        if self._kind == "polygon":
            if normalized is None:
                normalized = (self._pointsn is not None and self._points is None)
            if normalized:
                if self._pointsn is None:
                    self._need_size()
                    W, H = self._size  # type: ignore[assignment]
                    self._pointsn = self._points / np.array([W, H], dtype=float)  # type: ignore[operator]
                    self._points = None
                pts = self._pointsn
                c = pts.mean(axis=0, keepdims=True)
                self._pointsn = (pts - c) * np.array([fx, fy]) + c
            else:
                if self._points is None:
                    self._need_size()
                    W, H = self._size  # type: ignore[assignment]
                    self._points = self._pointsn * np.array([W, H], dtype=float)  # type: ignore[operator]
                    self._pointsn = None
                pts = self._points
                c = pts.mean(axis=0, keepdims=True)
                self._points = (pts - c) * np.array([fx, fy]) + c
            return self

        # box
        if self._mode == "a":
            cx, cy, w, h = self._a  # type: ignore[misc]
            self._a = (cx, cy, w * fx, h * fy)
        elif self._mode == "n":
            cxn, cyn, wn, hn = self._n  # type: ignore[misc]
            self._n = (cxn, cyn, wn * fx, hn * fy)
        else:
            raise ValueError("Box is empty; cannot scale.")
        return self

    @property
    def area(self) -> float:
        _, _, w, h = self.xywh
        return float(w * h)

    @property
    def aspect(self) -> float:
        _, _, w, h = self.xywh
        return float(w / h) if h != 0 else float("inf")

    @property
    def type(self) -> Optional[str]:
        return self._kind if self._kind else ("box" if self._mode in ("a", "n") else None)

    # --------------------- repr ---------------------
    def __repr__(self) -> str:
        try:
            if self._kind == "polygon":
                if self._points is not None:
                    return f"Box(polygon_abs={self._points.shape}, size={self._size})"
                if self._pointsn is not None:
                    return f"Box(polygon_norm={self._pointsn.shape}, size={self._size})"
            if self._mode == "a":
                return f"Box(xywh={self._np4(self._a)}, size={self._size})"  # type: ignore[arg-type]
            if self._mode == "n":
                return f"Box(xywhn={self._np4(self._n)}, size={self._size})"  # type: ignore[arg-type]
            return "Box(<empty>)"
        except Exception:
            return "Box(<unavailable>)"


def test_1():
    def show(box: Box):
        try:
            print('xywhn  ', box.xywhn)
        except Exception as e:
            print('xywhn  ', e)
        try:
            print('xywh   ', box.xywh)
        except Exception as e:
            print('xywh   ', e)
        try:
            print('xyxyn  ', box.xyxyn)
        except Exception as e:
            print('xyxyn  ', e)
        try:
            print('xyxy   ', box.xyxy)
        except Exception as e:
            print('xyxy   ', e)
        try:
            print('pointsn', box.pointsn)
        except Exception as e:
            print('pointsn', e)
        try:
            print('points ', box.points)
        except Exception as e:
            print('points ', e)

    def show2(box):
        try:
            print('x1y1n  ', box.x1y1n)
        except Exception as e:
            print('x1y1n  ', e)
        try:
            print('x1y1   ', box.x1y1)
        except Exception as e:
            print('x1y1   ', e)
        try:
            print('x1y2n  ', box.x1y2n)
        except Exception as e:
            print('x1y2n  ', e)
        try:
            print('x1y2   ', box.x1y2)
        except Exception as e:
            print('x1y2   ', e)
        try:
            print('x2y1n  ', box.x2y1n)
        except Exception as e:
            print('x2y1n  ', e)
        try:
            print('x2y1   ', box.x2y1)
        except Exception as e:
            print('x2y1   ', e)
        try:
            print('x2y2n  ', box.x2y2n)
        except Exception as e:
            print('x2y2n  ', e)
        try:
            print('x2y2   ', box.x2y2)
        except Exception as e:
            print('x2y2   ', e)
        try:
            print('xyn    ', box.xyn)
        except Exception as e:
            print('xyn    ', e)
        try:
            print('xy     ', box.xy)
        except Exception as e:
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
        box = Box(size=(W, H), **kw)
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
    b.move(10, 20)
    print(b.xywh)


