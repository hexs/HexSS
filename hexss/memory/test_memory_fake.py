"""ทดสอบ memory.py / pointer_scanner.py / scanner.py แบบ end-to-end ด้วย winapi ปลอม (รันได้ทุก OS)"""
import ctypes, importlib, os, shutil, sqlite3, struct, sys, tempfile, time, types
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "hexss_memory"

# ---------- fake winapi ----------
FAKE = r'''
import ctypes
PROCESS_DEFAULT_ACCESS = 0x43A
MEM_COMMIT, MEM_FREE, MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE = 0x1000, 0x10000, 0x20000, 0x40000, 0x1000000
PAGE_NOACCESS, PAGE_READONLY, PAGE_READWRITE, PAGE_GUARD = 1, 2, 4, 0x100
PAGE_WRITABLE_MASK = 0x4 | 0x8 | 0x40 | 0x80
PAGE_READABLE_MASK = PAGE_WRITABLE_MASK | 0x2 | 0x20

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.c_uint32), ("PartitionId", ctypes.c_uint16),
                ("RegionSize", ctypes.c_size_t), ("State", ctypes.c_uint32),
                ("Protect", ctypes.c_uint32), ("Type", ctypes.c_uint32)]

class World:  # สถานะของ process จำลอง
    pid = 4242; ptr = 8; handle = 0x1234
    modules = []; regions = []   # regions: dict(base, data, protect, type)
    last_error = 0; calls = {"module_base": 0}
W = World()

class K32:
    def OpenProcess(self, access, inherit, pid):
        if pid == W.pid: return W.handle
        W.last_error = 5; return None
    def CloseHandle(self, h): return 1
    def _find(self, addr):
        for r in W.regions:
            if r["base"] <= addr < r["base"] + len(r["data"]): return r
    def ReadProcessMemory(self, h, addr, buf, size, nref):
        r = self._find(addr)
        if r is None:
            nref._obj.value = 0; W.last_error = 299; return 0
        off = addr - r["base"]; n = min(size, len(r["data"]) - off)
        ctypes.memmove(buf, bytes(r["data"][off:off + n]), n)
        nref._obj.value = n
        if n < size: W.last_error = 299; return 0
        return 1
    def WriteProcessMemory(self, h, addr, buf, size, nref):
        r = self._find(addr)
        if r is None or addr - r["base"] + size > len(r["data"]):
            W.last_error = 998; return 0
        off = addr - r["base"]; r["data"][off:off + size] = ctypes.string_at(buf, size); return 1
    def VirtualQueryEx(self, h, addr, mbi_ref, size):
        mbi = mbi_ref._obj
        regs = sorted(W.regions, key=lambda r: r["base"])
        for r in regs:
            if r["base"] <= addr < r["base"] + len(r["data"]):
                mbi.BaseAddress, mbi.RegionSize = r["base"], len(r["data"])
                mbi.State, mbi.Protect, mbi.Type = MEM_COMMIT, r["protect"], r["type"]; return size
            if addr < r["base"]:
                mbi.BaseAddress, mbi.RegionSize = addr, r["base"] - addr
                mbi.State, mbi.Protect, mbi.Type = MEM_FREE, PAGE_NOACCESS, 0; return size
        return 0
kernel32 = K32()
def get_last_error(): return W.last_error
def format_error(c): return {5: "Access is denied", 299: "partial copy", 998: "invalid access"}.get(c, "?")
def get_pids(name): return [W.pid] if name.lower() == "game.exe" else []
def get_pid(name): return W.pid if name.lower() == "game.exe" else None
def list_modules(pid): return list(W.modules)
def get_module_base(pid, name):
    W.calls["module_base"] += 1
    for n, b, s in W.modules:
        if n.lower() == name.lower(): return b
def get_pointer_size(h): return W.ptr
'''

def load(ptr):
    root = Path(tempfile.mkdtemp())
    pkg = root / "fakepkg"; pkg.mkdir()
    for f in ("memory.py", "pointer_scanner.py", "scanner.py", "__init__.py"):
        shutil.copy(SRC / f, pkg / f)
    (pkg / "winapi.py").write_text(FAKE)
    for m in [m for m in sys.modules if m == "fakepkg" or m.startswith("fakepkg.")]: del sys.modules[m]
    sys.path.insert(0, str(root))
    pk = importlib.import_module("fakepkg")
    wa = importlib.import_module("fakepkg.winapi")
    W = wa.W; W.ptr = ptr
    IMG, HEAP = 0x140000000, 0x2000000
    pfmt = "<Q" if ptr == 8 else "<I"
    if ptr == 4: IMG = 0x400000
    img = bytearray(0x2000); heap = bytearray(0x2000)
    struct.pack_into(pfmt, img, 0x100, HEAP + 0x40)        # base+0x100 -> HEAP+0x40
    struct.pack_into(pfmt, heap, 0x50, HEAP + 0x800)       # HEAP+0x40+0x10 -> HEAP+0x800
    struct.pack_into("<i", heap, 0x808, 777)               # HEAP+0x800+0x8 = 777
    struct.pack_into("<f", heap, 0x900, 3.5)
    W.modules = [("game.exe", IMG, 0x10000), ("Other.dll", 0x7ff000000000 if ptr == 8 else 0x70000000, 0x1000)]
    W.regions = [
        dict(base=IMG, data=img, protect=4, type=0x1000000),                  # image RW
        dict(base=IMG + 0x2000, data=bytearray(0x1000), protect=2, type=0x1000000),  # image RO
        dict(base=HEAP, data=heap, protect=4, type=0x20000),                  # private RW
        dict(base=HEAP + 0x10000, data=bytearray(0x1000), protect=4 | 0x100, type=0x20000),  # guard
        dict(base=HEAP + 0x20000, data=bytearray(0x1000), protect=4, type=0x40000),  # mapped
        dict(base=HEAP + 0x30000, data=bytearray(0x1000), protect=2, type=0x20000),  # private RO
    ]
    return pk, wa, W, IMG, HEAP

ok = lambda name: print("ok  ", name)

for ptr in (8, 4):
    print(f"--- ptr_size={ptr}")
    pk, wa, W, IMG, HEAP = load(ptr)
    Memory, MemoryAccessError = pk.Memory, pk.MemoryAccessError

    # init
    for bad in (1.5, None, True):
        try: Memory(bad); raise SystemExit("should fail")
        except TypeError: pass
    try: Memory("nope.exe"); raise SystemExit("should fail")
    except ValueError: pass
    try: Memory(9999); raise SystemExit("should fail")
    except PermissionError as e: assert "WinError 5" in str(e)
    mem = Memory("game.exe"); assert mem.main_module == "game.exe" and mem.ptr_size == ptr and mem.pid == 4242
    mem_pid = Memory(4242); assert mem_pid.main_module == "game.exe"   # PID -> หา main module เอง
    ok("init / main module from PID")

    # pointer forms + chain
    for p in (mem.pointer(0x100, [0x8, 0x10], 4),
              mem.pointer("game.exe+100", [0x8, 0x10], 4),
              mem.pointer('"game.exe"+0x100', [0x8, 0x10], 4),
              mem.pointer(0x100, [0x8, 0x10], 4, module="GAME.EXE"),
              mem_pid.pointer(0x100, [0x8, 0x10], 4)):
        assert p.addr() == HEAP + 0x808 and p.read() == 777, p.addr()
    p = mem.pointer(0x100, [0x8, 0x10], 4)
    assert (p + 4).addr() == HEAP + 0x80C and (p - 4).addr() == HEAP + 0x804
    import numpy as np
    assert (p + np.int64(4)).addr() == HEAP + 0x80C
    try: p + 1.5; raise SystemExit("should fail")
    except TypeError: pass
    assert mem.pointer(0x100, dtype=4).addr() == IMG + 0x100          # ไม่มี offsets = base+offset ตรงๆ
    ok("pointer forms / chain / arithmetic")

    # legacy / invalid pointer() usage
    for args, kw, exc in [(("game.exe", 0x100, []), {}, TypeError), ((1.5,), {}, TypeError),
                          (("a.dll+10",), {"module": "b.dll"}, ValueError)]:
        try: mem.pointer(*args, **kw); raise SystemExit(f"should fail {args}")
        except exc as e: pass
    ok("pointer() rejects legacy form with hint")

    # read / write / dtype / signed
    a = mem.address(HEAP + 0x808, 4)
    assert a.read() == 777 and a.write(-5) and a.read() == -5 and a.read(signed=False) == 2**32 - 5
    assert mem.address(HEAP + 0x808, 4, signed=False).read() == 2**32 - 5
    assert mem.address(HEAP + 0x900, "float").read() == 3.5
    assert a.write([1, 2]) and a.read(count=2) == [1, 2]
    assert a.write("hi", dtype="utf-8") and a.read(dtype="utf-8", count=4) == "hi"
    ok("read/write/dtype/signed")

    # strict / error codes
    bad = mem.address(0x10, 4)
    assert bad.read() is None and bad.write(1) is False
    mem.strict = True
    try: bad.read(); raise SystemExit("should raise")
    except MemoryAccessError as e: assert "WinError 299" in str(e) and "0x10" in str(e)
    try: bad.write(1); raise SystemExit("should raise")
    except MemoryAccessError as e: assert "WinError 998" in str(e)
    try: mem.pointer(0x100, [1, 2], module="missing.dll").read(); raise SystemExit("should raise")
    except MemoryAccessError as e: assert "pointer chain" in str(e)
    assert bad.read(strict=False) is None
    mem.strict = False
    ok("strict mode")

    # broken chain / fallback_last_addr / module-miss cache
    pf = mem.pointer(0x100, [0x8, 0x10], 4, fallback_last_addr=True)
    assert pf.addr() == HEAP + 0x808
    struct.pack_into("<Q" if ptr == 8 else "<I", W.regions[0]["data"], 0x100, 0)   # null pointer
    assert pf.addr() == HEAP + 0x808                      # fallback
    assert mem.pointer(0x100, [0x8, 0x10], 4).addr() is None and mem.pointer(0x100, [0x8, 0x10], 4).read() is None
    struct.pack_into("<Q" if ptr == 8 else "<I", W.regions[0]["data"], 0x100, HEAP + 0x40)
    m = mem.pointer(0x10, [], module="ghost.dll")
    before = W.calls["module_base"]
    for _ in range(50): assert m.addr() is None
    assert W.calls["module_base"] - before == 1, W.calls   # ถามแค่ครั้งเดียวภายใน TTL
    time.sleep(1.05); m.addr(); assert W.calls["module_base"] - before == 2
    W.modules.append(("ghost.dll", 0x5000000, 0x100))     # โหลดทีหลัง -> เจอหลังหมด TTL
    time.sleep(1.05); assert m.addr() == 0x5000010
    assert "ghost.dll" in mem.refresh_modules()
    ok("broken chain / fallback / module-miss cache")

    # regions
    r = list(mem.regions())
    assert r == sorted([(IMG, 0x2000), (HEAP, 0x2000)]), [(hex(a), hex(b)) for a, b in r]
    r2 = list(mem.regions(writable_only=False))
    assert (IMG + 0x2000, 0x1000) in r2 and (HEAP + 0x30000, 0x1000) in r2 and (HEAP + 0x10000, 0x1000) not in r2
    assert (HEAP + 0x20000, 0x1000) not in r2 and (HEAP + 0x20000, 0x1000) in list(mem.regions(include_mapped=True))
    assert list(mem.regions(include_image=False)) == [(HEAP, 0x2000)]
    assert list(mem.regions(start=HEAP + 0x100, end=HEAP + 0x200)) == [(HEAP + 0x100, 0x100)]
    ok("regions filters")

    # scanner end-to-end ผ่าน Memory
    struct.pack_into("<i", W.regions[2]["data"], 0x808, 777)
    sc = mem.newscan(dtype=4); sc.first(777)
    assert HEAP + 0x808 in sc.addresses.tolist(), sc.addresses
    struct.pack_into("<i", W.regions[2]["data"], 0x808, 778)
    sc.next(778); assert sc.addresses.tolist() == [HEAP + 0x808]
    assert sc.results[0].read() == 778 and sc.results[0].dtype == 4
    sc.results[0].write(999); sc.next(999); assert sc.count == 1
    ok("newscan end-to-end")

    # from_xml
    xml = f'''<CheatTable><CheatEntries><CheatEntry><VariableType>4 Bytes</VariableType>
      <Address>"game.exe"+100</Address><Offsets><Offset>8</Offset><Offset>10</Offset></Offsets></CheatEntry></CheatEntries></CheatTable>'''
    x = mem.from_xml(xml); assert x.addr() == HEAP + 0x808 and x.dtype == 4
    fx = mem.from_xml("<CheatEntry><VariableType>Float</VariableType><Address>game.exe+100</Address></CheatEntry>")
    assert fx.dtype == "float"
    try: mem.from_xml("<CheatEntry><Address>7FF000</Address><Offsets><Offset>8</Offset></Offsets></CheatEntry>"); raise SystemExit("x")
    except ValueError: pass
    ok("from_xml")

    # PointerScanner + sqlite (schema แบบ CE)
    struct.pack_into("<i", W.regions[2]["data"], 0x808, 3)          # ค่า status = 3
    db = os.path.join(tempfile.mkdtemp(), "p.sqlite")
    con = sqlite3.connect(db)
    con.execute("create table modules(moduleid int, ptrid int, name text)")
    con.execute("create table results(ptrid int, moduleid int, moduleoffset int, " + ",".join(f"offset{i} int" for i in range(1, 10)) + ")")
    con.execute("insert into modules values (0, 0, 'game.exe')")
    rows = [(0, 0, 0x100, 8, 16)] * 6 + [(0, 0, 0x100, 8, 32)] + [(0, 99, 0x100, 8, 16)]   # ดี x6, ชี้ผิด x1, module NULL (-> main) x1
    for r_ in rows:
        con.execute("insert into results values (?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL)", r_)
    con.commit(); con.close()

    ps = mem.pointer_scanner(dtype=4).load_pointers_from_db(db, limit=50)
    assert len(ps.pointers) == 8
    best = ps.get_best_pointer(filter_cond=lambda v: v in range(6))
    assert best.addr() == HEAP + 0x808 and best.read() == 3 and best.dtype == 4
    assert ps.value_frequencies[HEAP + 0x808] == 7, ps.value_frequencies      # 6 + 1 (module NULL -> main)
    assert ps.get_best_pointer(filter_cond=lambda v: v > 100) is None and ps.value_frequencies == {}
    try: ps.get_best_pointer(filter_cond="x > 1"); raise SystemExit("should fail")
    except TypeError: pass
    ps2 = mem.pointer_scanner(dtype=4).load_pointers_from_db("/nonexistent/x.sqlite"); assert ps2.pointers == [] and ps2.get_best_pointer() is None
    ps3 = mem.pointer_scanner(dtype=4).load_pointers_from_db(db, limit=3); assert len(ps3.pointers) == 3
    ok("PointerScanner (dtype kept, NULL module, frequencies, callable-only)")

    # context manager / close
    with Memory("game.exe") as m2: h = m2.handle; assert h
    assert m2.handle is None
    mem.close(); mem.close(); mem_pid.close()
    ok("context manager")

# 32-bit Python + 64-bit target
pk, wa, W, IMG, HEAP = load(8)
real = ctypes.sizeof
import fakepkg.memory as fm
class FakeCtypes:
    def __getattr__(self, n): return getattr(ctypes, n)
    @staticmethod
    def sizeof(t): return 4 if t is ctypes.c_void_p else ctypes.sizeof(t)
fm.ctypes = FakeCtypes()
try: fm.Memory("game.exe"); raise SystemExit("should fail")
except OSError as e: assert "32-bit" in str(e)
print("ok   32-bit python vs 64-bit target rejected")
print("ALL PASSED")
