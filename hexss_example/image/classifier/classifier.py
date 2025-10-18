from pathlib import Path
from hexss.constants import *
from hexss.image import Image
from hexss.image.classifier import Classifier

if __name__ == '__main__':

    data_dir = Path('datasets')
    model_path = Path('classifier_models/model01.keras')

    if not data_dir.exists():
        print(f'{CYAN}========== download example datasets =========={END}')
        from hexss.github import download

        download('hexs', 'Image-Dataset', 'flower_photos', dest_dir=data_dir, max_workers=100)
        # Directory structure:
        # datasets/
        #   class_a/
        #   class_b/
        #   ...

    print(f'{CYAN}============== for create model =============={END}')
    classifier = Classifier(model_path)
    if classifier.model is None:
        classifier.train(
            data_dir,
            epochs=30,
            img_size=[180, 180],
            batch_size=32,
            validation_split=0.2,
        )

    results = classifier.test(data_dir, threshold=0.3, multiprocessing=True)
    print(results)

    print(f'{CYAN}=============== for load model ==============={END}')
    classifier = Classifier(model_path)
    classification = classifier.classify(Image(data_dir / 'roses/353897245_5453f35a8e.jpg'))
    print(classification.name, classification.conf_softmax(1.5))
    classification = classifier.classify(Image(data_dir / 'sunflowers/44079668_34dfee3da1_n.jpg'))
    print(classification.name, classification.conf_softmax(1.5))
    classification = classifier.classify(Image(data_dir / 'roses/12323085443_8ac0cdb713_n.jpg'))
    print(classification.name, classification.conf_softmax(1.5))