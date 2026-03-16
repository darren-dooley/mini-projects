# Minimal HTTP/3 over QUIC

A from-scratch implementation of HTTP/3 over QUIC using Python sockets, built as a learning exercise. Every line is commented to explain what's happening and why.

## File structure

| File | Purpose |
|---|---|
| `quic.py` | QUIC protocol layer — packet encoding/decoding, connection IDs, streams, ACKs |
| `http3.py` | HTTP/3 framing layer — HEADERS and DATA frames on top of QUIC streams |
| `server.py` | Listens on UDP, accepts QUIC handshakes, serves HTTP/3 responses |
| `client.py` | Connects via QUIC handshake, sends HTTP/3 GET requests, prints responses |

## Usage

Start the server:

```sh
python server.py
```

In another terminal, send requests:

```sh
python client.py          # GET /
python client.py /info    # GET /info
python client.py /notfound # GET /notfound (returns 404)
```

## What makes this "HTTP/3 over QUIC"

1. **UDP transport** — unlike HTTP/1.1 and HTTP/2 which use TCP, everything here runs over raw UDP datagrams
2. **QUIC handshake** — Initial → Handshake packet exchange establishes connection IDs (real QUIC does TLS 1.3 here)
3. **Connection IDs** — packets are routed by connection ID, not by source IP/port (enables connection migration in real QUIC)
4. **Long vs short headers** — handshake packets carry both connection IDs; application data packets only carry the destination ID (saves bytes)
5. **Streams** — data is multiplexed over numbered streams within one connection (no head-of-line blocking)
6. **HTTP/3 binary framing** — requests/responses use HEADERS + DATA frames (not text like HTTP/1.1)
7. **Pseudo-headers** — `:method`, `:path`, `:status` replace the text request/status lines of HTTP/1.1

## What's simplified vs real QUIC/HTTP/3

- No TLS 1.3 encryption (the biggest omission — real QUIC mandates it)
- No packet retransmission or congestion control
- No flow control or stream-level flow control
- No QPACK header compression (we use plain tab-separated text)
- Single-packet requests/responses (no fragmentation)
- No connection migration or path validation
