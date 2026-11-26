from .memory import Memory, Address, MemoryAccessError
from .pointer_scanner import PointerScanner


def __getattr__(name):
    # import ตอนใช้ เพื่อให้ numpy เป็น dependency เฉพาะส่วนสแกน
    if name == 'Scanner':
        from .scanner import Scanner
        return Scanner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
