import random


def random_str(length=10, ignore_list=[]):
    string = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=length))
    if string in ignore_list:
        string = random_str(length, ignore_list)
    return string
