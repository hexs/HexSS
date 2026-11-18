import time
from hexss.memory import Memory
from hexss.windows import relaunch_as_admin
relaunch_as_admin()

mem = Memory('taskmgr.exe')
# processes_addr = mem.address(0x7FF7713D0CA0)
# processes_addr = mem.from_xml('''
# <?xml version="1.0" encoding="utf-8"?>
# <CheatTable>
#   <CheatEntries>
#     <CheatEntry>
#       <ID>2</ID>
#       <Description>"No description"</Description>
#       <LastState Value="265" RealAddress="7FF7713D0CA0"/>
#       <ShowAsSigned>1</ShowAsSigned>
#       <VariableType>4 Bytes</VariableType>
#       <Address>taskmgr.exe+550CA0</Address>
#     </CheatEntry>
#   </CheatEntries>
# </CheatTable>
# ''')
processes_addr = mem.pointer('taskmgr.exe', 0x550CA0, [], dtype=4)
threads_addr = processes_addr + 4
handlers_addr = processes_addr + 8
speed_addr = mem.pointer('taskmgr.exe', 0x4323B8, [])

while True:
    processes = processes_addr.read(dtype=4, signed=False)  # 4 bytes unsigned
    threads = threads_addr.read(dtype=4)  # 4 bytes signed (default)
    handlers = handlers_addr.read(dtype=4)
    speed = speed_addr.read(dtype='utf-16', count=14)
    print(f'processes:{processes} | threads:{threads} | handlers:{handlers} | speed:{speed}')

    all_val = processes_addr.read(dtype=4, count=3)  # [processes, threads, handlers]
    print(f'all_val:{all_val}')

    time.sleep(0.1)
