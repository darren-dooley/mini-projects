"""
Minimal TCP socket server in Python.

This server listens on a local port, accepts a single client connection,
receives one message, sends a response, and then shuts down.

SHORTCUTS TAKEN (vs. production):
- Only handles one client at a time (production would use threading,
  asyncio, or select/poll to handle many clients concurrently).
- No graceful shutdown or signal handling (production would catch SIGINT/
  SIGTERM and clean up resources).
- Fixed buffer size of 1024 bytes — if the client sends more than 1024
  bytes in one message, we'd only read a partial message. Production code
  uses a framing protocol (length-prefix, delimiter, etc.) to know when
  a complete message has been received.
- No error handling or retries (production would wrap operations in
  try/except and handle connection resets, timeouts, etc.).
- No logging framework (production would use the `logging` module).
- No TLS/SSL encryption (production would wrap the socket with `ssl`
  for encrypted communication).
- Hardcoded host/port (production would use config files or env vars).
"""

# `socket` is Python's standard library module that provides access to
# the BSD socket interface — the low-level networking API that all
# operating systems expose for TCP/UDP communication.
import socket

# The host to bind to. "127.0.0.1" (loopback) means only accept
# connections from this machine. Using "0.0.0.0" would accept
# connections from any network interface.
HOST = "127.0.0.1"

# The port number to listen on. Ports below 1024 are reserved for
# well-known services (HTTP=80, HTTPS=443, etc.) and require root
# privileges. We pick an arbitrary high port.
PORT = 65432

# Create a new socket object.
# - `socket.AF_INET` selects IPv4 addressing (as opposed to AF_INET6
#   for IPv6, or AF_UNIX for local inter-process communication).
# - `socket.SOCK_STREAM` selects TCP (a reliable, ordered, byte-stream
#   protocol). The alternative is `SOCK_DGRAM` for UDP (unreliable,
#   unordered, message-based).
#
# The `with` statement ensures the socket is automatically closed when
# we exit the block, even if an exception occurs. Without it, we'd need
# to manually call server_socket.close().
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:

    # SO_REUSEADDR tells the OS to let us bind to this port even if it's
    # in a TIME_WAIT state from a recently closed connection. Without
    # this, restarting the server quickly would fail with "Address already
    # in use". This is a development convenience — in production you'd
    # still use it, but be aware it has subtle security implications on
    # some OSes (Windows allows port hijacking with SO_REUSEADDR).
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # `bind()` associates the socket with a specific network interface
    # and port number. This is what reserves the port in the OS so that
    # incoming packets addressed to HOST:PORT are delivered to this
    # socket. Under the hood this calls the POSIX bind() syscall.
    server_socket.bind((HOST, PORT))

    # `listen()` marks this socket as a passive/listening socket — one
    # that will accept incoming connections rather than initiate outgoing
    # ones. The OS begins maintaining a queue of incoming connection
    # requests.
    #
    # The argument (backlog=1) is the maximum number of queued
    # connections the OS will hold before refusing new ones. We use 1
    # because we only handle one client. Production servers use higher
    # values (e.g. 128).
    server_socket.listen(1)

    print(f"Server listening on {HOST}:{PORT}")

    # `accept()` blocks (pauses execution) until a client connects.
    # When a connection arrives, the OS completes the TCP three-way
    # handshake (SYN -> SYN-ACK -> ACK) and returns:
    # - `client_socket`: a NEW socket object for this specific
    #   connection. The original `server_socket` continues listening.
    # - `client_address`: a tuple of (ip, port) identifying the client.
    #
    # In production, you'd call accept() in a loop and spawn a thread
    # or coroutine for each connection.
    client_socket, client_address = server_socket.accept()

    # Use `with` to ensure the client socket is closed when done.
    with client_socket:
        print(f"Connected by {client_address}")

        # `recv(1024)` reads up to 1024 bytes from the client. This
        # call blocks until data arrives. The number 1024 is the buffer
        # size — the maximum number of bytes to read in one call.
        #
        # IMPORTANT: TCP is a byte stream, not a message stream. A
        # single `send()` on the client side does NOT guarantee a
        # single `recv()` here will get the complete data. Data could
        # arrive split across multiple recv() calls, or multiple sends
        # could be coalesced into one recv(). Production code MUST
        # implement message framing (e.g. newline-delimited, length-
        # prefixed) and loop over recv() until a full message is read.
        data = client_socket.recv(1024)

        # `recv()` returns an empty bytes object (b"") when the client
        # has closed its side of the connection. We check for this to
        # avoid processing empty messages.
        if data:
            # `data` is a `bytes` object (raw bytes), not a `str`.
            # We decode it from UTF-8 to get a Python string. This
            # assumes both sides agree on the encoding — production
            # protocols define this explicitly (e.g. HTTP headers
            # specify Content-Type charset).
            message = data.decode("utf-8")
            print(f"Received: {message}")

            # Build a response and send it back.
            # `encode("utf-8")` converts the str back to bytes,
            # because sockets only transmit raw bytes, never strings.
            response = f"Echo: {message}"
            client_socket.sendall(response.encode("utf-8"))
            # We use `sendall()` instead of `send()` because `send()`
            # may transmit only part of the data (it returns the number
            # of bytes actually sent). `sendall()` loops internally
            # until all bytes are transmitted, which is what we want.

            print(f"Sent: {response}")

    # When we exit the `with client_socket` block, client_socket.close()
    # is called automatically, sending a TCP FIN to the client.

# When we exit the `with server_socket` block, the listening socket is
# closed and the port is released back to the OS.
print("Server shut down.")
