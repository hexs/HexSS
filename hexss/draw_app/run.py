import time
from pprint import pprint
import cv2
import base64
import os
from hexss import json_update, json_load
from hexss.threading import Multithread
from app import run_server


class Video:
    def __init__(self, path):
        self.path = path
        self.is_folder = os.path.isdir(path)
        self.json_path = os.path.join('data', os.path.splitext(os.path.basename(path))[0] + '.json')
        self.rectangles = json_load(self.json_path, {})
        self.current_frame_number = 0
        self.current_frame_name = '0'
        self.total_frames = 0

        if self.is_folder:
            self.image_files = sorted([f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg'))])
            if not self.image_files:
                raise ValueError(f"No images found in folder: {path}")
            self.total_frames = len(self.image_files)
        else:  # video.mp4
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                raise ValueError(f"Failed to open video file: {path}")
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

        print('current_frame_number', self.current_frame_number)
        print('is_folder', self.is_folder)

    def get_frame_name(self):
        if self.is_folder:
            return self.image_files[self.current_frame_number]
        else:
            return f"{self.current_frame_number}"

    def get_img(self):
        if self.is_folder:
            # Handle folder (image sequence)
            if 0 <= self.current_frame_number < self.total_frames:
                img_path = os.path.join(self.path, self.image_files[self.current_frame_number])
                img = cv2.imread(img_path)
                if img is not None:
                    return img
            return None
        else:
            # Handle video file
            if 0 <= self.current_frame_number < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_number)
                ret, img = self.cap.read()
                if ret:
                    return img
            return None

    def update_rectangles(self, new_data):
        try:
            print(self.json_path)
            pprint(new_data)
            self.rectangles = json_update(self.json_path, new_data)
        except Exception as e:
            print(f"Failed to update rectangles: {str(e)}")
            raise


def generate_image(data):
    while True:
        video = data.get('video', None)
        if video is None:
            print('video is None')
            time.sleep(0.5)
            continue

        img = video.get_img()
        if img is None:
            print('No frame to display.')
            time.sleep(0.5)
            continue
        cv2.putText(img, f"Frame: {video.get_frame_name()}",
                    (10, 100), 0, 3, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.imshow('Video', cv2.resize(img, None, fx=0.5, fy=0.5))
        cv2.waitKey(1)
        _, buffer = cv2.imencode('.jpg', img)
        data['response'] = {
            "image": 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode('utf-8'),
            'current_frame_number': video.current_frame_number,
            'current_frame_name': video.current_frame_name,
            "total_frames": video.total_frames,
            "rectangles": video.rectangles.get(video.current_frame_name) or {}
        }
        time.sleep(0.01)


if __name__ == '__main__':
    data = {
        'play': True,
        'response': None,
        'video': None,
    }

    m = Multithread()
    m.add_func(target=generate_image, args=(data,))
    m.add_func(target=run_server, args=(data,), join=False)
    m.start()
    m.join()
