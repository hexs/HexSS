from __future__ import annotations

import logging
import sqlite3
from collections import Counter
from typing import Union, Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PointerScanner:
    def __init__(self, mem, dtype: Union[int, str] = 4, count: int = 1, signed: bool = True):
        self.db_path = None
        self.mem = mem
        self.dtype = dtype
        self.count = count
        self.signed = signed

        self.pointers: List[Any] = []
        # {address: จำนวน pointer ที่ชี้มาที่ address นั้น} จากการเรียก get_best_pointer() ครั้งล่าสุด
        self.value_frequencies: Dict[int, int] = {}

    def load_pointers_from_db(self, db_path: str, limit: int = 50) -> PointerScanner:
        """โหลด pointer แบบสุ่ม `limit` ตัวจากไฟล์ผลของ Cheat Engine pointer scan (.sqlite)"""
        self.db_path = db_path
        self.pointers = []
        query = """
        SELECT 
            m.name AS Base_Module, r.moduleoffset AS Base_Offset, 
            r.offset1, r.offset2, r.offset3, r.offset4, r.offset5, 
            r.offset6, r.offset7, r.offset8, r.offset9
        FROM results r
        LEFT JOIN modules m ON r.moduleid = m.moduleid AND r.ptrid = m.ptrid
        ORDER BY RANDOM() LIMIT ?
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(query, (int(limit),)).fetchall()
            logger.info("Fetched %d pointer records", len(rows))
        except sqlite3.Error as e:
            logger.error("[Database Error]: %s", e)
            return self

        for row in rows:
            target_module = row[0]  # None = ไม่มีชื่อ module -> ใช้ main module
            base_offset = int(row[1])
            valid_offsets = [int(offset) for offset in row[2:11] if offset is not None]
            self.pointers.append(self.mem.pointer(base_offset, valid_offsets, module=target_module))

        return self

    def get_best_pointer(self, filter_cond: Optional[Callable[[Any], bool]] = None):
        """
        หา Address ที่ pointer ชี้มาตรงกันมากที่สุด แล้วคืนเป็น Address แบบล็อกเป้า (Static Address)

        :param filter_cond: ฟังก์ชัน cond(value) -> bool กรองค่าที่อ่านได้ (ถ้า count > 1 value จะเป็น list)
        """
        if filter_cond is not None and not callable(filter_cond):
            raise TypeError("filter_cond must be a callable, e.g. lambda x: 0 <= x <= 5")
        if not self.pointers:
            return None

        counter: Counter = Counter()
        for p in self.pointers:
            addr = p.addr()
            if addr is None:
                continue
            current_value = p.read(dtype=self.dtype, count=self.count, signed=self.signed)
            if current_value is None:
                continue
            if filter_cond is not None and not filter_cond(current_value):
                continue
            counter[addr] += 1

        self.value_frequencies = dict(counter)
        if not counter:
            logger.warning("No pointer passed filter_cond (or none could be read)")
            return None

        best_address, _ = counter.most_common(1)[0]
        return self.mem.address(best_address, self.dtype, self.signed)
