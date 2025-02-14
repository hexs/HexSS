from hexss import check_packages

check_packages('ultralytics', auto_install=True, verbose=False)

from .object_detector import ObjectDetector
