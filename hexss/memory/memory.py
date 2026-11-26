import ctypes
import copy
import logging
import operator
import struct
import time
import xml.etree.ElementTree as ET
from typing import Optional, List, Union, Dict, Any, Tuple, Iterator, TYPE_CHECKING

from .winapi import (
    kernel32, get_pid, get_module_base, list_modules, get_pointer_size, get_last_error, format_error,
    MEMORY_BASIC_INFORMATION, PROCESS_DEFAULT_ACCESS, MEM_COMMIT, MEM_MAPPED, MEM_IMAGE,
    PAGE_GUARD, PAGE_NOACCESS, PAGE_WRITABLE_MASK, PAGE_READABLE_MASK,
)
from .pointer_scanner import PointerScanner

if TYPE_CHECKING:
    from .scanner import Scanner

logger = logging.getLogger(__name__)

MAX_USER_ADDRESS = 0x7FFFFFFFFFFF
MODULE_RETRY_SECONDS = 1.0  # หา module ไม่เจอ -> รออย่างน้อยเท่านี้ก่อนถาม Windows ใหม่

_CE_VARIABLE_TYPES = {'byte': 1, '2 bytes': 2, '4 bytes': 4, '8 bytes': 8, 'float': 'float', 'double': 'double'}


class MemoryAccessError(OSError):
    """อ่าน/เขียน memory ไม่สำเร็จ (เกิดเฉพาะตอน strict=True)"""


class Address:
    def __init__(self, process: 'Memory', address: Optional[int] = None, dtype: Optional[Union[int, str]] = None,
                 module: Optional[str] = None, base_offset: Optional[int] = None,
                 offsets: Optional[List[int]] = None, fallback_last_addr: bool = False,
                 signed: bool = True):
        self.process = process
        self.static_address = address
        self.dtype = dtype
        self.signed = signed

        self.module = module
        self.base_offset = base_offset
        self.offsets = offsets[::-1] if offsets else []  # เก็บเรียงตามลำดับที่ใช้จริง
        self.fallback_last_addr = fallback_last_addr
        self._last_addr = None

    def _handle_read_fail(self) -> Optional[int]:
        return self._last_addr if self.fallback_last_addr and self._last_addr is not None else None

    def addr(self) -> Optional[int]:
        if self.static_address is not None:
            return self.static_address

        mod_base = self.process.get_module_addr(self.module)
        if not mod_base: return self._handle_read_fail()

        current_addr = mod_base + self.base_offset

        size = self.process.ptr_size
        fmt = '<Q' if size == 8 else '<I'
        for offset in self.offsets:
            ptr_data = self.process.read_bytes(current_addr, size, strict=False)
            if not ptr_data: return self._handle_read_fail()
            val = struct.unpack(fmt, ptr_data)[0]
            if val == 0 or val > MAX_USER_ADDRESS: return self._handle_read_fail()
            current_addr = val + offset

        self._last_addr = current_addr
        return current_addr

    def _get_struct_format(self, dtype: Union[int, str], count: int, signed: bool) -> Tuple[str, int]:
        """ดึงรูปแบบ struct (format string) และคำนวณขนาด Bytes ตาม dtype"""
        fmt, item_size = '', 0
        if dtype in (1, 2, 4, 8):
            if dtype == 1:
                fmt = 'b' if signed else 'B'
                item_size = 1
            elif dtype == 2:
                fmt = 'h' if signed else 'H'
                item_size = 2
            elif dtype == 4:
                fmt = 'i' if signed else 'I'
                item_size = 4
            elif dtype == 8:
                fmt = 'q' if signed else 'Q'
                item_size = 8
        elif dtype == 'float':
            fmt = 'f'
            item_size = 4
        elif dtype == 'double':
            fmt = 'd'
            item_size = 8
        else:
            raise ValueError(f"Invalid numeric dtype: {dtype}")

        return f"<{count}{fmt}", item_size * count

    def read(
            self,
            count: int = 1,
            dtype: Optional[Union[int, str]] = None,
            signed: Optional[bool] = None,
            strict: Optional[bool] = None
    ) -> Any:
        """
        :param dtype: 1, 2, 4, 8, 'float', 'double', 'utf-8', 'utf-16', 'ascii'
        :param count: จำนวนตัวเลขที่จะอ่าน (ได้เป็น List) หรือ ความยาวตัวอักษร (ถ้าเป็น String)
        :param signed: True (ติดลบได้), False (ไม่ติดลบ) (ใช้เฉพาะตัวเลข) ; None = ใช้ค่าของ Address นี้
        :param strict: True = อ่านไม่ได้ให้ raise MemoryAccessError แทนการคืน None ; None = ใช้ค่าของ Memory
        """
        address = self.addr()
        if strict is None:
            strict = self.process.strict
        if not address:
            if strict:
                raise MemoryAccessError("pointer chain cannot be resolved (module not found or null pointer)")
            return None
        _dtype: Union[int, str] = dtype or self.dtype or 4
        if signed is None:
            signed = self.signed

        if isinstance(_dtype, str) and _dtype.lower() in ('utf-8', 'utf-16', 'utf-16-le', 'ascii'):
            encoding = 'utf-16-le' if _dtype.lower() == 'utf-16' else _dtype
            char_size = 2 if '16' in encoding else 1

            data = self.process.read_bytes(address, count * char_size, strict=strict)
            if not data: return None
            try:
                return data.decode(encoding).split('\x00')[0]
            except UnicodeDecodeError:
                return None

        fmt, total_bytes = self._get_struct_format(_dtype, count, signed)
        data = self.process.read_bytes(address, total_bytes, strict=strict)
        if not data: return None

        unpacked = struct.unpack(fmt, data)
        return unpacked[0] if count == 1 else list(unpacked)

    def write(
            self,
            value: Any,
            dtype: Optional[Union[int, str]] = None,
            signed: Optional[bool] = None,
            strict: Optional[bool] = None
    ) -> bool:
        address = self.addr()
        if strict is None:
            strict = self.process.strict
        if not address:
            if strict:
                raise MemoryAccessError("pointer chain cannot be resolved (module not found or null pointer)")
            return False
        _dtype: Union[int, str] = dtype or self.dtype or 4
        if signed is None:
            signed = self.signed

        try:
            # กรณีเขียนข้อความ (String)
            if isinstance(_dtype, str) and _dtype.lower() in ('utf-8', 'utf-16', 'utf-16-le', 'ascii'):
                encoding = 'utf-16-le' if _dtype.lower() == 'utf-16' else _dtype
                null_term = b'\x00\x00' if '16' in encoding else b'\x00'
                data = str(value).encode(encoding) + null_term
                return self.process.write_bytes(address, data, strict=strict)

            # กรณีเขียนตัวเลข (รองรับการเขียนแบบ List หรือตัวเดียว)
            val_list = value if isinstance(value, (list, tuple)) else [value]
            fmt, _ = self._get_struct_format(_dtype, len(val_list), signed)
            data = struct.pack(fmt, *val_list)
            return self.process.write_bytes(address, data, strict=strict)

        except MemoryAccessError:
            raise
        except Exception as e:
            logger.error("Write error: %s", e)
            return False

    def __add__(self, other: int) -> 'Address':
        try:
            other = operator.index(other)
        except TypeError:
            raise TypeError("Offsets must be integers") from None
        new_obj = copy.copy(self)
        if new_obj.static_address is not None:
            new_obj.static_address += other
        elif new_obj.offsets:
            new_obj.offsets = self.offsets[:]
            new_obj.offsets[-1] += other
        else:
            new_obj.base_offset += other
        return new_obj

    def __sub__(self, other: int) -> 'Address':
        return self.__add__(-operator.index(other))

    def __str__(self) -> str:
        address = self.addr()
        return hex(address) if address is not None else "None"


class Memory:
    def __init__(self, target: Union[int, str], access: int = PROCESS_DEFAULT_ACCESS, strict: bool = False):
        """
        :param target: ชื่อ process (เช่น 'taskmgr.exe') หรือ PID
        :param strict: True = อ่าน/เขียนไม่ได้ให้ raise MemoryAccessError (มีรหัส WinError)
        """
        self.pid = None
        self.handle = None
        self.strict = strict
        self.ptr_size = 8
        self.main_module: Optional[str] = None
        self.module_cache: Dict[str, int] = {}  # key = ชื่อ module ตัวพิมพ์เล็ก
        self._module_failed: Dict[str, float] = {}

        if isinstance(target, int):
            self.pid = target
        elif isinstance(target, str):
            self.pid = get_pid(target)
            if not self.pid: raise ValueError(f"Target process not found: '{target}'")
        else:
            raise TypeError(f"target must be a process name (str) or PID (int), got {type(target).__name__}")

        self.handle = kernel32.OpenProcess(access, False, self.pid)
        if not self.handle:
            code = get_last_error()
            raise PermissionError(f"Cannot open PID {self.pid} [WinError {code}] {format_error(code)} (Run as Admin?)")

        self.ptr_size = get_pointer_size(self.handle)
        if self.ptr_size > ctypes.sizeof(ctypes.c_void_p):
            self.close()
            raise OSError("Target is a 64-bit process but this Python is 32-bit; use 64-bit Python")

        self.refresh_modules()
        if self.main_module is None and isinstance(target, str):
            self.main_module = target

    # ------------------------------------------------------------------ modules
    def refresh_modules(self) -> Dict[str, int]:
        """โหลดรายการ module ใหม่ (เรียกเมื่อ DLL ถูกโหลด/ย้าย) คืน {ชื่อ: base address}"""
        mods = list_modules(self.pid)
        self.module_cache = {name.lower(): base for name, base, _ in mods}
        self._module_failed.clear()
        if mods and self.main_module is None:
            self.main_module = mods[0][0]  # module แรกคือ exe หลักเสมอ
        return {name: base for name, base, _ in mods}

    def get_module_addr(self, module_name: Optional[str] = None) -> Optional[int]:
        """base address ของ module (None = main module)"""
        key = (module_name or self.main_module or '').lower()
        if not key:
            return None
        base = self.module_cache.get(key)
        if base:
            return base

        now = time.monotonic()
        failed_at = self._module_failed.get(key)
        if failed_at is not None and now - failed_at < MODULE_RETRY_SECONDS:
            return None  # เพิ่งหาไม่เจอ ไม่ต้องถาม Windows ซ้ำทุกครั้งที่ addr() ถูกเรียก
        base = get_module_base(self.pid, key)
        if base:
            self.module_cache[key] = base
            self._module_failed.pop(key, None)
            return base
        self._module_failed[key] = now
        return None

    # ------------------------------------------------------------------ address factories
    def address(self, address: int, dtype: Optional[Union[int, str]] = None, signed: bool = True) -> Address:
        """สร้าง Pointer จาก Address คงที่ (Static Address)"""
        return Address(self, address=address, dtype=dtype, signed=signed)

    def pointer(self, base_offset: Union[int, str], offsets: Optional[List[int]] = None,
                dtype: Optional[Union[int, str]] = None, *, module: Optional[str] = None,
                fallback_last_addr: bool = False, signed: bool = True) -> Address:
        """
        สร้าง Pointer Chain (รูปแบบเดียวกับ CE)

            mem.pointer(0x550CA0, dtype=4)                          # main module
            mem.pointer(0x1234, [0x10, 0x8], module='UnityPlayer.dll')
            mem.pointer('UnityPlayer.dll+1234', [0x10, 0x8])        # แบบ string ของ CE
        """
        if isinstance(base_offset, str):
            mod_text, plus, off_text = base_offset.strip().rpartition('+')
            if not plus:
                raise TypeError(
                    "pointer() no longer takes the module name as first argument. "
                    f"Use mem.pointer(0x..., offsets, module={base_offset!r}) or mem.pointer('{base_offset}+HEX', offsets)")
            if module is not None:
                raise ValueError("give the module either in the string ('mod+HEX') or in module=, not both")
            module = mod_text.strip().strip('"')
            base_offset = int(off_text, 16)
        elif isinstance(base_offset, bool) or not isinstance(base_offset, int):
            raise TypeError(f"base_offset must be int or 'module+HEX' string, got {type(base_offset).__name__}")

        if module is None and self.main_module is None:
            raise ValueError("main module of this process is unknown; pass module='name.exe'")
        return Address(self, dtype=dtype, module=module, base_offset=base_offset, offsets=list(offsets or []),
                       fallback_last_addr=fallback_last_addr, signed=signed)

    def from_xml(self, xml_string: str, fallback_last_addr: bool = False) -> Address:
        """สร้าง Pointer โดยก๊อปปี้โค้ดมาจาก Cheat Engine XML"""
        root = ET.fromstring(xml_string.strip())
        address_text = (root.find('.//Address').text or '').strip()
        offsets = [int(offset.text, 16) for offset in root.findall('.//Offsets/Offset')]
        var_type = root.find('.//VariableType')
        dtype = _CE_VARIABLE_TYPES.get((var_type.text or '').strip().lower()) if var_type is not None else None

        if '+' in address_text:
            module_name, _, base_hex = address_text.rpartition('+')
            return self.pointer(int(base_hex, 16), offsets, dtype, module=module_name.strip().strip('"'),
                                fallback_last_addr=fallback_last_addr)
        if offsets:
            raise ValueError("pointer chain whose base is a plain address (no module) is not supported")
        return self.address(int(address_text, 16), dtype)

    # ------------------------------------------------------------------ raw access
    def _access_error(self, op: str, address: int, size: int) -> MemoryAccessError:
        code = get_last_error()
        return MemoryAccessError(f"Cannot {op} {size} bytes at 0x{address:X} [WinError {code}] {format_error(code)}")

    def read_bytes(self, address: int, size: int, strict: Optional[bool] = None) -> Optional[bytes]:
        """อ่านครบ size ไบต์ ถ้าอ่านไม่ได้/ได้ไม่ครบ คืน None (หรือ raise ถ้า strict)"""
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        success = kernel32.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(bytes_read))
        if success:
            return buffer.raw
        if self.strict if strict is None else strict:
            raise self._access_error('read', address, size)
        return None

    def read_bytes_partial(self, address: int, size: int) -> bytes:
        """อ่านเท่าที่อ่านได้จริง (ใช้ตอนสแกน) ถ้าอ่านไม่ได้เลยคืน b''"""
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        kernel32.ReadProcessMemory(self.handle, address, buffer, size, ctypes.byref(bytes_read))
        return bytes(memoryview(buffer)[:bytes_read.value])

    def write_bytes(self, address: int, data: bytes, strict: Optional[bool] = None) -> bool:
        size = len(data)
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t()
        success = bool(kernel32.WriteProcessMemory(self.handle, address, buffer, size, ctypes.byref(bytes_written)))
        if not success and (self.strict if strict is None else strict):
            raise self._access_error('write', address, size)
        return success

    def regions(self, writable_only: bool = True, include_image: bool = True, include_mapped: bool = False,
                start: int = 0, end: int = MAX_USER_ADDRESS) -> Iterator[Tuple[int, int]]:
        """
        ไล่ memory region ของ process (VirtualQueryEx) แล้ว yield (base_address, size)
        เฉพาะ region ที่ commit แล้ว อ่านได้ และไม่ใช่ guard page

        :param writable_only: True = เฉพาะที่เขียนได้ (ค่าเริ่มต้นของ Cheat Engine), False = อ่านได้ทั้งหมด
        :param include_image: รวม region ของ exe/dll (MEM_IMAGE) -> static data อยู่ตรงนี้
        :param include_mapped: รวม memory-mapped file/shared memory (MEM_MAPPED)
        """
        wanted = PAGE_WRITABLE_MASK if writable_only else PAGE_READABLE_MASK
        mbi = MEMORY_BASIC_INFORMATION()
        mbi_size = ctypes.sizeof(mbi)
        addr = start

        while addr < end:
            if not kernel32.VirtualQueryEx(self.handle, addr, ctypes.byref(mbi), mbi_size):
                break
            base = mbi.BaseAddress or 0
            next_addr = base + mbi.RegionSize
            if next_addr <= addr:  # กัน loop ไม่จบ
                break

            protect = mbi.Protect
            ok = bool(mbi.State == MEM_COMMIT
                      and not (protect & (PAGE_GUARD | PAGE_NOACCESS))
                      and (protect & 0xFF) & wanted)
            if ok:
                if mbi.Type == MEM_IMAGE:
                    ok = include_image
                elif mbi.Type == MEM_MAPPED:
                    ok = include_mapped
                # MEM_PRIVATE รวมเสมอ
            if ok:
                s, e = max(base, start), min(next_addr, end)
                if e > s:
                    yield s, e - s
            addr = next_addr

    def pointer_scanner(self, dtype: Union[int, str] = 4, count: int = 1, signed: bool = True) -> PointerScanner:
        return PointerScanner(self, dtype=dtype, count=count, signed=signed)

    def newscan(self, dtype: Union[int, str] = 4, signed: bool = True, **kwargs) -> 'Scanner':
        """สร้าง Scanner แบบ Cheat Engine (first scan / next scan) — ดู scanner.py"""
        from .scanner import Scanner  # import ตอนใช้ เพื่อให้ numpy เป็น dependency เฉพาะส่วนสแกน
        return Scanner(self, dtype=dtype, signed=signed, **kwargs)

    # ------------------------------------------------------------------ lifecycle
    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> 'Memory':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        self.close()
