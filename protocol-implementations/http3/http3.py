"""
Minimal HTTP/3 framing layer for learning purposes.

HTTP/3 (RFC 9114) runs on top of QUIC streams. It uses a binary framing
format (not text like HTTP/1.1). The two essential frame types are:
  - HEADERS: carries the HTTP headers (method, path, status, etc.)
  - DATA: carries the response/request body

Real HTTP/3 uses QPACK (a compression format) for headers. We use a
trivial key:value\\n encoding instead to keep things understandable.
"""

import struct  # For packing/unpacking binary frame headers


# --- HTTP/3 Frame Types ---
# These are the frame type identifiers defined by RFC 9114.
# We only implement the two essential ones.

H3_FRAME_DATA = 0x00     # Carries the message body (HTML, JSON, etc.)
H3_FRAME_HEADERS = 0x01  # Carries HTTP headers (method, status, path, etc.)


def encode_headers_frame(headers):
    """Encode an HTTP/3 HEADERS frame.

    Takes a dict of HTTP headers and encodes them into a binary frame.
    Real HTTP/3 uses QPACK compression here; we use plain text for clarity.

    Args:
        headers: dict like {":method": "GET", ":path": "/", ":status": "200"}
                 Pseudo-headers (prefixed with ":") are HTTP/3's way of
                 encoding what HTTP/1.1 put in the request/status line.

    Frame format:
      [1 byte ] frame_type   - 0x01 = HEADERS
      [4 bytes] length        - Length of the encoded headers
      [N bytes] header_data   - "key:value\\n" pairs, UTF-8 encoded
    """
    # Encode headers as simple "key\tvalue\n" pairs (tab-separated).
    # We use tab instead of colon because pseudo-headers like ":status"
    # start with ":", which would create ambiguity when splitting on ":".
    # Real QPACK uses Huffman coding and dynamic tables for compression.
    header_bytes = "".join(
        f"{key}\t{value}\n"      # Each header becomes "key\tvalue\n"
        for key, value in headers.items()
    ).encode("utf-8")             # Convert the whole string to bytes

    # Pack the frame header: type byte + length
    frame_header = struct.pack(
        "!B I",            # B=frame type (1 byte), I=length (4 bytes)
        H3_FRAME_HEADERS,  # This is a HEADERS frame
        len(header_bytes), # How many bytes of header data follow
    )
    return frame_header + header_bytes  # Frame header + header data


def encode_data_frame(body):
    """Encode an HTTP/3 DATA frame.

    Wraps a body (bytes) in a DATA frame. This is straightforward -
    just a type, length, and the raw body bytes.

    Args:
        body: bytes containing the message body

    Frame format:
      [1 byte ] frame_type  - 0x00 = DATA
      [4 bytes] length       - Length of the body
      [N bytes] body         - The raw body bytes
    """
    frame_header = struct.pack(
        "!B I",          # B=frame type, I=length
        H3_FRAME_DATA,   # This is a DATA frame
        len(body),       # How many bytes of body follow
    )
    return frame_header + body  # Frame header + body data


def decode_h3_frames(data):
    """Decode all HTTP/3 frames from raw bytes.

    HTTP/3 frames are sent on QUIC streams. A stream might contain
    a HEADERS frame followed by a DATA frame (for a response with a body).
    We read frames sequentially until data is exhausted.
    """
    frames = []    # Accumulate decoded frames
    offset = 0     # Current read position

    while offset < len(data):
        # Not enough bytes for even a frame header (1 + 4 = 5 bytes)
        if offset + 5 > len(data):
            break  # Incomplete frame, stop parsing

        # Read the frame type and payload length
        frame_type, length = struct.unpack_from("!B I", data, offset)
        offset += 5  # Consume the 5-byte frame header

        # Read the frame payload
        payload = data[offset:offset + length]
        offset += length  # Consume the payload bytes

        if frame_type == H3_FRAME_HEADERS:
            # Decode the "key\tvalue\n" header format back into a dict
            header_text = payload.decode("utf-8")  # Bytes -> string
            headers = {}
            for line in header_text.strip().split("\n"):  # Split on newlines
                if "\t" in line:
                    # Split on tab to separate key from value
                    key, value = line.split("\t", 1)
                    headers[key] = value
            frames.append({"type": H3_FRAME_HEADERS, "headers": headers})

        elif frame_type == H3_FRAME_DATA:
            # DATA frames just contain raw bytes, no further decoding needed
            frames.append({"type": H3_FRAME_DATA, "body": payload})

    return frames


def build_request(method, path, host):
    """Build a complete HTTP/3 request as bytes ready to send on a QUIC stream.

    An HTTP/3 request is a HEADERS frame (and optionally a DATA frame for
    POST/PUT bodies, which we skip for simplicity).

    The ":method", ":path", and ":authority" pseudo-headers replace what
    HTTP/1.1 encoded in the request line (e.g. "GET / HTTP/1.1").
    """
    headers = {
        ":method": method,     # GET, POST, etc.
        ":path": path,         # The URL path (e.g. "/")
        ":authority": host,    # The hostname (replaces HTTP/1.1 Host header)
        ":scheme": "https",    # HTTP/3 always uses HTTPS (we fake it)
    }
    return encode_headers_frame(headers)  # Just a single HEADERS frame


def build_response(status, body_text):
    """Build a complete HTTP/3 response as bytes ready to send on a QUIC stream.

    An HTTP/3 response is a HEADERS frame followed by a DATA frame.
    The ":status" pseudo-header replaces the HTTP/1.1 status line.
    """
    # First frame: response headers with status code
    headers = {
        ":status": str(status),          # e.g. "200"
        "content-type": "text/plain",    # We only serve plain text
    }
    headers_frame = encode_headers_frame(headers)

    # Second frame: the response body
    body_bytes = body_text.encode("utf-8")  # Convert string body to bytes
    data_frame = encode_data_frame(body_bytes)

    # Concatenate both frames - they'll be sent together on the same stream
    return headers_frame + data_frame
