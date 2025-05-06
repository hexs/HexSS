from typing import Union
import hexss
from hexss.image import Image

hexss.check_packages(
    'tensorflow', 'numpy', 'opencv-python',
    auto_install=True
)

import numpy as np
import cv2


class Classifier:
    def __init__(self, model_path: str, data: dict):

        from keras import models

        self.model = models.load_model(model_path)
        self.data = data
        # {
        #     'img_size': (180, 180),
        #     'class_names': ['ok', 'ng']
        # }
        self.predictions = None  # [     2.6491     -3.4541]
        self.class_index = None  # 0
        self.class_name = None  # happy
        self.confidence = None  # 2.649055

    def classify(self, image: Union[Image, np.ndarray]) -> tuple[str, float]:
        if isinstance(image, Image):
            arr = image.numpy()
        elif isinstance(image, np.ndarray):
            arr = image
        else:
            raise TypeError(
                f"Unsupported image type: {type(image)}. "
                "Provide an Im or NumPy array."
            )
        arr = cv2.resize(arr, self.data['img_size'])
        arr = np.expand_dims(arr, axis=0) / 255.0
        self.predictions = self.model.predict_on_batch(arr)[0]
        self.class_index = np.argmax(self.predictions)
        self.class_name = self.data['class_names'][self.class_index]
        self.confidence = self.predictions[self.class_index]
        return self.class_name, self.confidence
