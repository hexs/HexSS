from multiprocessing import freeze_support
from hexss.server import start_camera_server

if __name__ == '__main__':
    freeze_support()
    start_camera_server()