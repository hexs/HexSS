import cv2
import time

from hexss.thread_manager import ThreadManager
import hexss.server.file_manager_server


def capture(data, stop_event):
    cap = cv2.VideoCapture(0)
    while not stop_event.is_set():
        ret, frame = cap.read()
        if ret: data['img'] = frame
    cap.release()
    print("📸 Capture stopped.")


def show(data, stop_event):
    while not stop_event.is_set():
        if data['img'] is None: continue
        cv2.imshow('frame', data['img'])
        cv2.waitKey(1)
        if cv2.getWindowProperty('frame', cv2.WND_PROP_VISIBLE) < 1:
            stop_event.set()
    cv2.destroyAllWindows()
    print("🖥️ Show window closed.")


def file_manager_server():
    hexss.server.file_manager_server.run()

def count():
    i = 0
    while True:
        i+=1
        if i == 10:
            return 0
        time.sleep(1)


m = ThreadManager()
m.start_monitor_server(ip='0.0.0.0', port=2000)
data = {'img': None}

m.add_task(target=capture, args=(data,), task_id="capture")
m.add_task(target=show, args=(data,), task_id="show")
m.add_task(target=file_manager_server, join=False)
m.add_task(target=count)

m.start_all()
m.join_all()
