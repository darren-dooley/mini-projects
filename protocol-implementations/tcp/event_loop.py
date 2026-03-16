"""
Simplified asyncio event loop.

Demonstrates how asyncio works under the hood: coroutines that yield
control when they'd block on I/O, and a central loop that uses select()
to figure out when to resume them.

Usage:
    python event_loop.py

Then connect with multiple clients:
    python client.py
    python client.py
"""

import select
import socket
import types

HOST = "127.0.0.1"
PORT = 65432


# --- The event loop ---
# This is the core of what asyncio provides. It maintains a list of
# coroutines and uses select() to decide when to resume each one.

class EventLoop:
    def __init__(self):
        # Maps a socket -> coroutine that is waiting on that socket.
        self._readers = {}

    def run(self, coroutine):
        """Start the loop with an initial coroutine."""
        # Kick off the first coroutine. It will run until it hits a
        # yield, telling us which socket it's waiting on.
        self._advance(coroutine)

        while self._readers:
            # This is the ONE blocking call. select() sleeps until at
            # least one of the registered sockets has data ready.
            readable, _, _ = select.select(self._readers.keys(), [], [])

            for sock in readable:
                # Look up which coroutine was waiting on this socket,
                # remove it from the wait list, and resume it.
                coroutine = self._readers.pop(sock)
                self._advance(coroutine)

    def _advance(self, coroutine):
        """Resume a coroutine. It will yield the socket it wants to
        wait on, or raise StopIteration when it's done."""
        try:
            # send(None) resumes the coroutine. It runs until the next
            # yield, which returns the socket it's waiting for.
            sock = coroutine.send(None)
            self._readers[sock] = coroutine
        except StopIteration:
            pass


# --- Coroutines ---
# These look like normal functions but use `yield` to pause execution.
# Each yield says "I need to read from this socket — wake me up when
# it's ready." This is what `await` compiles down to conceptually.

@types.coroutine
def wait_for_read(sock):
    """Pause this coroutine until sock has data ready."""
    yield sock


async def handle_client(client_socket, address):
    """Handle a single client connection."""
    print(f"Connected by {address}")

    # Suspend until data arrives on this socket. The event loop will
    # resume us when select() says this socket is readable.
    await wait_for_read(client_socket)
    data = client_socket.recv(1024)

    if data:
        message = data.decode("utf-8")
        print(f"Received from {address}: {message}")

        response = f"Echo: {message}"
        client_socket.sendall(response.encode("utf-8"))
        print(f"Sent to {address}: {response}")

    client_socket.close()
    print(f"Disconnected {address}")


async def server():
    """Accept connections and spawn a coroutine for each client."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        # Suspend until a new client is waiting to connect.
        await wait_for_read(server_socket)
        client_socket, address = server_socket.accept()

        # Start a new coroutine for this client. We don't await it —
        # we just kick it off and let the event loop manage it.
        # This is like asyncio.create_task().
        loop._advance(handle_client(client_socket, address))


loop = EventLoop()
loop.run(server())
