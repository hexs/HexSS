import sqlite3
import statistics
from typing import Union, Any, Callable, Self


class PointerScanner:
    def __init__(self, mem, dtype: Union[int, str] = 4, count: int = 1, signed: bool = True):
        self.db_path = None
        self.mem = mem
        self.dtype = dtype
        self.count = count
        self.signed = signed

        self.pointers = []
        self.value_frequencies = {}

    def load_pointers_from_db(self, db_path: str, limit: int = 50) -> Self:
        self.db_path = db_path
        query = f"""
        SELECT 
            m.name AS Base_Module, r.moduleoffset AS Base_Offset, 
            r.offset1, r.offset2, r.offset3, r.offset4, r.offset5, 
            r.offset6, r.offset7, r.offset8, r.offset9
        FROM results r
        LEFT JOIN modules m ON r.moduleid = m.moduleid AND r.ptrid = m.ptrid
        ORDER BY RANDOM() LIMIT {limit}
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                print(f"Fetched {len(rows)} pointer records. Creating list...\n")

            for row in rows:
                target_module = row[0]
                base_offset = int(row[1])
                raw_offsets = row[2:11]
                valid_offsets = [int(offset) for offset in raw_offsets if offset is not None]

                # ใช้ API ใหม่ mem.pointer()
                ptr_obj = self.mem.pointer(target_module, base_offset, valid_offsets)
                self.pointers.append(ptr_obj)

        except sqlite3.Error as e:
            print(f"[Database Error]: {e}")

        return self

    def _eval_condition(self, condition: Union[str, Callable], x: Any) -> bool:
        if callable(condition):
            return condition(x)
        elif isinstance(condition, str):
            try:
                return eval(condition, {"__builtins__": None}, {"x": x})
            except Exception as e:
                return False
        return True

    def get_best_pointer(self, filter_cond: Union[str, Callable] = None):
        """หา Address ที่ตรงกันมากที่สุด แล้วคืนค่าเป็น MemoryPointer แบบล็อกเป้า (Static Address)"""
        if not self.pointers: return None

        addresses = []
        for p in self.pointers:
            addr = p.addr()
            # อ่านค่าแบบส่ง Dtype เข้าไปด้วย
            current_value = p.read(dtype=self.dtype, count=self.count, signed=self.signed)

            if addr is not None and current_value is not None:
                if filter_cond is not None and not self._eval_condition(filter_cond, current_value):
                    continue
                addresses.append(addr)

        if not addresses:
            print("ไม่พบ Address ที่ผ่านเงื่อนไข filter_cond")
            return None

        best_address = statistics.mode(addresses)
        # คืนค่ากลับไปเป็น API แบบ Static Address
        return self.mem.address(best_address)