import os
import shutil
from datetime import datetime
from pathlib import Path
from pprint import pprint
from typing import Union, Optional, Any, Dict, List, Tuple, Self
import concurrent.futures

import hexss
from hexss import json_load, json_dump, json_update
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
    hexss.check_packages('tensorflow', 'matplotlib', auto_install=True)
    import tensorflow as tf
    import keras
    from keras.models import load_model  # type: ignore


def default_layers(img_size: Tuple[int, int], num_classes: int) -> list[Any]:
    """
    Returns a default list of layers for model construction.
    """
    return [
        keras.layers.RandomFlip('horizontal', input_shape=(*img_size, 3)),
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
        keras.layers.Dense(num_classes, name='outputs')
    ]


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
    __slots__ = ('model_path', 'json_path', 'config', 'model', 'class_names', 'img_size', 'layers')

    def __init__(
            self,
            model_path: Union[Path, str],
            config: Optional[Dict[str, Any]] = None
    ) -> None:
        '''
        :param model_path: `.keras` file path
        :param config: data of `.keras` file
                        example
                        {
                            "class_names": ["ng", "ok"],
                            "img_size": [32, 32],
                            ...
                        }
        '''
        self.model_path = Path(model_path)
        self.json_path = self.model_path.with_suffix('.json')
        self.config = config or json_load(self.json_path, {'img_size': [180, 180], 'class_names': []})
        ############################ for support old data ############################
        if 'model_class_names' in self.config:
            self.config['class_names'] = self.config.pop('model_class_names')
        ###############################################################################
        self.class_names: List[str] = self.config.get('class_names', [])
        self.img_size: Tuple[int, int] = tuple(self.config.get('img_size'))
        self.layers: Optional[List[Any]] = None
        self.model: Optional[keras.Model] = None
        self.load_model()

    def load_model(self) -> Self:
        if not self.model_path.exists():
            if self.model_path.with_suffix('.h5').exists():
                self.model = keras.models.load_model(self.model_path.with_suffix('.h5'))
                return self
            print(f"Warning: Model file {self.model_path} not found. Train with .train()")
            return self

        self.model = keras.models.load_model(self.model_path)
        return self

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

        arr = cv2.resize(arr, self.img_size)
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

    def train(
            self,
            data_dir: Union[Path, str],
            epochs: int = 50,
            img_size: Tuple[int, int] = (180, 180),
            batch_size: int = 64,
            validation_split: float = 0.2,
            seed: int = 123,
            layers: Optional[List[Any]] = None
    ) -> None:

        data_dir = Path(data_dir)
        self.img_size = img_size
        train_ds, val_ds = keras.utils.image_dataset_from_directory(
            data_dir,
            validation_split=validation_split,
            subset='both',
            seed=seed,
            image_size=self.img_size,
            batch_size=batch_size
        )
        self.class_names = train_ds.class_names
        start_time = datetime.now()
        # Build config
        self.config = json_dump(self.json_path, {
            'class_names': self.class_names,
            'img_size': list(self.img_size),
            'epochs': epochs,
            'batch_size': batch_size,
            'validation_split': validation_split,
            'seed': seed,
            'start_time': start_time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Build model
        self.layers = layers or default_layers(self.img_size, len(self.class_names))
        AUTOTUNE = tf.data.AUTOTUNE
        train_ds = train_ds.cache().shuffle(1000).prefetch(AUTOTUNE)
        val_ds = val_ds.cache().prefetch(AUTOTUNE)
        self.model = keras.Sequential(self.layers)
        self.model.compile(
            optimizer='adam',
            loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
            metrics=['accuracy']
        )
        self.model.summary()

        # Save model after each epoch
        checkpoint_callback = keras.callbacks.ModelCheckpoint(
            filepath=self.model_path.with_name(f'{self.model_path.stem}_epoch{{epoch:03d}}.keras'),
            save_freq='epoch',
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

        # Save final model
        self.model.save(self.model_path)
        print(f"{GREEN}Model saved to {GREEN.UNDERLINED}{self.model_path}{END}")
        end_time = datetime.now()
        self.config.update({
            'end_time': end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'time_spent_training': (end_time - start_time).total_seconds(),
            'history': history.history
        })
        json_update(self.json_path, self.config)

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
        plt.savefig(self.model_path.with_name(f"{self.model_path.stem} Training and Validation Loss.png"))
        plt.close()

    def test(
            self,
            data_dir: Union[Path, str],
            threshold: float = 0.7,
            multiprocessing: bool = False,
    ) -> Dict[str, int]:
        """
        Test model on images in each class subfolder and print results.
        """
        data_dir = Path(data_dir)
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


class MultiClassifier:
    """
    Manages multiple named classifiers applied to subregions (frames) of full images.

    Attributes:
        base_path: Directory containing 'frames pos.json', 'img_full', 'img_frame', 'img_frame_log', and 'model'.
        frames: Mapping of frame keys to frame metadata (xywhn, model, resultMapping).
        models: Loaded Classifier instances keyed by model name.
    """

    def __init__(self, base_path: Union[Path, str]) -> None:
        self.base_path = Path(base_path)
        self.json_config = json_load(self.base_path / 'frames pos.json')
        raw_frames = self.json_config.get('frames', {})
        self.frames: Dict[str, Dict[str, Any]] = self._normalize(raw_frames)
        self.classifications: Dict[str, Classification] = {}

        # directories
        self.img_full_dir = self.base_path / 'img_full'
        self.img_frame_dir = self.base_path / 'img_frame'
        self.img_frame_log_dir = self.base_path / 'img_frame_log'
        self.model_dir = self.base_path / 'model'

        # load models
        self.models: Dict[str, Classifier] = {}
        for name in self.json_config.get('models', {}):
            model_file = self.model_dir / f"{name}.keras"
            # if not model_file.exists():
            #     model_file = self.model_dir / f"{name}.h5"
            self.models[name] = Classifier(model_file)

    def __repr__(self) -> str:
        return f"<MultiClassifier base_path={self.base_path} models={list(self.models)} frames={list(self.frames)}>"

    @staticmethod
    def _normalize(frames: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Normalize legacy keys: 'xywh' → 'xywhn', 'model_used' → 'model', 'res_show' → 'resultMapping'.
        """
        normalized = {}
        for key, frame in frames.items():
            f = frame.copy()
            if 'xywh' in f:
                f['xywhn'] = f.pop('xywh')
            if 'model_used' in f:
                f['model'] = f.pop('model_used')
            if 'res_show' in f:
                f['resultMapping'] = f.pop('res_show')
            normalized[key] = f
        return normalized

    def classify_all(
            self,
            im: Union[Image, PILImage.Image, np.ndarray]
    ) -> Dict[str, Classification]:
        im = Image(im)
        self.classifications: Dict[str, Classification] = {}
        for key, frame in self.frames.items():
            model_name = frame['model']
            if model_name not in self.models:
                continue

            xywhn = frame['xywhn']
            mapping = frame['resultMapping']
            crop_im = im.crop(xywhn=xywhn)
            self.classifications[key] = self.models[model_name].classify(crop_im, mapping=mapping, xywhn=xywhn)
        return self.classifications

    def crop_images_all(
            self,
            img_size: Tuple[int, int],
            shift_values: Optional[List[int]] = None,
            brightness_values: Optional[List[float]] = None,
            contrast_values: Optional[List[float]] = None,
            sharpness_values: Optional[List[float]] = None,
    ) -> None:
        """
        For each full image JSON and PNG pair in img_full, crop each defined frame,
        log original crops, then generate and save variations by shift, brightness,
        contrast, and sharpness settings.
        """
        shift_values = shift_values or [0]
        brightness_values = brightness_values or [1.0]
        contrast_values = contrast_values or [1.0]
        sharpness_values = sharpness_values or [1.0]

        def process_one_image(file_name):
            json_path = self.img_full_dir / f"{file_name}.json"
            img_path = self.img_full_dir / f"{file_name}.png"
            try:
                frames_status = json_load(json_path)
                im = Image(img_path)
            except Exception as e:
                print(f"{RED}Error loading {file_name}: {e}{END}")
                return

            for frame_name, status in frames_status.items():
                if frame_name not in self.frames:
                    print(f'{frame_name} not in frames')
                    continue
                frame = self.frames[frame_name]
                if frame['model'] != model_name:
                    continue
                print(end=f'\r{file_name} {model_name} {frame_name} {status}')

                # Save original cropped image
                log_dir = self.img_frame_log_dir / model_name
                variant_dir = self.img_frame_dir / model_name / status
                # log_dir.mkdir(parents=True, exist_ok=True)
                variant_dir.mkdir(parents=True, exist_ok=True)

                xywhn = frame['xywhn']
                im.crop(xywhn=xywhn).save(log_dir / f"{status}_{frame_name}_{file_name}.png")

                for sx in shift_values:
                    for sy in shift_values:
                        im_crop = im.crop(xywhn=xywhn, shift=(sx, sy)).resize(img_size)
                        for b in brightness_values:
                            for c in contrast_values:
                                for sharp in sharpness_values:
                                    im_variant = im_crop.copy().sharpness(sharp).brightness(b).contrast(c)
                                    output_filename = f"{file_name}!{frame_name}!{status}!{sx}!{sy}!{b}!{c}!{sharp}.png"
                                    im_variant.save(variant_dir / output_filename)
            print(f'\rProcessed {file_name} ({model_name})')

        for model_name in self.models.keys():
            print(f'{CYAN}==== {model_name} ===={END}')

            # clear old outputs
            shutil.rmtree(self.img_frame_dir / model_name, ignore_errors=True)
            shutil.rmtree(self.img_frame_log_dir / model_name, ignore_errors=True)

            # crop image
            img_files = sorted({f.stem for f in self.img_full_dir.glob("*") if f.suffix in ['.png', '.json']},
                               reverse=True)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(process_one_image, file_name)
                    for file_name in img_files
                ]
                for f in concurrent.futures.as_completed(futures):
                    pass
            print()

    def train_all(
            self,
            epochs: int = 10,
            img_size: Tuple[int, int] = (180, 180),
            batch_size: int = 64,
            validation_split: float = 0.2,
            seed: int = 123,
            layers: Optional[List[Any]] = None
    ) -> None:
        """
        Train each model using its corresponding directory under img_frame.
        """
        self.img_full_dir.mkdir(parents=True, exist_ok=True)
        self.img_frame_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        for model_name, clf in self.models.items():
            print(f'{CYAN}==== Training {model_name} ===={END}')
            clf.train(
                data_dir=self.img_frame_dir / model_name,
                epochs=epochs,
                img_size=img_size,
                batch_size=batch_size,
                validation_split=validation_split,
                seed=seed,
                layers=layers
            )

    def test_all(
            self,
            data_dir: str | Path,
            threshold: float = 0.7,
            shift_values: Optional[List[int]] = None,
            brightness_values: Optional[List[float]] = None,
            contrast_values: Optional[List[float]] = None,
            sharpness_values: Optional[List[float]] = None,
    ):
        data_dir = Path(data_dir)
        img_paths = sorted({
            f for f in data_dir.glob("*") if f.suffix == '.png'
        }, reverse=True)
        for img_path in img_paths:
            print(img_path)
            json_path = img_path.with_suffix('.json')
            if not json_path.exists():
                continue
            json_data = json_load(json_path)
            im = Image(img_path)

            stop = False
            im.image.thumbnail((1366, 768))

            draw = im.draw()
            font = ImageFont.truetype("arial.ttf", 14)

            clfs = self.classify_all(im)

            for frame_name, cls in clfs.items():
                ans = json_data.get(frame_name)
                if ans is None:
                    continue
                clf = clfs[frame_name]
                prob = clf.expo_preds(1.2)[clf.idx]
                is_match = clf.name == ans
                is_confident = is_match and prob >= threshold
                if is_confident:
                    outline = (0, 255, 255)
                    print(f'{frame_name}:{ans} -> {GREEN}{clf.name} {prob}{END}')
                elif is_match:
                    outline = (255, 255, 0)
                    print(f'{frame_name}:{ans} -> {YELLOW}{clf.name} {prob}{END}')
                    stop = True
                else:
                    outline = (255, 100, 0)
                    print(f'{frame_name}:{ans} -> {RED}{clf.name} {prob}{END}')
                    stop = True

                xywh = (np.array(clf.xywhn) * np.resize(im.size, 4)).tolist()
                xy = [xywh[0] - xywh[2] / 2, xywh[1] - xywh[3] / 2]
                xyxy = [xywh[0] - xywh[2] / 2, xywh[1] - xywh[3] / 2, xywh[0] + xywh[2] / 2, xywh[1] + xywh[3] / 2]

                draw.set_origin('topleft')
                draw.rectangle(xyxy, outline=outline, width=2)
                draw.set_origin(xy)
                draw.text((0, -35), f'{frame_name}:{ans}', fill=(0, 0, 0), font=font,
                          stroke_width=2, stroke_fill='white')
                draw.text((0, -20), f'{cls.name} {prob:.3f}', fill=(0, 0, 0), font=font,
                          stroke_width=2, stroke_fill='white')

            draw.set_origin((20, 20))
            draw.text((0, 0), f"{img_path}", fill=(0, 0, 0), font=font, stroke_width=2, stroke_fill='white')

            if stop:
                draw.move_origin((0, 20)).text((0, 0), f"press key to continue", fill=(0, 0, 0), font=font,
                                               stroke_width=2, stroke_fill='white')

            cv2.imshow(f"display", im.numpy())
            cv2.waitKey(0 if stop else 1)

        cv2.destroyAllWindows()
        print()
