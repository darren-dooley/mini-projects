class TcpConnection:
    def __init__(self, server_url):
        self.server_url = server_url

    def resolve_dns():
        pass

    def setup_socket():
        pass

    def send_client_ack():
        pass

    def process_server_ack():
        pass

    def send_hello():
        pass

    def receive_hello():
        pass


if __name__ == "__main__":
    server_url = "https://www.google.com"
    tcp_connection = TcpConnection(server_url)
    assert tcp_connection.server_url == server_url
