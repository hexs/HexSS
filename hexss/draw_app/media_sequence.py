from pathlib import Path
from pprint import pprint
import cv2
from hexss import json_update, json_load


class MediaSequence:
    def __init__(self, path):
        self.path = Path(path)
        self.is_folder = self.path.is_dir()
        self.json_path = self.path.with_suffix(".json")
        self.rectangles = json_load(self.json_path, {})
        self.current_frame_number = 0
        self.current_frame_name = '0'
        self.total_frames = 0

        if self.is_folder:
            self.image_files = sorted([
                f for f in self.path.iterdir()
                if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
            ])
            if not self.image_files:
                raise ValueError(f"No images found in folder: {self.path}")
            self.total_frames = len(self.image_files)
        else:
            self.cap = cv2.VideoCapture(str(self.path))
            if not self.cap.isOpened():
                raise ValueError(f"Failed to open video file: {self.path}")
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    def get_frame_name(self):
        if self.is_folder:
            return self.image_files[self.current_frame_number].name
        return str(self.current_frame_number)

    def get_img(self):
        if self.is_folder:
            if 0 <= self.current_frame_number < self.total_frames:
                img_path = self.image_files[self.current_frame_number]
                img = cv2.imread(str(img_path))
                if img is None:
                    raise ValueError(f"Failed to load image: {img_path}")
                return img
        else:
            if 0 <= self.current_frame_number < self.total_frames:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_number)
                ret, img = self.cap.read()
                if not ret or img is None:
                    raise ValueError(f"Failed to read frame #{self.current_frame_number} from video: {self.path}")
                return img
        return None

    def update_rectangles(self, new_data):
        try:
            self.rectangles = json_update(self.json_path, new_data)
        except Exception as e:
            raise RuntimeError(f"Failed to update rectangles: {str(e)}")
