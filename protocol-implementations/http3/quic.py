"""
Minimal QUIC protocol implementation for learning purposes.

Real QUIC (RFC 9000) requires TLS 1.3 for encryption, complex congestion
control, flow control, and many frame types. This implementation strips
all of that away to show the core ideas:
  - UDP-based transport
  - Connection IDs to identify connections
  - Packet types for handshake vs application data
  - Numbered streams for multiplexing
  - Simple ACKs for reliability

WARNING: This is NOT secure or production-ready. No encryption, no TLS.
"""

import struct  # For packing/unpacking binary data into network byte order
import os      # For generating random connection IDs


# --- Packet Types ---
# QUIC uses different packet types for different phases of a connection.
# "Long header" packets are used during the handshake (they carry both
# connection IDs). "Short header" packets are used after the handshake
# (they only carry the destination connection ID, saving bytes).

PACKET_INITIAL = 0x00    # Client's first packet - starts the handshake
PACKET_HANDSHAKE = 0x01  # Server's response - completes the handshake
PACKET_SHORT = 0x02      # Application data - used after handshake is done


# --- Frame Types ---
# Each QUIC packet contains one or more "frames". Frames are the actual
# units of communication within a packet.

FRAME_STREAM = 0x08       # Carries stream data (the main workhorse)
FRAME_ACK = 0x02          # Acknowledges received packets
FRAME_CONN_CLOSE = 0x1C   # Signals that the connection is being closed


# --- Connection States ---
# A QUIC connection goes through these states during its lifetime.

STATE_IDLE = 0        # No connection yet
STATE_HANDSHAKING = 1 # Handshake in progress
STATE_ESTABLISHED = 2 # Connection is ready for application data
STATE_CLOSED = 3      # Connection has been closed


def generate_connection_id():
    """Generate a random 8-byte connection ID.

    In real QUIC, connection IDs let the server identify which connection
    a packet belongs to, even if the client's IP address changes (e.g.
    switching from Wi-Fi to cellular). This is a key advantage over TCP.
    """
    return os.urandom(8)  # 8 random bytes = 64-bit ID


def encode_long_header(packet_type, dest_conn_id, src_conn_id, packet_number, payload):
    """Encode a long header packet (used during handshake).

    Long header format:
      [1 byte ] packet_type       - Which type of packet this is
      [4 bytes] version           - QUIC version (we use 0x00000001)
      [1 byte ] dcid_len          - Length of destination connection ID
      [N bytes] dest_conn_id      - Destination connection ID
      [1 byte ] scid_len          - Length of source connection ID
      [N bytes] src_conn_id       - Source connection ID
      [4 bytes] packet_number     - Monotonically increasing packet counter
      [N bytes] payload           - The actual frame data
    """
    header = struct.pack(
        "!B I",             # "!" = network byte order (big-endian), "B" = 1 byte, "I" = 4 bytes
        packet_type,        # Which packet type (Initial or Handshake)
        0x00000001,         # Version 1 - in real QUIC this enables version negotiation
    )
    # Append destination connection ID with its length prefix
    header += struct.pack("!B", len(dest_conn_id)) + dest_conn_id
    # Append source connection ID with its length prefix
    header += struct.pack("!B", len(src_conn_id)) + src_conn_id
    # Append the packet number (used for ACKs and ordering)
    header += struct.pack("!I", packet_number)
    # Append the payload (frames) after the header
    return header + payload


def decode_long_header(data):
    """Decode a long header packet back into its components.

    Returns a dict with all the header fields and the remaining payload.
    """
    offset = 0  # Track our position as we read through the bytes

    # Read packet type (1 byte) and version (4 bytes)
    packet_type, version = struct.unpack_from("!B I", data, offset)
    offset += 5  # 1 + 4 bytes consumed

    # Read destination connection ID
    dcid_len = struct.unpack_from("!B", data, offset)[0]  # Length prefix
    offset += 1
    dest_conn_id = data[offset:offset + dcid_len]         # The actual ID
    offset += dcid_len

    # Read source connection ID
    scid_len = struct.unpack_from("!B", data, offset)[0]
    offset += 1
    src_conn_id = data[offset:offset + scid_len]
    offset += scid_len

    # Read packet number
    packet_number = struct.unpack_from("!I", data, offset)[0]
    offset += 4

    # Everything remaining is the payload (frames)
    payload = data[offset:]

    return {
        "packet_type": packet_type,
        "version": version,
        "dest_conn_id": dest_conn_id,
        "src_conn_id": src_conn_id,
        "packet_number": packet_number,
        "payload": payload,
    }


def encode_short_header(dest_conn_id, packet_number, payload):
    """Encode a short header packet (used for application data after handshake).

    Short header format (more compact than long header):
      [1 byte ] flags             - Always 0x40 to identify as short header
      [8 bytes] dest_conn_id      - Only the destination ID (source is known)
      [4 bytes] packet_number     - Packet counter
      [N bytes] payload           - Frame data
    """
    header = struct.pack(
        "!B",       # 1-byte flags field
        0x40,       # Bit 6 set = short header (real QUIC uses this bit pattern)
    )
    header += dest_conn_id  # Destination connection ID (fixed 8 bytes for us)
    header += struct.pack("!I", packet_number)  # Packet number
    return header + payload


def decode_short_header(data):
    """Decode a short header packet.

    We know the connection ID is always 8 bytes in our implementation.
    """
    offset = 0

    flags = struct.unpack_from("!B", data, offset)[0]
    offset += 1

    # Connection ID is fixed at 8 bytes in our simplified version
    dest_conn_id = data[offset:offset + 8]
    offset += 8

    packet_number = struct.unpack_from("!I", data, offset)[0]
    offset += 4

    payload = data[offset:]

    return {
        "flags": flags,
        "dest_conn_id": dest_conn_id,
        "packet_number": packet_number,
        "payload": payload,
    }


def encode_stream_frame(stream_id, data):
    """Encode a STREAM frame.

    STREAM frames carry application data on a specific stream.
    Streams are QUIC's way of multiplexing multiple independent data
    flows over a single connection (no head-of-line blocking like TCP).

    Format:
      [1 byte ] frame_type  - 0x08 = STREAM
      [8 bytes] stream_id   - Which stream this data belongs to
      [4 bytes] length       - How many bytes of data follow
      [N bytes] data         - The actual stream data
    """
    frame = struct.pack(
        "!B Q I",       # B=1 byte type, Q=8 byte stream ID, I=4 byte length
        FRAME_STREAM,   # Frame type identifier
        stream_id,      # Which stream (HTTP/3 uses different streams per request)
        len(data),      # Length of the data that follows
    )
    return frame + data  # Append the actual data after the frame header


def encode_ack_frame(packet_number):
    """Encode an ACK frame.

    ACK frames tell the sender which packets have been received.
    This is how QUIC provides reliability over unreliable UDP.
    Real QUIC ACKs can acknowledge ranges of packets; ours just ACKs one.

    Format:
      [1 byte ] frame_type     - 0x02 = ACK
      [4 bytes] packet_number  - The packet number being acknowledged
    """
    return struct.pack(
        "!B I",         # B=type, I=packet number
        FRAME_ACK,      # Frame type
        packet_number,  # "I received your packet N"
    )


def encode_conn_close_frame(reason=""):
    """Encode a CONNECTION_CLOSE frame.

    Signals a graceful connection shutdown with an optional reason string.

    Format:
      [1 byte ] frame_type  - 0x1C = CONNECTION_CLOSE
      [4 bytes] reason_len  - Length of the reason string
      [N bytes] reason       - Human-readable close reason (UTF-8)
    """
    reason_bytes = reason.encode("utf-8")  # Convert string to bytes
    return struct.pack(
        "!B I",             # B=type, I=reason length
        FRAME_CONN_CLOSE,   # Frame type
        len(reason_bytes),  # How long the reason string is
    ) + reason_bytes


def decode_frames(payload):
    """Decode all frames from a packet's payload.

    A single QUIC packet can contain multiple frames back-to-back.
    We read them one at a time until the payload is exhausted.
    """
    frames = []       # Accumulate decoded frames here
    offset = 0        # Current read position in the payload

    while offset < len(payload):
        # Peek at the frame type (first byte of each frame)
        frame_type = struct.unpack_from("!B", payload, offset)[0]
        offset += 1  # Consume the type byte

        if frame_type == FRAME_STREAM:
            # Read stream ID (8 bytes) and data length (4 bytes)
            stream_id, length = struct.unpack_from("!Q I", payload, offset)
            offset += 12  # 8 + 4 bytes consumed
            # Read the actual stream data
            data = payload[offset:offset + length]
            offset += length
            frames.append({"type": FRAME_STREAM, "stream_id": stream_id, "data": data})

        elif frame_type == FRAME_ACK:
            # Read the acknowledged packet number (4 bytes)
            packet_number = struct.unpack_from("!I", payload, offset)[0]
            offset += 4
            frames.append({"type": FRAME_ACK, "packet_number": packet_number})

        elif frame_type == FRAME_CONN_CLOSE:
            # Read reason string length, then the reason itself
            reason_len = struct.unpack_from("!I", payload, offset)[0]
            offset += 4
            reason = payload[offset:offset + reason_len].decode("utf-8")
            offset += reason_len
            frames.append({"type": FRAME_CONN_CLOSE, "reason": reason})

        else:
            # Unknown frame type - skip remaining payload
            # Real QUIC has rules about which unknown frames to ignore vs error on
            break

    return frames


class QUICConnection:
    """Manages the state of a single QUIC connection.

    In real QUIC, this would handle TLS, congestion control, flow control,
    packet retransmission, and much more. We only track the essentials:
    connection IDs, state, packet numbering, and stream data.
    """

    def __init__(self, socket, remote_addr):
        """Initialize a new QUIC connection.

        Args:
            socket: The UDP socket to send/receive on
            remote_addr: The (host, port) tuple of the remote peer
        """
        self.socket = socket              # The underlying UDP socket
        self.remote_addr = remote_addr    # Where to send packets to
        self.local_conn_id = generate_connection_id()   # Our connection ID
        self.remote_conn_id = b""         # Peer's connection ID (learned during handshake)
        self.state = STATE_IDLE           # Start with no connection
        self.next_packet_number = 0       # Monotonically increasing counter
        self.streams = {}                 # stream_id -> accumulated bytes

    def _next_pn(self):
        """Get the next packet number and increment the counter.

        Packet numbers are never reused within a connection. They let the
        receiver detect lost packets and send ACKs.
        """
        pn = self.next_packet_number
        self.next_packet_number += 1
        return pn

    def send_initial(self):
        """Client sends an Initial packet to start the QUIC handshake.

        This is the very first packet in a QUIC connection. The client
        picks its own connection ID and sends it to the server. The server
        will respond with its own connection ID in the Handshake packet.
        """
        # The Initial packet payload is empty in our simplified version.
        # In real QUIC, it contains a TLS ClientHello in a CRYPTO frame.
        packet = encode_long_header(
            PACKET_INITIAL,          # This is an Initial packet
            b"\x00" * 8,            # Destination CID: unknown yet, use zeros
            self.local_conn_id,      # Source CID: tell the server who we are
            self._next_pn(),         # First packet number (0)
            b"",                     # No payload (real QUIC: TLS ClientHello)
        )
        self.socket.sendto(packet, self.remote_addr)  # Send over UDP
        self.state = STATE_HANDSHAKING  # We're now waiting for the server's response

    def send_handshake(self, dest_conn_id):
        """Server sends a Handshake packet to complete the handshake.

        The server has received the client's Initial packet and now responds
        with its own connection ID. After this, both sides know each other's
        connection IDs and the connection is established.
        """
        self.remote_conn_id = dest_conn_id  # Remember the client's connection ID
        packet = encode_long_header(
            PACKET_HANDSHAKE,        # This is a Handshake packet
            dest_conn_id,            # Send to the client's connection ID
            self.local_conn_id,      # Tell the client our connection ID
            self._next_pn(),         # Packet number
            b"",                     # No payload (real QUIC: TLS ServerHello)
        )
        self.socket.sendto(packet, self.remote_addr)
        self.state = STATE_ESTABLISHED  # Connection is ready

    def complete_handshake(self, server_conn_id):
        """Client processes the server's Handshake and marks connection as established."""
        self.remote_conn_id = server_conn_id  # Now we know the server's connection ID
        self.state = STATE_ESTABLISHED        # Connection is ready for data

    def send_stream_data(self, stream_id, data):
        """Send data on a specific stream using a short header packet.

        This is how application data (HTTP/3 frames) gets sent after the
        handshake. Each stream is independent - data on stream 0 doesn't
        block stream 4.
        """
        # Wrap the data in a STREAM frame
        frame = encode_stream_frame(stream_id, data)
        # Wrap the frame in a short header packet (compact, post-handshake format)
        packet = encode_short_header(
            self.remote_conn_id,  # Route to the peer's connection ID
            self._next_pn(),      # Unique packet number for ACK tracking
            frame,                # The STREAM frame as payload
        )
        self.socket.sendto(packet, self.remote_addr)

    def send_ack(self, packet_number):
        """Send an ACK for a received packet.

        Without ACKs, the sender wouldn't know if packets arrived (since
        UDP provides no delivery guarantees). Real QUIC batches ACKs and
        uses them to drive congestion control.
        """
        frame = encode_ack_frame(packet_number)
        packet = encode_short_header(
            self.remote_conn_id,
            self._next_pn(),
            frame,
        )
        self.socket.sendto(packet, self.remote_addr)

    def send_close(self, reason="done"):
        """Send a CONNECTION_CLOSE frame to gracefully shut down."""
        frame = encode_conn_close_frame(reason)
        packet = encode_short_header(
            self.remote_conn_id,
            self._next_pn(),
            frame,
        )
        self.socket.sendto(packet, self.remote_addr)
        self.state = STATE_CLOSED  # Mark ourselves as closed

    def receive_stream_data(self, stream_id, data):
        """Buffer received stream data.

        In real QUIC, streams can receive data out of order and we'd need
        to reassemble it. Our simplified version assumes in-order delivery.
        """
        if stream_id not in self.streams:
            self.streams[stream_id] = b""    # Initialize buffer for new stream
        self.streams[stream_id] += data      # Append data to the stream buffer

    def get_stream_data(self, stream_id):
        """Retrieve all buffered data for a stream."""
        return self.streams.get(stream_id, b"")  # Return empty bytes if no data
