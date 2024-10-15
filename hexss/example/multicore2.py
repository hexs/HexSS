import cv2
from hexss.multiprocessing import Multicore


def capture_video(data):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        data['play'] = False
        return

    while data['play']:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame.")
            data['play'] = False
        data['frame'] = frame.copy()
    cap.release()


def process_video(data):
    while data['play']:
        if 'frame' in data and data['frame'] is not None:
            cv2.imshow('frame', data['frame'])
            if cv2.waitKey(1) & 0xFF == ord('q'):
                data['play'] = False
    cv2.destroyAllWindows()


# def capture_video(data):
#     cap = cv2.VideoCapture(0)
#     while data['play']:
#         ret, frame = cap.read()
#         data['frame'] = frame.copy()
#
#
# def process_video(data):
#     while data['play']:
#         if data['frame'] is not None:
#             cv2.imshow('frame', data['frame'])
#
#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 data['play'] = False
#
#     cv2.destroyAllWindows()

if __name__ == '__main__':
    m = Multicore()
    m.set_data({
        'play': True,
        'frame': None,
    })
    m.add_func(capture_video)
    m.add_func(process_video)
    m.start()
    m.join()
