import os
import shutil
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Union, Optional, Any, Dict, List, Tuple, Self
import concurrent.futures

import hexss
from hexss import json_load, json_dump, json_update
from hexss import Config
from hexss.constants import *
from hexss.path import shorten
from hexss.image import Image, ImageFont, PILImage
import numpy as np
import cv2
import matplotlib.pyplot as plt

try:
    import tensorflow as tf
    import keras
    from keras.models import load_model
except ImportError:
    hexss.check_packages('tensorflow', 'keras', auto_install=True)
    import tensorflow as tf
    import keras
    from keras.models import load_model  # type: ignore


class Classification:
    """
    Holds prediction results for one classification.
    Attributes:
        predictions: Raw model output logits or probabilities.
        class_names: List of class labels.
        idx: Index of top prediction.
        name: Top predicted class name.
        conf: Confidence score of top prediction.
        group: Optional group name if mapping provided.
    """
    __slots__ = ('predictions', 'class_names', 'idx', 'name', 'conf', 'group', 'xywhn')

    def __init__(
            self,
            predictions: np.ndarray,
            class_names: List[str],
            mapping: Optional[Dict[str, List[str]]] = None,
            group: Optional[str] = None,
            xywhn: Optional[Tuple[float, float, float, float] | List[float]] = None
    ) -> None:
        self.predictions = predictions.astype(np.float64)
        self.class_names = class_names
        self.idx = int(self.predictions.argmax())
        self.name = class_names[self.idx]
        self.conf = float(self.predictions[self.idx])
        self.group = group
        self.xywhn = xywhn
        if mapping:
            for group_name, labels in mapping.items():
                if self.name in labels:
                    self.group = group_name
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

    def __repr__(self) -> str:
        return (
            f"<idx={self.idx} name={self.name!r} group={self.group!r}>"
        )


class Classifier:
    """
    Wraps a Keras model for image classification.
    """
    __slots__ = ('model_path', 'cfg', 'model', 'json_cfg', 'class_names')

    def __init__(self, model_path: Union[Path, str]) -> None:
        self.model_path = Path(model_path)
        self.cfg = Config(self.model_path.with_suffix('.pycfg'), default='''
from keras import Sequential, layers
from pathlib import Path

img_size = [100, 100]
epochs = 10
batch_size = 64
validation_split = 0.2
seed = 123
datasets_path = Path(__file__).parent / f'{Path(__file__).stem}_datasets'
class_names = [p.name for p in datasets_path.iterdir() if p.is_dir()]
# mapping = {'OK': [white, yello], 'NG': [black]}

model = Sequential([
    layers.Rescaling(1. / 255, input_shape=(*img_size, 3)),
    layers.Conv2D(16, 3, padding='same', activation='relu'),
    layers.MaxPooling2D(),
    layers.Conv2D(32, 3, padding='same', activation='relu'),
    layers.MaxPooling2D(),
    layers.Conv2D(64, 3, padding='same', activation='relu'),
    layers.MaxPooling2D(),
    layers.Flatten(),
    layers.Dense(128, activation='relu'),
    layers.Dense(len(class_names))
])
        ''')
        self.model: Optional[keras.Model] = None
        self.json_cfg = None
        self.class_names = []
        self.load_model()

    def load_model(self):
        if self.model_path.exists():
            self.model = keras.models.load_model(self.model_path)
            self.json_cfg = json_load(self.model_path.with_suffix('.json'))
            self.class_names = self.json_cfg['class_names']
        else:
            print(f"Warning: Model file {self.model_path} not found. Train with .train()")

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
            if im.ndim == 2 or (im.ndim == 3 and im.shape[2] == 1):
                arr = cv2.cvtColor(im, cv2.COLOR_GRAY2RGB)
            else:
                arr = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        else:
            raise TypeError(f"Unsupported image type: {type(im)}")

        arr = cv2.resize(arr, self.cfg.img_size)
        if arr.shape[2] == 4:
            arr = arr[..., :3]

        return np.expand_dims(arr, axis=0)

    def classify(
            self,
            im: Union[Image, PILImage.Image, np.ndarray],
            mapping: Optional[Dict[str, List[str]]] = None,
            xywhn=None
    ) -> Classification:
        """
        Run a forward pass and return a Classification.
        """
        if self.model is None:
            raise ValueError("Model is not loaded. Call train() or load an existing model.")
        batch = self._prepare_image(im)
        preds = self.model.predict(batch, verbose=0)[0]
        return Classification(
            predictions=preds,
            class_names=self.class_names,
            mapping=mapping,
            xywhn=xywhn
        )

    def predict(self, *args, **kwargs):
        return self.classify(*args, **kwargs)

    def train(self, ignore_exists=False) -> None:
        if ignore_exists and self.model is not None:
            return
        try:
            train_ds, val_ds = keras.utils.image_dataset_from_directory(
                self.cfg.datasets_path,
                validation_split=self.cfg.validation_split,
                subset='both',
                seed=self.cfg.seed,
                image_size=self.cfg.img_size,
                batch_size=self.cfg.batch_size
            )
        except Exception as e:
            print(e)
            return

        self.class_names = train_ds.class_names
        start_time = datetime.now()

        self.json_cfg = json_dump(self.model_path.with_suffix('.json'), {
            'class_names': self.class_names,
            'img_size': list(self.cfg.img_size),
            'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Build model
        AUTOTUNE = tf.data.AUTOTUNE
        train_ds = train_ds.cache().shuffle(1000).prefetch(AUTOTUNE)
        val_ds = val_ds.cache().prefetch(AUTOTUNE)
        self.model = self.cfg.model
        self.model.compile(
            optimizer='adam',
            loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
            metrics=['accuracy']
        )
        self.model.summary()

        # Save model after each epoch
        checkpoint_callback = keras.callbacks.ModelCheckpoint(
            # <model folder>/x1_model/temp model epoch001.keras
            filepath=self.model_path.parent / f'{self.model_path.stem}_model' / f'temp model epoch{{epoch:03d}}.keras',
            save_freq='epoch',
            save_weights_only=False,
            verbose=0
        )

        # Train
        history = self.model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=self.cfg.epochs,
            callbacks=[checkpoint_callback]
        )

        # Save final model
        self.model.save(self.model_path)
        print(f"{GREEN}Model saved to {GREEN.UNDERLINED}{self.model_path}{END}")
        end_time = datetime.now()
        self.json_cfg.update({
            'end_time': end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'time_spent_training': (end_time - start_time).total_seconds(),
            'history': history.history
        })
        json_update(self.model_path.with_suffix('.json'), self.json_cfg)

        # Plot training history
        acc = history.history.get('accuracy', [])
        val_acc = history.history.get('val_accuracy', [])
        loss = history.history.get('loss', [])
        val_loss = history.history.get('val_loss', [])
        epochs_range = range(len(acc))

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
        plt.savefig(self.model_path.parent / f'{self.model_path.stem}_model' / 'Training and Validation Loss.png')
        plt.close()

    def test(
            self,
            data_dir: Union[Path, str, None] = None,
            threshold: float = 0.7,
            multiprocessing: bool = False,
    ) -> Dict[str, int]:
        """
        Test model on images in each class subfolder and print results.
        """
        data_dir = Path(data_dir or self.cfg.datasets_path)
        total = 0
        results = []

        def _test_one(class_name: str, img_path: Path, i: int, total: int) -> str:
            im = Image.open(img_path)
            clf = self.classify(im)
            prob = clf.expo_preds(1.2)[clf.idx]
            is_match = (clf.name == class_name)
            is_confident = is_match and prob >= threshold
            short = shorten(img_path, 2, 3)
            if is_confident:
                print(end=f'\r{class_name}({i}/{total}) {GREEN}{clf.name},{prob:.2f}{END} {short}')
                return 'correct'
            elif is_match:
                print(end=f'\r{class_name}({i}/{total}) {YELLOW}{clf.name},{prob:.2f}{END} {short}\n')
                return 'uncertain'
            else:
                print(end=f'\r{class_name}({i}/{total}) {RED}{clf.name},{prob:.2f}{END} {short}\n')
                return 'wrong'

        for class_name in self.class_names:
            folder = data_dir / class_name
            if not folder.exists():
                continue
            images = [f for f in folder.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}]
            total = len(images)
            if total == 0:
                continue

            if multiprocessing:
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    futures = [
                        ex.submit(_test_one, class_name, img_path, i + 1, total)
                        for i, img_path in enumerate(images)
                    ]
                    results = [f.result() for f in futures]
            else:
                for i, img_path in enumerate(images):
                    results.append(_test_one(class_name, img_path, i + 1, len(images)))
        print("\r")

        correct = results.count('correct')
        uncertain = results.count('uncertain')
        wrong = results.count('wrong')
        return {'correct': correct, 'uncertain': uncertain, 'wrong': wrong, 'total': total}

    def __repr__(self) -> str:
        return (
            f"<Classifier path={self.model_path} loaded={'yes' if self.model else 'no'}"
            f" classes={self.class_names}>"
        )


if __name__ == '__main__':
    c = Classifier('classification_model_example/x1.keras')
    c.cfg.img_size = [80, 80]
    c.cfg.epochs = 1000
    c.train(ignore_exists=False)
    results = c.test(multiprocessing=True)
    print(results)
