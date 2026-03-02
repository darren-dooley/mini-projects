import socket


class SocketClient:
    def __init__(self) -> None:
        self.socket = socket.socket()


if __name__ == "__main__":
    server_ip = "127.0.0.1"
    socket_client = SocketClient()
