import time
from hexss.memory import Memory

mem = Memory('taskmgr.exe')
processes_addr = mem.pointer(0x550CA0, [], dtype=4)
threads_addr = processes_addr + 4
handlers_addr = processes_addr + 8
speed_addr = mem.pointer(0x4323B8,[], dtype='utf-16')

# แบบอื่นที่ใช้ได้เหมือนกัน
#   mem.pointer('taskmgr.exe+550CA0', dtype=4)      # string แบบ Cheat Engine
#   mem.pointer(0x1234, [0x10, 0x8], module='other.dll')   # module อื่น

while True:
    processes = processes_addr.read()
    threads = threads_addr.read()
    handlers = handlers_addr.read()
    speed = speed_addr.read(14)
    print(f'processes:{processes} | threads:{threads} | handlers:{handlers} | speed:{speed}')

    all_val = processes_addr.read(3)  # [processes, threads, handlers]
    print(f'all_val:{all_val}')

    time.sleep(0.1)
