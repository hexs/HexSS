"""
ลอง scan หา address ของจำนวน Processes ใน Task Manager (เหมือน Cheat Engine)

วิธีใช้: เปิด Task Manager (แท็บ Performance) -> รันไฟล์นี้ด้วยสิทธิ์ Admin
  1) ใส่ค่า Processes ที่เห็น   -> first scan
  2) เปิด/ปิดโปรแกรมให้ค่าเปลี่ยน แล้วพิมพ์ next ตามด้วยค่าใหม่ เช่น
        next 270
        next changed
        next increased
        next between 200 300
        next increased_by 1
        show        (แสดงผล)     reset (เริ่มใหม่)     quit
"""
from hexss.memory import Memory

mem = Memory('taskmgr.exe')
answer_addr = mem.pointer(0x550CA0, []).addr()
if answer_addr:
    print(f'answer_addr:{hex(answer_addr)}')

def show_progress(done, total, found):
    print(f'\r  scanning {done / total:6.1%}   found {found:,}      ', end='', flush=True)


def parse(text):
    out = []
    for p in text.split():
        for cast in (int, float):
            try:
                out.append(cast(p))
                break
            except ValueError:
                continue
        else:
            out.append(p)
    return out


scan = mem.newscan(dtype=4, progress=show_progress)


def report():
    print(f'\n  results: {scan.count:,}   (answer_addr {"is" if answer_addr in scan.addresses else "is NOT"} in results)')
    if scan.count <= 20:
        scan.show()


scan.first(int(input('Processes ที่เห็นตอนนี้: ')))
report()

while True:
    cmd = input('> ').strip()
    if cmd in ('quit', 'q'):
        break
    if cmd == 'show':
        scan.show()
    elif cmd == 'reset':
        scan.reset().first(int(input('Processes ที่เห็นตอนนี้: ')))
        report()
    elif cmd.startswith('next'):
        try:
            scan.next(*parse(cmd[4:]))
            report()
        except (TypeError, ValueError, RuntimeError) as e:
            print('  error:', e)

mem.close()
