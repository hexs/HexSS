import os
import signal


def kill():
    os.kill(os.getpid(), signal.SIGINT)
