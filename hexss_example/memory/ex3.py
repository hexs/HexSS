import time
from hexss import keyboard

from hexss.memory import Memory
from hexss.threading import Multithread
from hexss.constants import *
from hexss.windows import is_admin, relaunch_as_admin

'''
fishing_status
0 ยืนก่อนตก       1718862356 1326225478
1 ปาเบ็ด       
1 รอปลา          1440015781 3120743969
2 ปลาติดเบ็ด       2587756550 4185891800
5 กำลังเก็บปลา       
4 เบ็ดขาด
3 เก็บ 

tension
1.0 ดึงเบ็ดแล้วค่าลดลง
0.0 เบ็ดขาด
(Float 1) = 00 00 B0 3F = 1065353216
'''


def release_f():
    keyboard.release('f')
    print(f'{GREEN}release_f{END}')


def press_f():
    keyboard.press('f')
    print(f'{GREEN}press_f{END}')


def press_release_f():
    print(f'{GREEN}press_release_f{END}')
    keyboard.press('f')
    time.sleep(0.1)
    keyboard.release('f')
    time.sleep(0.1)


def main(data):
    from hexss.image.capture import WindowCapture

    cap = WindowCapture(title='Heartopia')
    cap.activate()
    data['started'].append('main')

    mem = Memory("xdt.exe")

    # 1. โหลดข้อมูลจาก Database
    print("กำลังสแกนหา Address ของ Fishing Status...")
    status_scanner = mem.pointer_scanner(dtype=4).load_pointers_from_db(
        db_path=r'C:\Users\Ek\Documents\fish\aa.sqlite',
        limit=500
    )

    print("กำลังสแกนหา Address ของ Tension...")
    tension_scanner = mem.pointer_scanner(dtype='float').load_pointers_from_db(
        db_path=r'C:\Users\Ek\Documents\fish\tt.sqlite',
        limit=500
    )

    status_addr = status_scanner.get_best_pointer(filter_cond=lambda x: x in [0, 1, 2, 3, 4, 5])
    tension_addr = tension_scanner.get_best_pointer(filter_cond=lambda x: 0.0001 <= x <= 1)
    is_pull_ptr = status_addr + 4

    if status_addr is None or tension_addr is None:
        print("ไม่พบ Address ที่ถูกต้อง กรุณาตรวจสอบ Database")
        return

    print(f"ล็อก Address สำเร็จ! Status: {status_addr}, Tension: {tension_addr}")

    while data.get("running"):
        time.sleep(0.1)

        fishing_status = status_addr.read()
        is_pull_the_hook = is_pull_ptr.read()
        tension = tension_addr.read(dtype='float')

        data['status'] = fishing_status

        print(end=f"\rstatus:{fishing_status}, is_pull:{is_pull_the_hook}, tension:{tension} ")

        if fishing_status == 2:  # ปลาติดเบ็ด
            if tension >= 0.3 and not is_pull_the_hook:
                press_f()  # ดึง
            if tension <= 0.2 and is_pull_the_hook:
                release_f()  # ปล่อย

        if data['enable'] == 'enable':
            if fishing_status == 0:
                press_release_f()  # โยนเบ็ด

        if fishing_status in [4, 5]:
            if is_pull_the_hook:
                release_f()


def enable(data):
    def on_key_event(event):
        if event.name == 'F3':
            data['enable'] = 'enable'
            print(f'{YELLOW}enable{END}')
        if event.name == 'F4':
            data['enable'] = 'disable'
            print(f'{YELLOW}disable{END}')

            if data['status'] == 1:  # รอปลา
                press_release_f()  # เก็บเบ็ด

    data['started'].append('key_event')

    listener = keyboard.Listener(on_press=on_key_event)
    listener.start()
    listener.join()


if __name__ == '__main__':
    print("is_admin (before):", is_admin())
    relaunch_as_admin()
    print("is_admin (after):", is_admin())

    data = {
        'running': True,
        'started': [],

        'enable': 'disable',
        'status': 0

    }

    m = Multithread()

    m.add_func(enable, args=(data,))
    m.add_func(main, args=(data,))

    m.start()
    while data.get("running"):
        print(data['started'])
        print(m.get_status())
        if len(data['started']) == 2:
            break
        time.sleep(1)
    m.join()
