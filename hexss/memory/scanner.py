"""
Scanner แบบ Cheat Engine: first scan -> next scan -> ได้รายการ Address

    scan = mem.newscan(dtype=4)          # 1, 2, 4, 8, 'float', 'double'
    scan.first(100)                      # exact value
    scan.next(101)                       # กรองต่อด้วยค่าใหม่
    scan.next('changed')                 # changed / unchanged / increased / decreased
    scan.next('between', 90, 110)        # between / greater / less / increased_by / decreased_by
    scan.count                           # จำนวนผลลัพธ์
    scan.results[0].read()               # เป็น Address object ใช้ read()/write() ได้เลย

ตัวสแกนรับ `mem` เป็น duck-typing ขอแค่มี  regions(**opts)  และ  read_bytes_partial(addr, size)
"""
from __future__ import annotations

import math
import threading
from typing import Any, Callable, List, Optional, Tuple, Union, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .memory import Address, Memory

CHUNK = 4 * 1024 * 1024  # ขนาดที่อ่านต่อครั้งตอน first scan
MAX_READ = 4 * 1024 * 1024  # ขนาดสูงสุดต่อครั้งตอน next scan
GAP = 256  # address ที่ห่างกันไม่เกินนี้ จะถูกอ่านรวมเป็นก้อนเดียว

_ABSOLUTE = {'exact', 'between', 'greater', 'less'}
_RELATIVE = {'changed', 'unchanged', 'increased', 'decreased', 'increased_by', 'decreased_by'}
_NARGS = {'exact': 1, 'greater': 1, 'less': 1, 'between': 2, 'increased_by': 1, 'decreased_by': 1,
          'changed': 0, 'unchanged': 0, 'increased': 0, 'decreased': 0}
_ALIASES = {'exact_value': 'exact', 'bigger': 'greater', 'bigger_than': 'greater', 'greater_than': 'greater',
            'smaller': 'less', 'smaller_than': 'less', 'less_than': 'less', 'range': 'between'}

Number = Union[int, float]


class ScanCancelled(Exception):
    pass


def _np_dtype(dtype: Union[int, str], signed: bool) -> np.dtype:
    if dtype == 'float':
        return np.dtype('<f4')
    if dtype == 'double':
        return np.dtype('<f8')
    if dtype in (1, 2, 4, 8):
        return np.dtype(f"<{'i' if signed else 'u'}{dtype}")
    raise ValueError(f"Invalid numeric dtype: {dtype!r} (use 1, 2, 4, 8, 'float', 'double')")


class ScanResults:
    """มองผลลัพธ์เป็น list ของ Address (สร้างตอนเรียกใช้ ไม่กิน memory เพิ่ม)"""

    def __init__(self, scanner: 'Scanner'):
        self._s = scanner

    def _make(self, addr: int) -> 'Address':
        return self._s.mem.address(addr, self._s.dtype, signed=self._s.signed)

    def __len__(self) -> int:
        return len(self._s._addrs)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [self._make(a) for a in self._s._addrs[i].tolist()]
        return self._make(int(self._s._addrs[i]))


class Scanner:
    def __init__(self, mem: 'Memory', dtype: Union[int, str] = 4, signed: bool = True,
                 alignment: Optional[int] = None, tolerance: float = 0.0,
                 writable_only: bool = True, include_image: bool = True, include_mapped: bool = False,
                 start: int = 0, end: Optional[int] = None,
                 max_results: int = 20_000_000,
                 progress: Optional[Callable[[int, int, int], None]] = None):
        """
        :param alignment: สแกนเฉพาะ address ที่หารด้วยค่านี้ลงตัว (ค่าเริ่มต้น = ขนาดของ dtype เหมือน CE)
        :param tolerance: ความคลาดเคลื่อนที่ยอมรับตอนเทียบ float/double (0 = ตรงเป๊ะ)
        :param max_results: ถ้าเจอเกินนี้ใน first scan จะหยุด (scan.truncated = True)
        :param progress: callback(done_bytes, total_bytes, found) เรียกหลังอ่านแต่ละก้อน
        """
        self.mem = mem
        self.dtype = dtype
        self.signed = signed
        self.np_dtype = _np_dtype(dtype, signed)
        self.itemsize = self.np_dtype.itemsize
        self.is_float = self.np_dtype.kind == 'f'
        self.tolerance = float(tolerance)
        self.max_results = max_results
        self.progress = progress

        self.alignment = alignment or self.itemsize
        if self.alignment < 1 or not (self.alignment % self.itemsize == 0 or self.itemsize % self.alignment == 0):
            raise ValueError(f"alignment must divide or be a multiple of the item size ({self.itemsize})")
        if self.alignment >= self.itemsize:
            self._phases, self._step = [0], self.alignment // self.itemsize
        else:
            self._phases, self._step = list(range(0, self.itemsize, self.alignment)), 1

        self._region_opts = dict(writable_only=writable_only, include_image=include_image,
                                 include_mapped=include_mapped, start=start)
        if end is not None:
            self._region_opts['end'] = end

        self._stop = threading.Event()
        self.truncated = False
        self.cancelled = False
        self._started = False
        self._addrs = np.empty(0, dtype=np.uint64)
        self._values = np.empty(0, dtype=self.np_dtype)

    # ------------------------------------------------------------------ public
    @property
    def count(self) -> int:
        return len(self._addrs)

    @property
    def addresses(self) -> np.ndarray:
        return self._addrs

    @property
    def values(self) -> np.ndarray:
        """ค่าจากการสแกนครั้งล่าสุด"""
        return self._values

    @property
    def results(self) -> ScanResults:
        return ScanResults(self)

    def reset(self) -> 'Scanner':
        """ล้างผล เริ่ม New Scan"""
        self._addrs = np.empty(0, dtype=np.uint64)
        self._values = np.empty(0, dtype=self.np_dtype)
        self._started = False
        self.truncated = False
        self.cancelled = False
        return self

    def stop(self) -> None:
        """ขอยกเลิกการสแกนที่กำลังทำอยู่ (เรียกจาก thread อื่น)"""
        self._stop.set()

    def first(self, *args) -> 'Scanner':
        """first('exact' | 'between' | 'greater' | 'less', ...) ; first(100) = exact"""
        kind, v1, v2 = self._parse(args, _ABSOLUTE)
        self.reset()
        self._stop.clear()
        try:
            with np.errstate(all='ignore'):
                self._do_first(kind, v1, v2)
            self._started = True
        except ScanCancelled:
            self.reset()
            self.cancelled = True
        return self

    def next(self, *args) -> 'Scanner':
        """next(101) / next('changed') / next('between', lo, hi) / next('increased_by', 5) ..."""
        if not self._started:
            raise RuntimeError("call first() before next()")
        kind, v1, v2 = self._parse(args, _ABSOLUTE | _RELATIVE)
        self._stop.clear()
        self.cancelled = False
        try:
            with np.errstate(all='ignore'):
                self._do_next(kind, v1, v2)
        except ScanCancelled:
            self.cancelled = True  # ผลเดิมไม่ถูกแตะ
        return self

    def items(self, limit: int = 20, live: bool = False) -> List[Tuple[int, Number]]:
        """[(address, value), ...]  live=True อ่านค่าปัจจุบันจากโปรเซสตอนนี้"""
        addrs = self._addrs[:limit]
        vals = self._read_values(addrs)[0] if live else self._values[:limit]
        return list(zip(addrs.tolist(), vals.tolist()))

    def show(self, limit: int = 20, live: bool = True) -> None:
        for addr, val in self.items(limit, live):
            print(f"0x{addr:X}  {val}")
        if self.count > limit:
            print(f"... ({self.count - limit:,} more)")

    def __len__(self) -> int:
        return self.count

    def __repr__(self) -> str:
        return f"<Scanner dtype={self.np_dtype} results={self.count:,}>"

    # ---------------------------------------------------------------- internals
    def _check_stop(self) -> None:
        if self._stop.is_set():
            raise ScanCancelled

    def _parse(self, args: tuple, allowed: set) -> Tuple[str, Any, Any]:
        if not args:
            raise TypeError("give a value or a scan type, e.g. scan.first(100) / scan.next('changed')")
        if isinstance(args[0], str):
            kind = args[0].lower().replace(' ', '_')
            kind, rest = _ALIASES.get(kind, kind), args[1:]
        else:
            kind, rest = 'exact', args
        if kind not in allowed:
            raise ValueError(f"scan type {kind!r} not allowed here; use one of {sorted(allowed)}")
        if len(rest) != _NARGS[kind]:
            raise TypeError(f"scan type {kind!r} takes {_NARGS[kind]} value(s), got {len(rest)}")
        return kind, (rest[0] if rest else None), (rest[1] if len(rest) > 1 else None)

    def _make_condition(self, kind: str, v1: Any, v2: Any) -> Callable:
        """คืน cond(cur, prev) -> bool array (หรือ None = ไม่มีตัวไหนตรง)"""
        dt = self.np_dtype.type
        tol = self.tolerance

        # --- เทียบกับค่าก่อนหน้า
        if kind in ('changed', 'unchanged', 'increased', 'decreased'):
            op = {'changed': np.not_equal, 'unchanged': np.equal,
                  'increased': np.greater, 'decreased': np.less}[kind]
            return lambda cur, prev: op(cur, prev)

        if kind in ('increased_by', 'decreased_by'):
            sign = 1 if kind == 'increased_by' else -1
            if self.is_float:
                target = sign * float(v1)
                eff = tol if tol > 0 else 1e-6 * max(1.0, abs(target))
                return lambda cur, prev: np.abs(cur.astype(np.float64) - prev.astype(np.float64) - target) <= eff
            if v1 != math.floor(v1):
                return lambda cur, prev: None
            target = sign * int(v1)
            # คำนวณใน int64 (uint64 ที่ค่าเกิน 2^63 อาจเพี้ยน)
            return lambda cur, prev: (cur.astype(np.int64) - prev.astype(np.int64)) == target

        # --- เทียบกับค่าคงที่ (float)
        if self.is_float:
            if kind == 'exact':
                t = dt(float(v1))
                if tol > 0:
                    return lambda cur, prev: np.abs(cur - t) <= tol
                return lambda cur, prev: cur == t
            if kind == 'between':
                lo, hi = sorted((float(v1), float(v2)))
                lo_t, hi_t = dt(lo - tol), dt(hi + tol)
                return lambda cur, prev: (cur >= lo_t) & (cur <= hi_t)
            t = dt(float(v1))
            if kind == 'greater':
                return lambda cur, prev: cur > t
            return lambda cur, prev: cur < t

        # --- เทียบกับค่าคงที่ (integer): แปลงทุกแบบเป็นช่วง [lo, hi]
        info = np.iinfo(self.np_dtype)
        if kind == 'exact':
            if v1 != math.floor(v1):
                return lambda cur, prev: None
            lo = hi = int(v1)
        elif kind == 'between':
            lo, hi = math.ceil(min(v1, v2)), math.floor(max(v1, v2))
        elif kind == 'greater':
            lo, hi = math.floor(v1) + 1, int(info.max)
        else:  # less
            lo, hi = int(info.min), math.ceil(v1) - 1
        lo, hi = max(lo, int(info.min)), min(hi, int(info.max))
        if lo > hi:
            return lambda cur, prev: None
        if lo == hi:
            t = dt(lo)
            return lambda cur, prev: cur == t
        lo_t, hi_t = dt(lo), dt(hi)
        return lambda cur, prev: (cur >= lo_t) & (cur <= hi_t)

    # ---- first scan
    def _iter_chunks(self, regions):
        size = self.itemsize
        for base, rsize in regions:
            off = 0
            while off < rsize:
                n = min(CHUNK, rsize - off)
                # อ่านเกินมา size-1 ไบต์ กันค่าที่คร่อมรอยต่อ chunk (นับเฉพาะค่าที่เริ่มใน n ไบต์แรก)
                yield base + off, min(n + size - 1, rsize - off), n
                off += n

    def _scan_buffer(self, data: bytes, base: int, limit: int, cond: Callable):
        size = self.itemsize
        out_a, out_v = [], []
        for phase in self._phases:
            cnt = min((len(data) - phase) // size, -(-(limit - phase) // size))
            if cnt <= 0:
                continue
            arr = np.frombuffer(data, dtype=self.np_dtype, count=cnt, offset=phase)
            if self._step > 1:
                arr = arr[::self._step]
            mask = cond(arr, None)
            if mask is None:
                continue
            idx = np.flatnonzero(mask)
            if idx.size == 0:
                continue
            out_a.append(np.uint64(base + phase) + idx.astype(np.uint64) * np.uint64(size * self._step))
            out_v.append(arr[idx])
        if not out_a:
            return None, None
        if len(out_a) == 1:
            return out_a[0], out_v[0]
        a, v = np.concatenate(out_a), np.concatenate(out_v)
        order = np.argsort(a, kind='stable')
        return a[order], v[order]

    def _do_first(self, kind: str, v1: Any, v2: Any) -> None:
        cond = self._make_condition(kind, v1, v2)
        regions = list(self.mem.regions(**self._region_opts))
        total = sum(size for _, size in regions)
        parts_a: List[np.ndarray] = []
        parts_v: List[np.ndarray] = []
        found = done = 0

        for addr, read_len, limit in self._iter_chunks(regions):
            self._check_stop()
            data = self.mem.read_bytes_partial(addr, read_len)
            if len(data) >= self.itemsize:
                a, v = self._scan_buffer(data, addr, limit, cond)
                if a is not None:
                    parts_a.append(a)
                    parts_v.append(v)
                    found += len(a)
            done += limit
            if self.progress:
                self.progress(done, total, found)
            if found >= self.max_results:
                self.truncated = True
                break

        if parts_a:
            self._addrs = np.concatenate(parts_a)
            self._values = np.concatenate(parts_v)

    # ---- next scan
    def _extract(self, data: bytes, offs: np.ndarray) -> np.ndarray:
        """ดึงค่าที่ตำแหน่ง offs (ไบต์) ออกจาก data"""
        size = self.itemsize
        if offs.size == 0:
            return np.empty(0, dtype=self.np_dtype)
        if not (offs % size).any():  # ทุกตัว align เทียบกับต้น buffer -> view ตรงๆ เร็วกว่า
            arr = np.frombuffer(data, dtype=self.np_dtype, count=len(data) // size)
            return arr[offs // size]
        buf = np.frombuffer(data, dtype=np.uint8)
        idx = offs[:, None] + np.arange(size)
        return np.ascontiguousarray(buf[idx]).view(self.np_dtype).reshape(-1)

    def _read_values(self, addrs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """อ่านค่าปัจจุบันของ addrs (เรียงจากน้อยไปมาก) -> (values, ok_mask)"""
        n = len(addrs)
        size = self.itemsize
        out = np.zeros(n, dtype=self.np_dtype)
        ok = np.zeros(n, dtype=bool)
        if n == 0:
            return out, ok

        # รวม address ที่อยู่ใกล้กันเป็นก้อน เพื่อลดจำนวนครั้งที่เรียก ReadProcessMemory
        brk = (np.flatnonzero(np.diff(addrs) > np.uint64(GAP)) + 1).tolist()
        for s, e in zip([0] + brk, brk + [n]):
            i = s
            last = int(addrs[e - 1])
            while i < e:
                self._check_stop()
                base = int(addrs[i])
                if last - base + size <= MAX_READ:
                    j = e
                else:
                    j = i + int(np.searchsorted(addrs[i:e], np.uint64(base + MAX_READ - size + 1), side='left'))
                span = int(addrs[j - 1]) - base + size
                data = self.mem.read_bytes_partial(base, span)
                if len(data) >= size:
                    offs = (addrs[i:j] - np.uint64(base)).astype(np.int64)
                    good = offs + size <= len(data)
                    out[i:j][good] = self._extract(data, offs[good])
                    ok[i:j] = good
                i = j
        return out, ok

    def _do_next(self, kind: str, v1: Any, v2: Any) -> None:
        cond = self._make_condition(kind, v1, v2)
        cur, ok = self._read_values(self._addrs)
        match = cond(cur, self._values)
        keep = ok if match is None else (ok & match)
        self._addrs = self._addrs[keep]
        self._values = cur[keep]
