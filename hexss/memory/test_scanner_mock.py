"""ทดสอบตรรกะของ scanner.py ด้วย memory จำลอง (ไม่ต้องใช้ Windows)"""
import importlib.util, random, struct
import numpy as np

import pathlib
PATH = pathlib.Path(__file__).resolve().parent.parent / "hexss_memory" / "scanner.py"
spec = importlib.util.spec_from_file_location("scanner", PATH)
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)

class FakeAddr:
    def __init__(self, a, dtype, signed): self.a, self.dtype, self.signed = a, dtype, signed

class FakeMem:
    def __init__(self, regions):  # regions: {base: bytearray}
        self.r = regions
    def regions(self, **kw):
        for b, d in sorted(self.r.items()): yield b, len(d)
    def read_bytes_partial(self, addr, size):
        for b, d in self.r.items():
            if b <= addr < b + len(d):
                return bytes(d[addr - b: addr - b + size])
        return b''
    def address(self, a, dtype=None, signed=True): return FakeAddr(a, dtype, signed)
    def poke(self, addr, fmt, v):
        for b, d in self.r.items():
            if b <= addr < b + len(d):
                struct.pack_into(fmt, d, addr - b, v); return

random.seed(1)
def mk(n_regions=3, size=100_000):
    regs = {}
    for k in range(n_regions):
        regs[0x10000000 + k * 0x1000000] = bytearray(random.randbytes(size))
    return FakeMem(regs)

def brute(mem, fmt, isz, pred, align):
    out = []
    for b, d in sorted(mem.r.items()):
        for off in range(0, len(d) - isz + 1, align):
            v = struct.unpack_from(fmt, d, off)[0]
            if pred(v): out.append((b + off, v))
    return out

# 1) tiny CHUNK/MAX_READ เพื่อทดสอบรอยต่อ chunk และการแบ่งก้อนตอน next
sc.CHUNK = 4096 + 8; sc.MAX_READ = 1000; sc.GAP = 16
mem = mk()
# ฝังค่าที่รู้ตำแหน่ง รวมถึงตรงรอยต่อ chunk
planted = [0x10000000 + 4096 + 8 - 4, 0x10000000 + 4096 + 8, 0x10000000 + 50000, 0x11000000 + 12]
for a in planted: mem.poke(a, '<i', 123456789)

s = sc.Scanner(mem, dtype=4)
s.first(123456789)
got = set(s.addresses.tolist())
exp = {a for a, v in brute(mem, '<i', 4, lambda v: v == 123456789, 4)}
assert got == exp and set(planted) <= got, (got, exp)
print("first exact int32 ok", len(got))

# next: changed / increased / decreased / exact / by (ตรวจละเอียด)
mem = mk()
A = planted[:3]; B = planted[3]
for a in planted: mem.poke(a, '<i', 123456789)
s = sc.Scanner(mem, dtype=4); s.first(123456789)
base_set = set(s.addresses.tolist()); assert set(planted) <= base_set
for a in A: mem.poke(a, '<i', 123456794)      # +5
mem.poke(B, '<i', 123456780)                   # -9
import copy
def fresh():
    x = sc.Scanner(mem, dtype=4); x._addrs = s._addrs.copy(); x._values = s._values.copy(); x._started = True; return x
x = fresh(); x.next('changed');   assert set(x.addresses.tolist()) == set(planted), x.addresses
x = fresh(); x.next('unchanged'); assert set(x.addresses.tolist()) == base_set - set(planted)
x = fresh(); x.next('increased'); assert set(x.addresses.tolist()) == set(A)
x = fresh(); x.next('decreased'); assert set(x.addresses.tolist()) == {B}
x = fresh(); x.next('increased_by', 5); assert set(x.addresses.tolist()) == set(A)
x = fresh(); x.next('decreased_by', 9); assert set(x.addresses.tolist()) == {B}
x = fresh(); x.next(123456794); assert set(x.addresses.tolist()) == set(A)
x.next(123456794); assert set(x.addresses.tolist()) == set(A)   # chain
assert all(v == 123456794 for v in x.values.tolist())
print("next types ok")

# 2) random cross-check vs brute force: หลาย dtype / alignment / kind
cases = [
  (4, True, 4, 'exact', (7,), lambda v: v == 7, '<i'),
  (1, False, 1, 'less', (3,), lambda v: v < 3, '<B'),
  (2, True, 2, 'between', (-100, 100), lambda v: -100 <= v <= 100, '<h'),
  (4, True, 1, 'greater', (2_000_000_000,), lambda v: v > 2_000_000_000, '<i'),   # unaligned
  (8, False, 4, 'greater', (2**63,), lambda v: v > 2**63, '<Q'),                 # align 4 < size 8
  (4, True, 8, 'less', (-2_000_000_000,), lambda v: v < -2_000_000_000, '<i'),   # align > size
  (4, True, 4, 'greater', (10**12,), lambda v: False, '<i'),                    # out of range
  (4, True, 4, 'exact', (3.5,), lambda v: False, '<i'),                         # non-integer on int
]
for dtype, signed, align, kind, args, pred, fmt in cases:
    mem = mk(2, 30_000)
    s = sc.Scanner(mem, dtype=dtype, signed=signed, alignment=align)
    s.first(kind, *args)
    isz = {1:1,2:2,4:4,8:8}[dtype]
    exp = brute(mem, fmt, isz, pred, align)
    assert s.addresses.tolist() == [a for a, _ in exp], (dtype, align, kind, len(s.addresses), len(exp))
    assert s.values.tolist() == [v for _, v in exp]
    # next('unchanged') ต้องไม่เปลี่ยนผล
    n = s.count; s.next('unchanged'); assert s.count == n
    print("brute ok", dtype, align, kind, n)

# 3) float
mem = mk(1, 20_000)
vals = [1.5, 2.25, 100.37, -7.0]
base = 0x10000000
for i, v in enumerate(vals): mem.poke(base + 4 * (100 + i), '<f', v)
s = sc.Scanner(mem, dtype='float'); s.first(1.5); assert base + 400 in s.addresses
s = sc.Scanner(mem, dtype='float', tolerance=0.01); s.first(100.37)
assert base + 4*102 in s.addresses
s.next('between', 100, 101); assert base + 4*102 in s.addresses
mem.poke(base + 4*102, '<f', 105.37)
s.next('increased_by', 5); assert s.addresses.tolist() == [base + 4*102], s.addresses
print("float ok")

# 4) double + next(exact) + live items + cancel + progress + parse errors
mem = mk(1, 20_000); mem.poke(base + 800, '<d', 3.14159)
s = sc.Scanner(mem, dtype='double'); s.first(3.14159); assert base + 800 in s.addresses
assert s.items(5, live=True)[0][1] == 3.14159
calls = []
s = sc.Scanner(mem, dtype=4, progress=lambda d, t, f: calls.append((d, t, f))); s.first('less', 0); assert calls and calls[-1][0] == calls[-1][1]
s.stop()  # stop ก่อน first -> first เคลียร์ event เอง
for bad in [(), ('changed',), ('between', 1), ('bogus', 1)]:
    try: sc.Scanner(mem).first(*bad); raise SystemExit(f"should fail {bad}")
    except (TypeError, ValueError): pass
try: sc.Scanner(mem).next(1); raise SystemExit("should fail")
except RuntimeError: pass
s = sc.Scanner(mem, dtype=4); s.first('greater', -1)  # เยอะ
n = s.count
orig = mem.read_bytes_partial
calls_n = [0]
def hooked(a, sz):
    calls_n[0] += 1
    if calls_n[0] == 3: s.stop()
    return orig(a, sz)
mem.read_bytes_partial = hooked
s.next('unchanged'); assert s.cancelled and s.count == n
mem.read_bytes_partial = orig
calls_n[0] = -10**9
# cancel ระหว่าง first -> ผลว่าง
mem.read_bytes_partial = lambda a, sz: (s2.stop(), orig(a, sz))[1]
s2 = sc.Scanner(mem, dtype=4); s2._stop.clear()
mem.read_bytes_partial = lambda a, sz: (s2._stop.set(), orig(a, sz))[1]
s2.first('greater', 0); assert s2.cancelled and s2.count == 0
mem.read_bytes_partial = orig
s = sc.Scanner(mem, dtype=4, max_results=100); s.first('greater', -2**31 - 1); assert s.truncated
print("misc ok")
print("ALL PASSED")
