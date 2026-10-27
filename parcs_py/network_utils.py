import socket


def find_free_port():
    with socket.socket() as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


def get_ip():
    # Deployment supplies the private VM address explicitly.
    return '127.0.0.1'
