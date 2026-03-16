"""
Minimal HTTP/3 client.

Connects to the server via QUIC, sends an HTTP/3 GET request,
and prints the response. Run server.py first, then this.

Usage: python client.py [path]
  Examples:
    python client.py          # GET /
    python client.py /info    # GET /info
"""

import socket  # Python's low-level networking interface
import sys     # For reading command-line arguments

# Import our QUIC and HTTP/3 implementations
from quic import (
    QUICConnection,
    decode_long_header,
    decode_short_header,
    decode_frames,
    PACKET_HANDSHAKE,
    FRAME_STREAM,
    FRAME_ACK,
    STATE_ESTABLISHED,
)
from http3 import build_request, decode_h3_frames, H3_FRAME_HEADERS, H3_FRAME_DATA


# Server address to connect to (must match server.py)
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 4433


def main():
    # Read the request path from command-line args, defaulting to "/"
    path = sys.argv[1] if len(sys.argv) > 1 else "/"

    # Create a UDP socket (QUIC runs over UDP)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Set a 5-second timeout so we don't hang forever waiting for a response.
    # UDP has no built-in connection concept, so without a timeout,
    # recvfrom() would block indefinitely if the server is down.
    sock.settimeout(5.0)

    # Create a QUIC connection object pointed at the server
    conn = QUICConnection(sock, (SERVER_HOST, SERVER_PORT))

    # === Step 1: QUIC Handshake ===
    # Send an Initial packet to start the connection
    print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
    print(f"  Our Connection ID: {conn.local_conn_id.hex()}")
    conn.send_initial()

    # Wait for the server's Handshake response
    try:
        data, addr = sock.recvfrom(65535)  # Block until we get a response
    except socket.timeout:
        print("Error: No response from server (is it running?)")
        return

    # Decode the server's Handshake packet
    pkt = decode_long_header(data)

    if pkt["packet_type"] != PACKET_HANDSHAKE:
        print(f"Error: Expected Handshake packet, got type {pkt['packet_type']}")
        return

    # Complete the handshake - now we know the server's connection ID
    conn.complete_handshake(pkt["src_conn_id"])
    print(f"  Server Connection ID: {pkt['src_conn_id'].hex()}")
    print("  Handshake complete!\n")

    # === Step 2: Send HTTP/3 Request ===
    # Build an HTTP/3 GET request and send it on stream 0.
    # In real HTTP/3, client-initiated request streams use IDs 0, 4, 8, 12...
    # (increments of 4, because the two low bits encode stream type).
    stream_id = 0  # First client-initiated bidirectional stream
    request_data = build_request("GET", path, SERVER_HOST)

    print(f"Sending GET {path} on stream {stream_id}...")
    conn.send_stream_data(stream_id, request_data)

    # === Step 3: Receive HTTP/3 Response ===
    # Wait for the server's response (may arrive as multiple UDP datagrams)
    try:
        data, addr = sock.recvfrom(65535)  # Receive the response packet
    except socket.timeout:
        print("Error: Timed out waiting for response")
        return

    # The response comes in a short header packet (post-handshake)
    pkt = decode_short_header(data)

    # Decode the QUIC frames inside the packet
    frames = decode_frames(pkt["payload"])

    for frame in frames:
        if frame["type"] == FRAME_STREAM:
            # This stream data contains HTTP/3 frames (HEADERS + DATA)
            h3_frames = decode_h3_frames(frame["data"])

            print("\n--- Response ---")
            for h3_frame in h3_frames:
                if h3_frame["type"] == H3_FRAME_HEADERS:
                    # Print the response headers
                    for key, value in h3_frame["headers"].items():
                        print(f"  {key}: {value}")
                elif h3_frame["type"] == H3_FRAME_DATA:
                    # Print the response body
                    print(f"\n{h3_frame['body'].decode('utf-8')}")

    # We might also receive an ACK packet from the server - try to read it
    # but don't fail if it doesn't come (non-blocking receive with short timeout)
    sock.settimeout(0.5)  # Short timeout for optional ACK
    try:
        data, addr = sock.recvfrom(65535)
        # We received something (likely the ACK), but we don't need to process it
    except socket.timeout:
        pass  # No ACK received, that's fine for our demo

    # === Step 4: Close Connection ===
    # Send a CONNECTION_CLOSE to cleanly shut down
    conn.send_close("client done")
    print("Connection closed.")

    # Close the UDP socket
    sock.close()


if __name__ == "__main__":
    main()
