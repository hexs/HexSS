import os
import sys


def get_script_directory():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_working_directory():
    return os.getcwd()


def move_up(directory_path):
    # cd ..
    return os.path.split(directory_path)[0]


