import socket


def get_ipv4():
    return socket.gethostbyname(socket.gethostname())
