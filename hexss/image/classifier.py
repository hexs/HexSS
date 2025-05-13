from typing import Union, Optional, Dict
import hexss
from hexss.image import Image
from PIL import Image as PILImage
import numpy as np
import cv2


class Classification:
    def __init__(self, predictions: np.ndarray, class_index: int, class_name: str, confidence: float):
        """
        Args:
            predictions (np.ndarray): Array of prediction scores for each class.
            class_index (int): Index of the predicted class.
            class_name (str): Name of the predicted class.
            confidence (float): Confidence score of the predicted class.
        """
        self.predictions = predictions
        self.class_index = class_index
        self.class_name = class_name
        self.confidence = confidence


class Classifier:

    def __init__(self, model_path: str, json_data: Dict = None):
        """
        Args:
            model_path (str): Path to the pre-trained model.
            json_data (Dict): Configuration dictionary containing:
                              - 'img_size': Tuple[int, int], e.g., (180, 180)
                              - 'class_names': List[str], e.g., ['ok', 'ng']
        """
        try:
            from keras import models
        except ImportError:
            hexss.check_packages('tensorflow', auto_install=True)
            from keras import models

        # Load the pre-trained model
        self.model = models.load_model(model_path)

        if json_data is None:
            json_path = model_path.replace('.h5', '.json')
            json_data = hexss.json_load(json_path)

        # Fixed bugs to be compatible with older model.
        if 'class_names' not in json_data and json_data.get('model_class_names'):
            json_data['class_names'] = json_data['model_class_names']

        # Validate required keys in the configuration dictionary
        if 'img_size' not in json_data or 'class_names' not in json_data:
            raise ValueError("json_data must contain 'img_size' and 'class_names' keys.")

        self.json_data = json_data
        # json_data = {
        #     'img_size': (180, 180),
        #     'class_names': ['ok', 'ng']
        # }
        self.classification: Optional[Classification] = None

    def classify(self, image: Union[Image, PILImage.Image, np.ndarray]) -> Classification:
        """
        Classify an image using the pre-trained model.

        Args:
            image (Union[Image, PILImage.Image, np.ndarray]): The input image to classify. Can be:
                                                              - hexss.Image |RGB
                                                              - PIL Image   |RGB
                                                              - NumPy array |BGR

        Returns:
            Classification: The classification result.

        Raises:
            TypeError: If the input image type is not supported.
        """
        # Convert hexss.Image to a NumPy array
        if isinstance(image, Image):
            image_arr = image.numpy('RGB')
        elif isinstance(image, PILImage.Image):
            image_arr = np.array(image).copy()
        elif isinstance(image, np.ndarray):
            image_arr = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            raise TypeError(
                f"Unsupported image type: {type(image)}. Supported types: hexss.Image, PIL.Image, np.ndarray.")

        img_size = self.json_data['img_size']
        arr = cv2.resize(image_arr, img_size)  # Resize image
        arr = np.expand_dims(arr, axis=0) / 255.0  # Normalize and add batch dimension

        predictions = self.model.predict_on_batch(arr)[0]  # [     2.6491     -3.4541]
        class_index = np.argmax(predictions)  # 0
        class_name = self.json_data['class_names'][class_index]  # happy
        confidence = predictions[class_index]  # 2.649055

        self.classification = Classification(
            predictions=predictions,
            class_index=int(class_index),
            class_name=class_name,
            confidence=float(confidence)
        )
        return self.classification
