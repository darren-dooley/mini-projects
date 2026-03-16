"""
Minimal TCP socket client in Python.

This client connects to the server, sends one message, receives the
server's response, and then disconnects.

SHORTCUTS TAKEN (vs. production):
- Sends exactly one message and quits (production clients typically
  maintain long-lived connections and exchange many messages).
- No reconnection logic (production would retry with exponential
  backoff if the server is unavailable).
- No timeout set — if the server never responds, this client hangs
  forever. Production code sets timeouts via socket.settimeout() or
  SO_RCVTIMEO/SO_SNDTIMEO.
- No error handling (production would catch ConnectionRefusedError,
  TimeoutError, BrokenPipeError, etc.).
- Hardcoded message (production would read from user input, a file,
  or application logic).
- See server.py for additional shortcuts around buffer size, framing,
  TLS, and configuration.
"""

import socket

# Must match the server's HOST and PORT exactly, otherwise the OS
# won't know where to route the connection.
HOST = "127.0.0.1"
PORT = 65432

# Create a TCP/IPv4 socket, same as the server.
# The client and server must agree on the socket family (AF_INET)
# and type (SOCK_STREAM). Mismatched types won't communicate.
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:

    # `connect()` initiates the TCP three-way handshake with the
    # server:
    #   1. Client sends SYN (synchronize) packet to server
    #   2. Server responds with SYN-ACK (synchronize-acknowledge)
    #   3. Client sends ACK (acknowledge)
    # After this completes, a full-duplex (bidirectional) byte stream
    # is established. This call blocks until the handshake completes
    # or fails (e.g. ConnectionRefusedError if nothing is listening).
    #
    # Note: the client does NOT call bind() — the OS automatically
    # assigns an available local port (an "ephemeral port", typically
    # in range 49152-65535). Only servers need to bind to a known port.
    client_socket.connect((HOST, PORT))

    # The message we want to send. This is a regular Python string.
    message = "Hello from the client!"

    # `sendall()` converts our string to raw bytes via encode() and
    # transmits them over the TCP connection. The bytes travel through:
    #   1. Our process's send buffer (in kernel memory)
    #   2. The local network stack (TCP segmentation, IP routing)
    #   3. The loopback interface (since we're on 127.0.0.1; on a
    #      real network this would go through a NIC and physical media)
    #   4. The server process's receive buffer (in kernel memory)
    #   5. The server's recv() call reads from that buffer
    client_socket.sendall(message.encode("utf-8"))
    print(f"Sent: {message}")

    # Block until the server sends a response. Same caveats as the
    # server's recv() — we may not get the full response in one call.
    # For this minimal example with short messages, one recv() suffices.
    data = client_socket.recv(1024)

    # Decode the raw bytes back into a string and display it.
    print(f"Received: {data.decode('utf-8')}")

# Exiting the `with` block closes the socket, which sends a TCP FIN
# (finish) packet to the server, initiating a graceful connection
# teardown (the four-way FIN handshake: FIN -> ACK -> FIN -> ACK).
print("Connection closed.")
