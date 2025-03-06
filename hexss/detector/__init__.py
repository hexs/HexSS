from hexss import check_packages

check_packages('ultralytics', auto_install=True)

from .object_detector import ObjectDetector
