import ctypes
import time
from ctypes import wintypes
from typing import List, Optional, Tuple

# --- Process access rights ---
PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
# สิทธิ์ที่จำเป็นจริงๆ สำหรับ อ่าน/เขียน/สแกน (น้อยกว่า ALL_ACCESS → โดนปฏิเสธน้อยกว่า)
PROCESS_DEFAULT_ACCESS = (PROCESS_VM_OPERATION | PROCESS_VM_READ |
                          PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION)

# --- Toolhelp ---
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_BAD_LENGTH = 24  # Toolhelp snapshot ของ process ที่กำลังโหลด module -> ต้องลองใหม่

# --- VirtualQueryEx: MEMORY_BASIC_INFORMATION.State / Type / Protect ---
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100

PAGE_WRITABLE_MASK = (PAGE_READWRITE | PAGE_WRITECOPY |
                      PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY)
PAGE_READABLE_MASK = PAGE_WRITABLE_MASK | PAGE_READONLY | PAGE_EXECUTE_READ

# แยก instance ของตัวเอง เพื่อไม่ให้ argtypes ไปชนกับไลบรารีอื่นที่ใช้ ctypes.windll
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


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
        ("th32DefaultHeapID", ctypes.c_size_t),  # ULONG_PTR
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260)
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        *([("PartitionId", wintypes.WORD)] if ctypes.sizeof(ctypes.c_void_p) == 8 else []),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


# --- Function signatures (สำคัญมากบน 64-bit: ไม่ตั้ง จะตัด address/handle เหลือ 32-bit) ---
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL

kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
                                        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.restype = wintypes.BOOL

kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                                    ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE

for _fn in (kernel32.Process32First, kernel32.Process32Next):
    _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    _fn.restype = wintypes.BOOL
for _fn in (kernel32.Module32First, kernel32.Module32Next):
    _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
    _fn.restype = wintypes.BOOL


kernel32.IsWow64Process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
kernel32.IsWow64Process.restype = wintypes.BOOL

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE

# --- Helper Functions ---
def get_last_error() -> int:
    return ctypes.get_last_error()


def format_error(code: int) -> str:
    return ctypes.FormatError(code).strip()


def _decode(raw: bytes) -> str:
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('mbcs', errors='ignore')


def _open_snapshot(flags: int, pid: int):
    for _ in range(10):
        handle = kernel32.CreateToolhelp32Snapshot(flags, pid)
        if handle not in (None, INVALID_HANDLE_VALUE):
            return handle
        if ctypes.get_last_error() != ERROR_BAD_LENGTH:
            break
        time.sleep(0.005)
    return None


def list_processes() -> List[Tuple[int, str]]:
    """[(pid, exe_name), ...]"""
    snapshot = _open_snapshot(TH32CS_SNAPPROCESS, 0)
    result: List[Tuple[int, str]] = []
    if snapshot is None:
        return result
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = kernel32.Process32First(snapshot, ctypes.byref(entry))
        while ok:
            result.append((entry.th32ProcessID, _decode(entry.szExeFile)))
            ok = kernel32.Process32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def get_pids(process_name: str) -> List[int]:
    """pid ของทุก process ที่ชื่อตรง (ไม่สนตัวพิมพ์เล็ก/ใหญ่)"""
    name = process_name.lower()
    return [pid for pid, exe in list_processes() if exe.lower() == name]


def get_pid(process_name: str) -> Optional[int]:
    pids = get_pids(process_name)
    return pids[0] if pids else None


def list_modules(pid: int) -> List[Tuple[str, int, int]]:
    """[(module_name, base_address, size), ...]  ตัวแรกคือ exe หลักเสมอ"""
    snapshot = _open_snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    result: List[Tuple[str, int, int]] = []
    if snapshot is None:
        return result
    try:
        entry = MODULEENTRY32()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32)
        ok = kernel32.Module32First(snapshot, ctypes.byref(entry))
        while ok:
            base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value or 0
            result.append((_decode(entry.szModule), base, entry.modBaseSize))
            ok = kernel32.Module32Next(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def get_main_module(pid: int) -> Optional[Tuple[str, int]]:
    mods = list_modules(pid)
    return (mods[0][0], mods[0][1]) if mods else None


def get_module_base(pid: int, module_name: str) -> Optional[int]:
    name = module_name.lower()
    for mod_name, base, _ in list_modules(pid):
        if mod_name.lower() == name:
            return base
    return None


def _is_wow64(handle) -> bool:
    flag = wintypes.BOOL()
    return bool(kernel32.IsWow64Process(handle, ctypes.byref(flag))) and bool(flag.value)


def get_pointer_size(handle) -> int:
    """ขนาด pointer (4 หรือ 8 ไบต์) ของ process เป้าหมาย"""
    if _is_wow64(handle):  # โปรแกรม 32-bit บน Windows 64-bit
        return 4
    if ctypes.sizeof(ctypes.c_void_p) == 8 or _is_wow64(kernel32.GetCurrentProcess()):
        return 8  # Windows 64-bit และไม่ใช่ WOW64 -> เป้าหมายเป็น 64-bit
    return 4  # Windows 32-bit
