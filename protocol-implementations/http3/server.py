"""
Minimal HTTP/3 server.

This server listens on a UDP socket, accepts QUIC connections, and
serves HTTP/3 responses. Run it, then use client.py to connect.

Usage: python server.py
"""

import socket  # Python's low-level networking interface

# Import our QUIC and HTTP/3 implementations
from quic import (
    QUICConnection,
    decode_long_header,
    decode_short_header,
    decode_frames,
    PACKET_INITIAL,
    PACKET_HANDSHAKE,
    FRAME_STREAM,
    FRAME_CONN_CLOSE,
)
from http3 import decode_h3_frames, build_response, H3_FRAME_HEADERS


# Server configuration
HOST = "127.0.0.1"  # Listen on localhost only
PORT = 4433         # Port 4433 is conventionally used for QUIC/HTTP3 testing


def handle_request(headers):
    """Route an HTTP/3 request to a response.

    This is our trivial "application layer" - a real server would have
    routing, middleware, file serving, etc. We just return a greeting.
    """
    # Extract the path from the pseudo-headers
    path = headers.get(":path", "/")       # Default to "/" if missing
    method = headers.get(":method", "GET") # Default to GET

    print(f"  Request: {method} {path}")   # Log the request

    # Simple routing: different paths get different responses
    if path == "/":
        return build_response(200, "Hello from HTTP/3 over QUIC!\n")
    elif path == "/info":
        return build_response(200, "This is a minimal HTTP/3 server.\n")
    else:
        return build_response(404, f"Not found: {path}\n")  # 404 for unknown paths


def main():
    # Create a UDP socket. QUIC runs over UDP, not TCP.
    # AF_INET = IPv4, SOCK_DGRAM = UDP (datagrams, not streams)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind the socket to our host and port so clients can connect to us
    sock.bind((HOST, PORT))

    print(f"HTTP/3 server listening on {HOST}:{PORT} (UDP)")
    print("Waiting for QUIC connections...\n")

    # Track active connections by their connection ID
    # In real QUIC, a server handles thousands of concurrent connections
    connections = {}  # connection_id_bytes -> QUICConnection

    while True:
        # Receive a UDP datagram (up to 65535 bytes, the max UDP payload)
        # recvfrom() also gives us the sender's address so we can reply
        data, client_addr = sock.recvfrom(65535)

        # Peek at the first byte to determine if this is a long or short header.
        # Long headers have the first byte < 0x40 in our scheme.
        # Short headers have bit 6 set (0x40).
        first_byte = data[0]

        if first_byte == PACKET_INITIAL:
            # --- QUIC Handshake: Client Initial ---
            # A new client is trying to connect. Decode their Initial packet.
            pkt = decode_long_header(data)
            print(f"[Handshake] Received Initial from {client_addr}")
            print(f"  Client Connection ID: {pkt['src_conn_id'].hex()}")

            # Create a new connection object for this client
            conn = QUICConnection(sock, client_addr)

            # Store the connection indexed by our (server's) connection ID
            # so we can look it up when short header packets arrive later
            connections[conn.local_conn_id] = conn

            # Send our Handshake packet back to the client
            # This tells the client our connection ID and completes the handshake
            conn.send_handshake(pkt["src_conn_id"])
            print(f"  Server Connection ID: {conn.local_conn_id.hex()}")
            print(f"[Handshake] Complete - connection established\n")

        elif first_byte == 0x40:
            # --- Application Data: Short Header ---
            # This is a post-handshake packet carrying HTTP/3 data.
            pkt = decode_short_header(data)

            # Look up the connection by the destination connection ID
            # (which is our local connection ID)
            conn = connections.get(pkt["dest_conn_id"])
            if conn is None:
                print(f"[Error] Unknown connection ID: {pkt['dest_conn_id'].hex()}")
                continue  # Ignore packets for unknown connections

            # Decode the QUIC frames inside this packet
            frames = decode_frames(pkt["payload"])

            for frame in frames:
                if frame["type"] == FRAME_STREAM:
                    # We received stream data - this should be an HTTP/3 request
                    stream_id = frame["stream_id"]
                    print(f"[Stream {stream_id}] Received data ({len(frame['data'])} bytes)")

                    # Decode the HTTP/3 frames within the stream data
                    h3_frames = decode_h3_frames(frame["data"])

                    for h3_frame in h3_frames:
                        if h3_frame["type"] == H3_FRAME_HEADERS:
                            # We got a request! Generate and send a response.
                            response_data = handle_request(h3_frame["headers"])

                            # Send the HTTP/3 response back on the same stream ID.
                            # HTTP/3 uses the same stream for request and response.
                            conn.send_stream_data(stream_id, response_data)
                            print(f"[Stream {stream_id}] Sent response\n")

                            # ACK the client's packet to confirm receipt
                            conn.send_ack(pkt["packet_number"])

                elif frame["type"] == FRAME_CONN_CLOSE:
                    # Client is closing the connection
                    print(f"[Connection] Closed by peer: {frame['reason']}")
                    # Remove the connection from our tracking dict
                    connections.pop(pkt["dest_conn_id"], None)


if __name__ == "__main__":
    main()
