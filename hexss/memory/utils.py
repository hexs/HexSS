import ctypes
from ctypes import wintypes
import struct
import copy

# --- Windows API Constants ---
PROCESS_ALL_ACCESS = 0x1F0FFF
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010


# --- Structures ---
class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(wintypes.BYTE)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260)
    ]


k32 = ctypes.windll.kernel32


# --- Helper Functions ---
def get_pid(process_name):
    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1: return None
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    if k32.Process32First(snapshot, ctypes.byref(entry)):
        while True:
            try:
                name = entry.szExeFile.decode('utf-8')
            except:
                name = entry.szExeFile.decode('mbcs')
            if name.lower() == process_name.lower():
                k32.CloseHandle(snapshot)
                return entry.th32ProcessID
            if not k32.Process32Next(snapshot, ctypes.byref(entry)): break
    k32.CloseHandle(snapshot)
    return None


def get_module_base(pid, module_name):
    snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snapshot == -1: return None
    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)
    if k32.Module32First(snapshot, ctypes.byref(entry)):
        while True:
            try:
                name = entry.szModule.decode('utf-8')
            except:
                name = entry.szModule.decode('mbcs')
            if name.lower() == module_name.lower():
                k32.CloseHandle(snapshot)
                return ctypes.addressof(entry.modBaseAddr.contents)
            if not k32.Module32Next(snapshot, ctypes.byref(entry)): break
    k32.CloseHandle(snapshot)
    return None


class MemoryPointer:
    TYPE_MAP = {
        # Signed (ติดลบได้)
        1: ('b', 1), '1': ('b', 1), 'byte': ('b', 1),
        2: ('h', 2), '2': ('h', 2), 'short': ('h', 2),
        4: ('i', 4), '4': ('i', 4), int: ('i', 4), 'int': ('i', 4),
        8: ('q', 8), '8': ('q', 8), 'longlong': ('q', 8),

        # Unsigned (ไม่ติดลบ)
        'u1': ('B', 1), 'ubyte': ('B', 1),
        'u2': ('H', 2), 'ushort': ('H', 2),
        'u4': ('I', 4), 'uint': ('I', 4),
        'u8': ('Q', 8), 'ulonglong': ('Q', 8),

        # Floats
        'f': ('f', 4), 'float': ('f', 4), float: ('f', 4),
        'd': ('d', 8), 'double': ('d', 8)
    }

    def __init__(self, process, dtype, address=None, module=None, base_offset=None, offsets=None):
        self.process = process
        self.module = module
        self.base_offset = base_offset
        self.offsets = offsets if offsets else []
        self.static_address = address

        if dtype not in self.TYPE_MAP:
            raise ValueError(f"Unknown dtype: {dtype}")

        self.struct_fmt, self.size = self.TYPE_MAP[dtype]

    @property
    def addr(self):
        if self.static_address is not None:
            return self.static_address

        mod_base = self.process.get_module_addr(self.module)
        if not mod_base: return 0

        current_addr = mod_base + self.base_offset

        for offset in self.offsets[:-1]:
            ptr = self.process.read_bytes(current_addr, 8)
            if not ptr: return 0
            val = struct.unpack('Q', ptr)[0]
            if val == 0: return 0
            current_addr = val + offset

        if self.offsets:
            ptr = self.process.read_bytes(current_addr, 8)
            if not ptr: return 0
            val = struct.unpack('Q', ptr)[0]
            if val == 0: return 0
            return val + self.offsets[-1]

        return current_addr

    def read(self):
        address = self.addr
        if address == 0: return None
        data = self.process.read_bytes(address, self.size)
        if not data: return None
        return struct.unpack(self.struct_fmt, data)[0]

    def write(self, value):
        address = self.addr
        if address == 0: return False
        try:
            data = struct.pack(self.struct_fmt, value)
            return self.process.write_bytes(address, data)
        except Exception as e:
            print(f"Write error: {e}")
            return False

    def __add__(self, other):
        if not isinstance(other, int): raise TypeError("Can only add integer offsets")
        new_obj = copy.copy(self)
        if new_obj.static_address is not None:
            new_obj.static_address += other
        elif new_obj.offsets:
            new_obj.offsets = self.offsets[:]
            new_obj.offsets[-1] += other
        else:
            new_obj.base_offset += other
        return new_obj

    def __sub__(self, other):
        return self.__add__(-other)

    def __str__(self):
        return hex(self.addr)


class Memory:
    def __init__(self, target):
        self.pid = None
        self.handle = None
        self.module_cache = {}

        if isinstance(target, int):
            self.pid = target
        elif isinstance(target, str):
            self.pid = get_pid(target)
            if not self.pid:
                raise Exception(f"Process '{target}' not found")

        self.handle = k32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.handle:
            raise Exception(f"Failed to open process PID {self.pid}")

    def get_module_addr(self, module_name):
        if module_name in self.module_cache:
            return self.module_cache[module_name]

        addr = get_module_base(self.pid, module_name)
        if addr:
            self.module_cache[module_name] = addr
        return addr

    def set_addr(self, address, dtype: int | str = 4):
        return MemoryPointer(self, dtype, address=address)

    def set_pointer(self, target_module, base_offset, offsets, dtype):
        return MemoryPointer(self, dtype, module=target_module, base_offset=base_offset, offsets=offsets)

    def read_bytes(self, address, size):
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        success = k32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read))
        return buffer.raw if success else None

    def write_bytes(self, address, data):
        size = len(data)
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t()
        success = k32.WriteProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size,
                                         ctypes.byref(bytes_written))
        return success

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None

    def __del__(self):
        self.close()


if __name__ == "__main__":
    import time

    mem = Memory("xdt.exe")

    # z_pos = mem.set_addr(0x19FD3EF33E4, float)
    # or
    z_pos = mem.set_pointer(
        target_module="mono-2.0-sgen.dll",
        base_offset=0x004CEAA0,
        offsets=[0x0, 0x18, 0x18, 0x60, 0x680, 0x16C],
        dtype='float'
    )

    x_pos = z_pos - 4
    y_pos = z_pos + 4
    while True:
        x_val = x_pos.read()
        y_val = y_pos.read()
        z_val = z_pos.read()

        x_str = f"{x_val:.2f}" if x_val is not None else "None"
        y_str = f"{y_val:.2f}" if y_val is not None else "None"
        z_str = f"{z_val:.2f}" if z_val is not None else "None"

        print(end=f"\r[Pointer] X: {x_str} Y: {y_str} Z: {z_str}")
        time.sleep(0.1)

