from pathlib import Path
from typing import Union, Optional

from hexss.box import Box
from hexss.image import Image, ImageFont


class Models:
    def __init__(self, model_path: Union[Path, str]):
        self.classifiers = {}
        self.detectors = {}
        self.model_path = Path(model_path)
        self.classifier_model_path = self.model_path / 'classifier'
        self.detector_model_path = self.model_path / 'detector'

    def add_model(self, model_name: str, type_: str):
        from hexss.image.classifier import Classifier
        from hexss.image.detector import Detector

        if type_ == 'classifier':
            if model_name not in self.classifiers:
                model_file = self.classifier_model_path / model_name / 'model' / f'{model_name}.keras'
                self.classifiers[model_name] = Classifier(model_file)
                # if self.classifiers[model_name].model is None:
                #     try:
                #         self.classifiers[model_name].train(
                #             self.model_path / fr'classifier/{model_name}/datasets',
                #             epochs=200
                #         )
                #     except:
                #         ...
        elif type_ == 'detector':
            if model_name not in self.detectors:
                print(list((self.detector_model_path / model_name / 'model').iterdir()))
                last_model = list((self.detector_model_path / model_name / 'model').iterdir())[-1]
                print(last_model)
                model_file = last_model / 'weights/best.pt'
                print(model_file, model_file.exists())
                if model_file.exists():
                    self.detectors[model_name] = Detector(model_file)

    def load_all(self, root_dict: dict):
        def recurse(node):
            if isinstance(node, dict):
                cls = node.get('classifier')
                if isinstance(cls, dict) and cls.get('name'):
                    self.add_model(cls['name'], 'classifier')
                det = node.get('detector')
                if isinstance(det, dict) and det.get('name'):
                    self.add_model(det['name'], 'detector')
                for value in node.values():
                    recurse(value)
            elif isinstance(node, list):
                for item in node:
                    recurse(item)

        recurse(root_dict)


class ImageBox:
    def __init__(self, name='root', box=Box(xywhn=[0.5, 0.5, 1.0, 1.0])):
        self.name = name
        self.box: Box = box
        self.color = (255, 255, 0)
        self.width = 5
        self.text_color = 'black'
        self.text_stroke_color = 'white'
        self.show_name = True
        self.font = ImageFont.load_default(20)

        self.image = None
        self.imxes: dict[str, 'ImageBox'] = {}
        self.detector_imxes: list['ImageBox'] = []

        self.detector_name = None
        self.detections = []
        self.detector_box_setup = {}

        self.classifier_name = None
        self.classification = None

    def set_image(self, image: Image):
        self.image = image
        self.box.set_size(image.size)
        for name, child in self.imxes.items():
            child.box.set_size(self.box.xywh[2:])
            child.set_image(image.crop(child.box).copy())

    def set_components(self, imxes_dict):
        for name, imx_dict in imxes_dict.items():
            imx = ImageBox(name, Box(xywhn=imx_dict['xywhn']))
            imx.classifier_name = (imx_dict.get('classifier') or {}).get('name')
            imx.detector_name = (imx_dict.get('detector') or {}).get('name')
            imx.detector_box_setup = (imx_dict.get('detector') or {}).get('imxes_setup') or {}
            self.add_imx(imx)

    def add_imx(self, imx: 'ImageBox'):
        if self.image is not None:
            imx.box.set_size(self.image.size)
            imx.image = self.image.crop(imx.box)
        self.imxes[imx.name] = imx

    def add_detector_imx(self, imx: 'ImageBox'):
        if self.image is not None:
            imx.box.set_size(self.image.size)
            imx.image = self.image.crop(imx.box)
        self.detector_imxes.append(imx)

    def reset_detector_imx(self):
        self.detector_imxes = []

    def draw_boxes(
            self,
            image: Union[Image],
            thickness: int = 2,
            font_size: int = 14
    ) -> Image:
        image = Image(image)
        draw = image.draw()
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default(font_size)

        for det in self.detections:
            x1, y1, x2, y2 = map(int, det.xyxy)
            label = f"{det.name} {det.conf:.2f}"
            draw.rectangle([x1, y1, x2, y2], outline="red", width=thickness)
            draw.text((x1, y1), label, fill="black", font=font, stroke_width=thickness, stroke_fill="white")

        return image

    def draw_box(
            self,
            image: Image = None,
            color='yellow',
            thickness: int = 2,
            font_size: int = 14
    ) -> Image:
        if image is not None:
            self.set_image(Image(image))
        image = self.image.copy()
        draw = image.draw()
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default(font_size)

        for name, imx in self.imxes.items():
            draw.rectangle(imx.box, outline=color, width=thickness)
            draw.text(imx.box.x1y1, name, fill="black", font=font, stroke_width=thickness, stroke_fill="white")
        return image

    def publish(self, winname):
        self.draw_all(self.image.copy()).publish(winname)

    def detect(self, models: Optional[Models], model_name):
        self.reset_detector_imx()
        if self.image is None or model_name not in models.detectors:
            self.detections = []
            return self.detections

        self.detections = models.detectors[model_name].detect(self.image)
        for i, detection in enumerate(self.detections):
            detection.image = self.image.crop(detection.box).copy()
            imx = ImageBox(f'{i}', Box(xywhn=detection.xywhn))
            imx.classifier_name = (self.detector_box_setup.get('classifier') or {}).get('name')
            imx.detector_name = (self.detector_box_setup.get('detector') or {}).get('name')
            self.add_detector_imx(imx)

        return self.detections

    def classify(self, models: Optional[Models], model_name):
        if self.image is None or model_name not in models.classifiers:
            return

        self.classification = models.classifiers[model_name].classify(self.image)
        if self.classification.group == 'OK':
            self.color = 'green'
        elif self.classification.group == 'NG':
            self.color = 'red'
        else:
            self.color = '#22f'
        return self.classification

    def predict(self, models: Optional[Models] = None):
        if self.image is None or models is None:
            return

        if self.detector_name in models.detectors:
            self.detect(models, self.detector_name)

        if self.classifier_name in models.classifiers:
            if models.classifiers[self.classifier_name].model is not None:
                self.classify(models, self.classifier_name)

        for child in self.detector_imxes:
            child.predict(models)
        for child in self.imxes.values():
            child.predict(models)

    def save(self, path: Union[str, Path]):
        if self.image:
            self.image.save(path)

    def draw_all(self, image: Image) -> Image:
        draw = image.draw()
        self.box.set_size(image.size)

        if self.box.type == 'polygon':
            draw.polygon(self.box, outline=self.color, width=self.width)
            if self.show_name:
                draw.text(self.box.points[0], self.name, font=self.font, fill=self.text_color,
                          stroke_width=self.width, stroke_fill=self.text_stroke_color)
        elif self.box.type == 'box':
            draw.rectangle(self.box.xyxy, outline=self.color, width=self.width)
            if self.show_name:
                draw.text(self.box.x1y1, self.name, font=self.font, fill=self.text_color,
                          stroke_width=self.width, stroke_fill=self.text_stroke_color)

        cropped = image.crop(self.box.xyxy).copy()
        for child in self.imxes.values():
            child.draw_all(cropped)
        for child in self.detector_imxes:
            child.draw_all(cropped)
        image.overlay(cropped, self.box.x1y1.astype(int).tolist())
        return image

    @classmethod
    def from_dict(cls, data: dict) -> 'ImageBox':
        def create_box(name: str, box_data: dict) -> 'ImageBox':
            box = cls(name, Box(
                xywhn=box_data.get('xywhn'),
                pointsn=box_data.get('pointsn')
            ))

            image_data = box_data.get('image')
            if image_data is not None:
                boxes_data = image_data.get('boxes')
                classifier_data = image_data.get('classifier')
                detector_data = image_data.get('detector')

                if boxes_data is not None:
                    for child_name, child_data in boxes_data.items():
                        child_box = create_box(child_name, child_data)
                        box.add(child_box)
                if classifier_data is not None:
                    box.classifier_name = classifier_data.get('name')
                    box.classifier_ok_group = classifier_data.get('ok_group')
                    box.classifier_ng_group = classifier_data.get('ng_group')

                if detector_data is not None:
                    box.detector_name = detector_data.get('name')
                    box.detector_should_count = detector_data.get('should_count')
                    _classifier = detector_data.get('classifier')
                    if _classifier:
                        box.detector_classifier_name = _classifier.get('name')

            return box

        root = cls("root", Box(xywhn=[0.5, 0.5, 1.0, 1.0]))
        root_data = data.get('boxes', {})
        for name, box_data in root_data.items():
            root.add_imx(create_box(name, box_data))
        return root
