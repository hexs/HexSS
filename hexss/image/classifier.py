import os
import shutil
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Union, Optional, Any, Dict, List, Tuple
import concurrent.futures

import hexss
from hexss import json_load, json_dump, json_update
from hexss.constants import *
from hexss.path import shorten
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
    __slots__ = ('model_path', 'json_path', 'json_data', 'model', 'class_names', 'img_size', 'layers')

    def __init__(
            self,
            model_path: Union[Path, str],
            json_data: Optional[Dict[str, Any]] = None
    ) -> None:
        '''
        :param model_path: `.keras` file path
        :param json_data: data of `.keras` file
                        example
                        {
                            "class_names": ["ng", "ok"],
                            "img_size": [32, 32],
                            ...
                        }
        '''
        self.model_path = Path(model_path)
        self.json_path = self.model_path.with_suffix('.json')
        self.json_data = json_data
        if self.json_data is None:
            self.json_data = json_load(self.json_path, {
                'img_size': [180, 180]
            })
            ############################ for support old data ############################
            if 'model_class_names' in self.json_data and 'class_names' not in self.json_data:
                self.json_data['class_names'] = self.json_data.pop('model_class_names')
            ###############################################################################

        self.class_names: List[str] = self.json_data.get('class_names', [])
        self.img_size: Tuple[int, int] = tuple(self.json_data.get('img_size'))
        self.model = None
        self.layers: Optional[Dict] = None

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
            if len(im.shape) == 2 or im.shape[2] == 1:
                arr = cv2.cvtColor(im, cv2.COLOR_GRAY2RGB)
            else:
                arr = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        else:
            raise TypeError(f"Unsupported image type: {type(im)}")

        arr = cv2.resize(arr, self.img_size)
        if arr.shape[2] == 4:
            arr = arr[..., :3]

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
            seed: int = 123,
            layers: Optional[Dict] = None
    ) -> None:
        try:
            import tensorflow as tf
            import keras
            import matplotlib.pyplot as plt
        except ImportError:
            hexss.check_packages('tensorflow', 'matplotlib', auto_install=True)
            import tensorflow as tf
            import keras
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
        self.json_data = json_dump(self.json_path, {
            'class_names': class_names,
            'img_size': self.img_size,
            'epochs': epochs,
            'batch_size': batch_size,
            'validation_split': validation_split,
            'seed': seed,
            'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # layers
        if layers:
            self.layers = layers
        if self.layers is None:
            self.layers = [
                keras.layers.RandomFlip("horizontal", input_shape=(*self.img_size, 3)),
                keras.layers.RandomRotation(0.1),
                keras.layers.RandomZoom(0.1),
                keras.layers.Rescaling(1. / 255),
                keras.layers.Conv2D(16, 3, padding='same', activation='relu'),
                keras.layers.MaxPooling2D(),
                keras.layers.Conv2D(32, 3, padding='same', activation='relu'),
                keras.layers.MaxPooling2D(),
                keras.layers.Conv2D(64, 3, padding='same', activation='relu'),
                keras.layers.MaxPooling2D(),
                keras.layers.Dropout(0.2),
                keras.layers.Flatten(),
                keras.layers.Dense(128, activation='relu'),
                keras.layers.Dense(len(class_names), name="outputs")
            ]

        # Optimize performance
        AUTOTUNE = tf.data.AUTOTUNE
        train_ds = train_ds.cache().shuffle(1000).prefetch(AUTOTUNE)
        val_ds = val_ds.cache().prefetch(AUTOTUNE)

        # Build the model
        self.model = keras.models.Sequential(self.layers)

        self.model.compile(
            optimizer='adam',
            loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
            metrics=['accuracy']
        )
        self.model.summary()

        # ModelCheckpoint callback to save model after each epoch
        checkpoint_callback = keras.callbacks.ModelCheckpoint(
            filepath=self.model_path.with_name(f'{self.model_path.stem}_epoch{{epoch:03d}}.keras'),
            save_freq="epoch",
            save_weights_only=False,
            verbose=0
        )
        # Train
        history = self.model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
            callbacks=[checkpoint_callback]
        )

        # Save the final model
        self.model.save(self.model_path)
        print(f"{GREEN}Model saved to {GREEN.UNDERLINED}{self.model_path}{END}")
        end_time = datetime.now()
        self.json_data.update({
            'end_time': end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'time_spent_training': (end_time - start_time).total_seconds(),
            'history': history.history
        })
        json_update(self.json_path, self.json_data)

        acc = history.history['accuracy']
        val_acc = history.history['val_accuracy']
        loss = history.history['loss']
        val_loss = history.history['val_loss']

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
        plt.savefig(self.model_path.with_name(f"{self.model_path.stem} Training and Validation Loss.png"))
        plt.close()

    def test(self, data_dir: Union[Path, str], multiprocessing=False) -> None:
        """
        Test model on images in each class subfolder and print results.
        """

        def test_one_image(class_name, img_path, i, total):
            im = Image.open(img_path)
            clf = self.classify(im)
            prob = clf.expo_preds(1.2)[clf.idx]
            short = shorten(img_path, 2, 3)
            if clf.name == class_name:
                if prob < 0.7:
                    print(f'\r{class_name}({i}/{total}) {YELLOW}{clf.name},{prob:.2f}{END} {short}\n', end='')
                else:
                    print(f'\r{class_name}({i}/{total}) {GREEN}{clf.name},{prob:.2f}{END} {short}', end='')
            else:
                print(f'\r{class_name}({i}/{total}) {RED}{clf.name},{prob:.2f}{END} {short}\n', end='')

        data_dir = Path(data_dir)
        for class_name in self.class_names:
            folder = data_dir / class_name
            if not folder.exists():
                continue
            files = [f for f in folder.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}]
            total = len(files)
            if total == 0:
                continue

            if multiprocessing:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [
                        executor.submit(test_one_image, class_name, img_path, i + 1, total)
                        for i, img_path in enumerate(files)
                    ]
                    for f in concurrent.futures.as_completed(futures):
                        pass
            else:
                for i, img_path in enumerate(files):
                    test_one_image(class_name, img_path, i + 1, total)
        print()


class MultiClassifier:
    def __init__(self, base_path: Union[Path, str]) -> None:
        self.base_path = Path(base_path)
        self.json_config = json_load(self.base_path / 'frames pos.json')
        self.frames = self.json_config.get('frames', {})
        self.classifications: Dict[str, Classification] = {}

        self.img_full_dir = self.base_path / 'img_full'
        self.img_frame_dir = self.base_path / 'img_frame'
        self.img_frame_log_dir = self.base_path / 'img_frame_log'
        self.model_dir = self.base_path / 'model'

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
        for name in self.json_config.get('models', {}):
            model_file = self.model_dir / f"{name}.keras"
            if not model_file.exists():
                model_file = self.model_dir / f"{name}.h5"
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

    def crop_images_all(
            self,
            img_size,
            shift_values=[0],
            brightness_values=[1],
            contrast_values=[1],
    ):
        def process_one_image(model_name, file_name, total_count):
            json_file = self.img_full_dir / f"{file_name}.json"
            img_file = self.img_full_dir / f"{file_name}.png"
            try:
                frames = json_load(str(json_file))
                im = Image(img_file)
            except Exception as e:
                print(f"{RED}Error loading {file_name}: {e}{END}")
                return

            for pos_name, status in frames.items():
                if pos_name not in self.frames:
                    print(f'{pos_name} not in frames')
                    continue
                if self.frames[pos_name]['model'] != model_name:
                    continue

                # Print progress (non-thread-safe, but okay for console)
                print(f'\r{file_name} {model_name} {pos_name} {status}', end='')

                xywhn = self.frames[pos_name]['xywhn']

                # Save original cropped image
                log_dir = self.img_frame_log_dir / model_name
                log_dir.mkdir(parents=True, exist_ok=True)
                im.crop(xywhn=xywhn).save(log_dir / f"{status}_{pos_name}_{file_name}.png")

                # Process and save variations
                variant_dir = self.img_frame_dir / model_name / status
                variant_dir.mkdir(parents=True, exist_ok=True)

                for shift_y in shift_values:
                    for shift_x in shift_values:
                        im_crop = im.crop(xywhn=xywhn, shift=(shift_x, shift_y)).resize(img_size)
                        for brightness in brightness_values:
                            for contrast in contrast_values:
                                for sharpness in [1.0, 5.0]:
                                    im_variant = im_crop.copy().brightness(brightness).contrast(contrast).sharpness(
                                        sharpness)
                                    output_filename = f"{file_name}!{pos_name}!{status}!{shift_y}!{shift_x}!{brightness}!{contrast}!{sharpness}.png"
                                    im_variant.save(variant_dir / output_filename)
            print(f'\rProcessed {file_name} ({model_name})')

        for model_name in self.models.keys():
            print(f'{CYAN}==== {model_name} ===={END}')

            # delete old data
            if (self.img_frame_dir / model_name).exists():
                shutil.rmtree(self.img_frame_dir / model_name)
            if (self.img_frame_log_dir / model_name).exists():
                shutil.rmtree(self.img_frame_log_dir / model_name)

            # crop image
            img_files = sorted({f.stem for f in self.img_full_dir.glob("*") if f.suffix in ['.png', '.json']},
                               reverse=True)
            total_count = len(img_files)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(process_one_image, model_name, file_name, total_count)
                    for file_name in img_files
                ]
                for f in concurrent.futures.as_completed(futures):
                    pass
            print()

    def train_all(
            self,
            epochs=10,
            img_size=(180, 180),
            batch_size=64
    ):
        self.img_full_dir.mkdir(parents=True, exist_ok=True)
        self.img_frame_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        for model_name in self.models.keys():
            print(f'{CYAN}==== {model_name} ===={END}')
            classifier = Classifier(self.model_dir / f'{model_name}.keras')
            classifier.train(
                self.img_frame_dir / model_name,
                epochs=epochs,
                img_size=img_size,
                batch_size=batch_size,
                validation_split=0.2,
                seed=123
            )

    def test_all(self, multiprocessing=False):
        for model_name in self.models.keys():
            print(f'{CYAN}==== {model_name} ===={END}')
            classifier = Classifier(self.model_dir / f'{model_name}.keras')
            classifier.test(self.img_frame_dir / model_name, multiprocessing=multiprocessing)
