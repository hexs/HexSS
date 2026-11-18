import ctypes
import struct
import copy
import xml.etree.ElementTree as ET
from typing import Optional, List, Union, Dict, Any, Tuple

from .winapi import kernel32, PROCESS_ALL_ACCESS, get_pid, get_module_base
from .pointer_scanner import PointerScanner


class Address:
    def __init__(self, process: 'Memory', address: Optional[int] = None, dtype: Optional[Union[int, str]] = None,
                 module: Optional[str] = None, base_offset: Optional[int] = None,
                 offsets: Optional[List[int]] = None, fallback_last_addr: bool = False):
        self.process = process
        self.static_address = address
        self.dtype = dtype

        self.module = module
        self.base_offset = base_offset
        self.offsets = offsets[::-1] if offsets else []  # รับรูปแบบ Cheat Engine
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

        for offset in self.offsets[:-1]:
            ptr_data = self.process.read_bytes(current_addr, 8)
            if not ptr_data: return self._handle_read_fail()
            val = struct.unpack('Q', ptr_data)[0]
            if val == 0: return self._handle_read_fail()
            current_addr = val + offset

        if self.offsets:
            ptr_data = self.process.read_bytes(current_addr, 8)
            if not ptr_data: return self._handle_read_fail()
            val = struct.unpack('Q', ptr_data)[0]
            if val == 0: return self._handle_read_fail()
            current_addr = val + self.offsets[-1]

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

    def read(self, count: int = 1, dtype: Optional[Union[int, str]] = None, signed: bool = True) -> Any:
        """
        :param dtype: 1, 2, 4, 8, 'float', 'double', 'utf-8', 'utf-16', 'ascii'
        :param count: จำนวนตัวเลขที่จะอ่าน (ได้เป็น List) หรือ ความยาวตัวอักษร (ถ้าเป็น String)
        :param signed: True (ติดลบได้), False (ไม่ติดลบ) (ใช้เฉพาะตัวเลข)
        """

        address = self.addr()
        if not address:
            return None
        _dtype: Union[int, str] = dtype or self.dtype or 4

        if isinstance(_dtype, str) and _dtype.lower() in ('utf-8', 'utf-16', 'utf-16-le', 'ascii'):
            encoding = 'utf-16-le' if _dtype.lower() == 'utf-16' else _dtype
            char_size = 2 if '16' in encoding else 1

            data = self.process.read_bytes(address, count * char_size)
            if not data: return None
            try:
                return data.decode(encoding).split('\x00')[0]
            except UnicodeDecodeError:
                return None

        fmt, total_bytes = self._get_struct_format(_dtype, count, signed)
        data = self.process.read_bytes(address, total_bytes)
        if not data: return None

        unpacked = struct.unpack(fmt, data)
        return unpacked[0] if count == 1 else list(unpacked)

    def write(self, value: Any, dtype: Union[int, str] = 4, signed: bool = True) -> bool:
        address = self.addr()
        if not address:
            return False
        _dtype: Union[int, str] = dtype or self.dtype or 4

        try:
            # กรณีเขียนข้อความ (String)
            if isinstance(_dtype, str) and _dtype.lower() in ('utf-8', 'utf-16', 'utf-16-le', 'ascii'):
                encoding = 'utf-16-le' if _dtype.lower() == 'utf-16' else _dtype
                null_term = b'\x00\x00' if '16' in encoding else b'\x00'
                data = str(value).encode(encoding) + null_term
                return self.process.write_bytes(address, data)

            # กรณีเขียนตัวเลข (รองรับการเขียนแบบ List หรือตัวเดียว)
            val_list = value if isinstance(value, (list, tuple)) else [value]
            fmt, _ = self._get_struct_format(_dtype, len(val_list), signed)
            data = struct.pack(fmt, *val_list)
            return self.process.write_bytes(address, data)

        except Exception as e:
            print(f"Write error: {e}")
            return False

    def __add__(self, other: int) -> 'Address':
        if not isinstance(other, int): raise TypeError("Offsets must be integers")
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
        return self.__add__(-other)

    def __str__(self) -> str:
        address = self.addr()
        return hex(address) if address is not None else "None"


class Memory:
    def __init__(self, target: Union[int, str]):
        self.pid = None
        self.handle = None
        self.module_cache: Dict[str, int] = {}

        if isinstance(target, int):
            self.pid = target
        elif isinstance(target, str):
            self.pid = get_pid(target)
            if not self.pid: raise ValueError(f"Target process not found: '{target}'")

        self.handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.handle: raise PermissionError(f"Cannot access PID {self.pid} (Run as Admin)")

    def get_module_addr(self, module_name: str) -> Optional[int]:
        if module_name not in self.module_cache:
            addr = get_module_base(self.pid, module_name)
            if addr: self.module_cache[module_name] = addr
        return self.module_cache.get(module_name)

    def address(self, address: int, dtype: Optional[Union[int, str]] = None) -> Address:
        """สร้าง Pointer จาก Address คงที่ (Static Address)"""
        return Address(self, address=address, dtype=dtype)

    def pointer(self, target_module: str, base_offset: int, offsets: List[int], dtype: Optional[Union[int, str]] = None,
                fallback_last_addr: bool = False) -> Address:
        """สร้าง Pointer Chain (รูปแบบเดียวกับ CE)"""
        return Address(self, dtype=dtype, module=target_module, base_offset=base_offset, offsets=offsets,
                       fallback_last_addr=fallback_last_addr)

    def from_xml(self, xml_string: str, fallback_last_addr: bool = False) -> Address:
        """สร้าง Pointer โดยก๊อปปี้โค้ดมาจาก Cheat Engine XML"""
        root = ET.fromstring(xml_string.strip())
        address_text = root.find('.//Address').text
        offsets_node = root.find('.//Offsets')

        if '+' in address_text or offsets_node is not None:
            module_name, base_offset_hex = address_text.split('+')
            offsets = [int(offset.text, 16) for offset in
                       root.findall('.//Offsets/Offset')] if offsets_node is not None else []
            return self.pointer(module_name.strip('"'), int(base_offset_hex, 16), offsets, fallback_last_addr)
        else:
            return self.address(int(address_text, 16))

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        success = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size,
                                             ctypes.byref(bytes_read))
        return buffer.raw if success else None

    def write_bytes(self, address: int, data: bytes) -> bool:
        size = len(data)
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t()
        success = kernel32.WriteProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size,
                                              ctypes.byref(bytes_written))
        return bool(success)

    def pointer_scanner(self, dtype: Union[int, str] = 4, count: int = 1, signed: bool = True) -> PointerScanner:
        return PointerScanner(self, dtype=dtype, count=count, signed=signed)

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        self.close()
