import os
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Union, Optional, Any, Dict, List, Tuple

import hexss
from hexss import json_load, json_dump, json_update
from hexss.constants import *
from hexss.image import Image, ImageFont, PILImage
import numpy as np
import cv2


class Classification:
    """
    Holds prediction results for one classification.
    Attributes:
        predictions: Raw model output logits or probabilities.
        class_names: List of class labels.
        idx: Index of top prediction.
        name: Top predicted class name.
        conf: Confidence score of top prediction.
        mapping_name: Optional group name if mapping provided.
    """

    __slots__ = ('predictions', 'class_names', 'idx', 'name', 'conf', 'mapping_name')

    def __init__(
            self,
            predictions: np.ndarray,
            class_names: List[str],
            mapping: Optional[Dict[str, List[str]]] = None
    ) -> None:
        self.predictions = predictions.astype(np.float64)
        self.class_names = class_names
        self.idx = int(self.predictions.argmax())
        self.name = class_names[self.idx]
        self.conf = float(self.predictions[self.idx])

        self.mapping_name: Optional[str] = None
        if mapping:
            for group, names in mapping.items():
                if self.name in names:
                    self.mapping_name = group
                    break

    def expo_preds(self, base: float = np.e) -> np.ndarray:
        """
        Exponentiate predictions by `base` and normalize to sum=1.
        """
        exp_vals = np.power(base, self.predictions)
        return exp_vals / exp_vals.sum()

    def softmax_preds(self) -> np.ndarray:
        """
        Compute standard softmax probabilities.
        """
        z = self.predictions - np.max(self.predictions)
        e = np.exp(z)
        return e / e.sum()


class Classifier:
    """
    Wraps a Keras model for image classification.
    """
    __slots__ = ('model_path', 'json_data', 'model', 'class_names', 'img_size')

    def __init__(
            self,
            model_path: Union[Path, str],
            json_data: Optional[Dict[str, Any]] = None
    ) -> None:
        self.model_path = Path(model_path)
        self.json_data = json_data
        if self.json_data is None:
            self.json_data = json_load(self.model_path.with_suffix('.json'), {
                'img_size': [180, 180]
            })
            ############################ for support old data ############################
            if 'model_class_names' in self.json_data and 'class_names' not in self.json_data:
                self.json_data['class_names'] = self.json_data.pop('model_class_names')
            ###############################################################################

        self.class_names: List[str] | List = self.json_data.get('class_names', [])
        self.img_size: Tuple[int, int] = tuple(self.json_data.get('img_size'))
        self.model = None

        if not self.model_path.exists():
            print(f"Model file not found: {self.model_path}")
            return

        try:
            from keras.models import load_model
        except ImportError:
            hexss.check_packages('tensorflow', auto_install=True)
            from keras.models import load_model  # type: ignore

        self.model = load_model(self.model_path)

    def _prepare_image(
            self,
            im: Union[Image, PILImage.Image, np.ndarray]
    ) -> np.ndarray:
        """
        Convert input to RGB array resized to `img_size` and batch of 1.
        """
        if isinstance(im, Image):
            arr = im.numpy('RGB')
        elif isinstance(im, PILImage.Image):
            arr = np.array(im.convert('RGB'))
        elif isinstance(im, np.ndarray):
            arr = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        else:
            raise TypeError(f"Unsupported image type: {type(im)}")

        arr = cv2.resize(arr, self.img_size)
        return np.expand_dims(arr, axis=0)

    def classify(
            self,
            im: Union[Image, PILImage.Image, np.ndarray],
            mapping: Optional[Dict[str, List[str]]] = None
    ) -> Classification:
        """
        Run a forward pass and return a Classification.
        """
        if self.model is None:
            raise ValueError("Model not loaded")

        batch = self._prepare_image(im)
        preds = self.model.predict(batch, verbose=0)[0]
        return Classification(
            predictions=preds,
            class_names=self.class_names,
            mapping=mapping
        )

    def train(
            self,
            data_dir: Union[Path, str],
            epochs: int = 50,
            img_size: Tuple[int, int] = (180, 180),
            batch_size: int = 64,
            validation_split: float = 0.2,
            seed: int = 123
    ) -> None:
        try:
            import tensorflow as tf
            from keras import layers, models
            import matplotlib.pyplot as plt
        except ImportError:
            hexss.check_packages('tensorflow', 'matplotlib', auto_install=True)
            import tensorflow as tf
            from keras import layers, models
            import matplotlib.pyplot as plt

        data_dir = Path(data_dir)
        self.img_size = img_size

        train_ds, val_ds = tf.keras.utils.image_dataset_from_directory(
            data_dir,
            validation_split=validation_split,
            subset='both',
            seed=seed,
            image_size=self.img_size,
            batch_size=batch_size
        )

        class_names = train_ds.class_names
        start_time = datetime.now()
        self.json_data = json_dump(self.model_path.with_suffix('.json'), {
            'class_names': class_names,
            'img_size': self.img_size,
            'batch_size': batch_size,
            'validation_split': validation_split,
            'seed': seed,
            'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Optimize performance
        AUTOTUNE = tf.data.AUTOTUNE
        train_ds = train_ds.cache().shuffle(1000).prefetch(AUTOTUNE)
        val_ds = val_ds.cache().prefetch(AUTOTUNE)

        # Build model
        num_classes = len(class_names)
        model = models.Sequential([
            layers.Input(shape=(*self.img_size, 3)),
            layers.RandomFlip('horizontal'),
            # layers.RandomRotation(0.1),
            # layers.RandomZoom(0.1),
            layers.Rescaling(1. / 255),
            layers.Conv2D(16, 3, padding='same', activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(32, 3, padding='same', activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(64, 3, padding='same', activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Conv2D(128, 3, padding='same', activation='relu'),
            layers.BatchNormalization(),
            layers.MaxPooling2D(),
            layers.Dropout(0.2),
            layers.Flatten(),
            layers.Dense(256, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(128, activation='relu'),
            layers.Dense(num_classes, name='output_logits')
        ])

        model.compile(
            optimizer='adam',
            loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
            metrics=['accuracy']
        )
        model.summary()

        # Train
        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
        )

        # Save the final model
        self.model = model
        model.save(self.model_path)
        print(f"{GREEN}Model saved to {GREEN.UNDERLINED}{self.model_path}{END}")
        end_time = datetime.now()
        self.json_data.update({
            'end_time': end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'time_spent_training': (end_time - start_time).total_seconds(),
            'history': history.history
        })
        json_update(self.model_path.with_suffix('.json'), self.json_data)

        acc = history.history['accuracy']
        val_acc = history.history['val_accuracy']
        loss = history.history['loss']
        val_loss = history.history['val_loss']

        # Adjust epochs_range based on the actual number of epochs run
        epochs = len(acc)
        epochs_range = range(epochs)

        plt.figure(figsize=(8, 8))
        plt.subplot(1, 2, 1)
        plt.plot(epochs_range, acc, label='Training Accuracy')
        plt.plot(epochs_range, val_acc, label='Validation Accuracy')
        plt.legend(loc='lower right')
        plt.title('Training and Validation Accuracy')

        plt.subplot(1, 2, 2)
        plt.plot(epochs_range, loss, label='Training Loss')
        plt.plot(epochs_range, val_loss, label='Validation Loss')
        plt.legend(loc='upper right')
        plt.title('Training and Validation Loss')

        plt.savefig(str(self.model_path.with_suffix(".png")))
        # plt.show()

    def test(self, data_dir: Union[Path, str]) -> None:
        """
        Test model on images in each class subfolder and print results.
        """
        data_dir = Path(data_dir)
        for class_name in self.class_names:
            folder = data_dir / class_name
            if not folder.exists():
                continue
            files = [f for f in folder.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}]
            total = len(files)
            for i, img_path in enumerate(files, start=1):
                im = Image.open(img_path)
                clf = self.classify(im)
                prob = clf.expo_preds(1.2)[clf.idx]
                if clf.name == class_name:
                    print(f'\r{class_name}({i}/{total}) {GREEN}{clf.name},{prob:.2f}{END} {img_path}', end='')
                else:
                    print(f'\r{class_name}({i}/{total}) {RED}{clf.name},{prob:.2f}{END} {img_path}')
        print()


class MultiClassifier:
    """
    Manages several classifiers and applies them to regions of an image.
    """

    def __init__(self, base_path: Union[Path, str]) -> None:
        base_path = Path(base_path)
        config = json_load(base_path / 'frames pos.json')
        self.frames = config['frames']
        self.classifications: Dict[str, Classification] = {}

        ############################ for support old data ############################
        for frame in self.frames.values():
            if "xywh" in frame:
                frame["xywhn"] = frame.pop("xywh")
            if "model_used" in frame:
                frame["model"] = frame.pop("model_used")
            if "res_show" in frame:
                frame["resultMapping"] = frame.pop("res_show")
        ###############################################################################

        self.models: Dict[str, Classifier] = {}
        for name in config['models']:
            model_file = base_path / 'model' / f"{name}.keras"
            if not model_file.exists():
                model_file = base_path / 'model' / f"{name}.h5"
            self.models[name] = Classifier(model_file)

    def classify_all(
            self,
            im: Union[Image, PILImage.Image, np.ndarray]
    ) -> Dict[str, Classification]:
        im = Image(im)
        self.classifications: Dict[str, Classification] = {}
        for key, frame in self.frames.items():
            model_name = frame['model']
            xywhn = frame['xywhn']
            mapping = frame['resultMapping']
            crop_im = im.crop(xywhn=xywhn)
            self.classifications[key] = self.models[model_name].classify(crop_im, mapping=mapping)
        return self.classifications


# ==== Usage Example ==== #
if __name__ == '__main__':
    # from hexss.github import download
    #
    # download('hexs', 'bottle-label-check', 'train_keras/classification_image', 'data', 100)

    # Directory structure:
    # data/
    #   class_a/
    #   class_b/
    #   ...
    data_dir = 'data'
    model_path = 'models/trained_model.keras'

    print('========== for create model ==========')
    classifier = Classifier(model_path)
    classifier.train(
        data_dir=data_dir,
        epochs=2,
        img_size=(180, 180),
        batch_size=32,
        validation_split=0.2
    )
    classifier.test(data_dir)

    print('========== for load model ==========')
    classifier = Classifier(model_path)
    classifier.test(data_dir)
    classifier.classify(Image(r'C:\PythonProjects\hexss\hexss\image\data\ng\1749564823.52831.png'))
