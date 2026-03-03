"""
Minimal TCP/IPv4 socket implementation in Mojo using libc FFI.
macOS (Darwin) specific implementation.
"""

from sys.ffi import external_call
from memory import UnsafePointer
from memory.unsafe_pointer import alloc

# ============================================================================
# Constants
# ============================================================================

comptime AF_INET = 2
comptime SOCK_STREAM = 1
comptime SOL_SOCKET = 0xFFFF  # macOS value
comptime SO_REUSEADDR = 0x0004  # macOS value
comptime INADDR_ANY = 0


# ============================================================================
# Structs
# ============================================================================


@fieldwise_init
struct in_addr(Copyable, Movable, ImplicitlyCopyable):
    """IPv4 address structure."""

    var s_addr: UInt32


@fieldwise_init
struct sockaddr_in(Copyable, Movable, ImplicitlyCopyable):
    """IPv4 socket address structure (macOS layout)."""

    var sin_len: UInt8  # macOS only
    var sin_family: UInt8
    var sin_port: UInt16
    var sin_addr: in_addr
    var sin_zero_0: UInt8
    var sin_zero_1: UInt8
    var sin_zero_2: UInt8
    var sin_zero_3: UInt8
    var sin_zero_4: UInt8
    var sin_zero_5: UInt8
    var sin_zero_6: UInt8
    var sin_zero_7: UInt8


fn make_sockaddr_in(family: Int = AF_INET, port: UInt16 = 0, addr: UInt32 = 0) -> sockaddr_in:
    """Create a sockaddr_in with default zero padding."""
    return sockaddr_in(
        sin_len=16,
        sin_family=UInt8(family),
        sin_port=port,
        sin_addr=in_addr(s_addr=addr),
        sin_zero_0=0,
        sin_zero_1=0,
        sin_zero_2=0,
        sin_zero_3=0,
        sin_zero_4=0,
        sin_zero_5=0,
        sin_zero_6=0,
        sin_zero_7=0,
    )


# ============================================================================
# libc FFI bindings (using opaque pointers)
# ============================================================================


fn c_socket(domain: Int32, type: Int32, protocol: Int32) -> Int32:
    """Create a socket."""
    return external_call["socket", Int32, Int32, Int32, Int32](domain, type, protocol)


fn c_bind(sockfd: Int32, addr: UnsafePointer[sockaddr_in], addrlen: UInt32) -> Int32:
    """Bind socket to address."""
    return external_call["bind", Int32](sockfd, addr, addrlen)


fn c_listen(sockfd: Int32, backlog: Int32) -> Int32:
    """Listen for connections."""
    return external_call["listen", Int32, Int32, Int32](sockfd, backlog)


fn c_accept(
    sockfd: Int32, addr: UnsafePointer[sockaddr_in], addrlen: UnsafePointer[UInt32]
) -> Int32:
    """Accept a connection."""
    return external_call["accept", Int32](sockfd, addr, addrlen)


fn c_connect(sockfd: Int32, addr: UnsafePointer[sockaddr_in], addrlen: UInt32) -> Int32:
    """Connect to a server."""
    return external_call["connect", Int32](sockfd, addr, addrlen)


fn c_send(sockfd: Int32, buf: UnsafePointer[UInt8], length: Int, flags: Int32) -> Int:
    """Send data on socket."""
    return external_call["send", Int](sockfd, buf, length, flags)


fn c_recv(sockfd: Int32, buf: UnsafePointer[UInt8], length: Int, flags: Int32) -> Int:
    """Receive data from socket."""
    return external_call["recv", Int](sockfd, buf, length, flags)


fn c_close(fd: Int32) -> Int32:
    """Close a file descriptor."""
    return external_call["close", Int32, Int32](fd)


fn c_setsockopt(
    sockfd: Int32,
    level: Int32,
    optname: Int32,
    optval: UnsafePointer[Int32],
    optlen: UInt32,
) -> Int32:
    """Set socket options."""
    return external_call["setsockopt", Int32](sockfd, level, optname, optval, optlen)


fn htons(hostshort: UInt16) -> UInt16:
    """Convert host byte order to network byte order (16-bit)."""
    return external_call["htons", UInt16, UInt16](hostshort)


fn inet_aton(cp: UnsafePointer[UInt8], inp: UnsafePointer[in_addr]) -> Int32:
    """Convert IPv4 address string to binary form."""
    return external_call["inet_aton", Int32](cp, inp)


# ============================================================================
# Socket struct
# ============================================================================


struct Socket:
    """TCP/IPv4 socket wrapper."""

    var fd: Int32
    var _closed: Bool

    fn __init__(out self):
        """Create a new TCP socket."""
        self.fd = c_socket(AF_INET, SOCK_STREAM, 0)
        self._closed = False

    fn __init__(out self, fd: Int32):
        """Wrap an existing file descriptor."""
        self.fd = fd
        self._closed = False

    fn __del__(deinit self):
        """Close socket on destruction."""
        if not self._closed and self.fd >= 0:
            _ = c_close(self.fd)

    fn is_valid(self) -> Bool:
        """Check if socket was created successfully."""
        return self.fd >= 0

    fn set_reuse_addr(mut self) -> Bool:
        """Enable SO_REUSEADDR option."""
        var optval_ptr = alloc[Int32](1)
        optval_ptr[] = Int32(1)
        var result = c_setsockopt(self.fd, SOL_SOCKET, SO_REUSEADDR, optval_ptr, 4)
        optval_ptr.free()
        return result == 0

    fn bind(mut self, host: String, port: Int) -> Bool:
        """Bind socket to host:port."""
        var addr_ptr = alloc[sockaddr_in](1)
        addr_ptr[] = make_sockaddr_in(AF_INET, htons(UInt16(port)), INADDR_ANY)

        # Parse host address if not binding to all interfaces
        if host != "0.0.0.0" and host != "":
            var host_bytes = host.as_bytes()
            var host_cstr = alloc[UInt8](len(host_bytes) + 1)
            for i in range(len(host_bytes)):
                host_cstr[i] = host_bytes[i]
            host_cstr[len(host_bytes)] = 0  # null terminator

            var in_addr_ptr = alloc[in_addr](1)
            in_addr_ptr[] = addr_ptr[].sin_addr
            var aton_result = inet_aton(host_cstr, in_addr_ptr)
            if aton_result == 0:
                host_cstr.free()
                in_addr_ptr.free()
                addr_ptr.free()
                return False
            addr_ptr[].sin_addr = in_addr_ptr[]
            host_cstr.free()
            in_addr_ptr.free()

        var result = c_bind(self.fd, addr_ptr, 16)
        addr_ptr.free()
        return result == 0

    fn listen(self, backlog: Int = 5) -> Bool:
        """Start listening for connections."""
        var result = c_listen(self.fd, Int32(backlog))
        return result == 0

    fn accept(self) -> Socket:
        """Accept a connection and return new Socket.

        Returns a Socket with fd=-1 on failure.
        """
        var addr_ptr = alloc[sockaddr_in](1)
        addr_ptr[] = make_sockaddr_in()
        var len_ptr = alloc[UInt32](1)
        len_ptr[] = 16

        var client_fd = c_accept(self.fd, addr_ptr, len_ptr)

        addr_ptr.free()
        len_ptr.free()
        return Socket(client_fd)

    fn connect(mut self, host: String, port: Int) -> Bool:
        """Connect to a server at host:port."""
        var addr_ptr = alloc[sockaddr_in](1)
        addr_ptr[] = make_sockaddr_in(AF_INET, htons(UInt16(port)), 0)

        var host_bytes = host.as_bytes()
        var host_cstr = alloc[UInt8](len(host_bytes) + 1)
        for i in range(len(host_bytes)):
            host_cstr[i] = host_bytes[i]
        host_cstr[len(host_bytes)] = 0

        var in_addr_ptr = alloc[in_addr](1)
        in_addr_ptr[] = addr_ptr[].sin_addr
        var aton_result = inet_aton(host_cstr, in_addr_ptr)
        if aton_result == 0:
            host_cstr.free()
            in_addr_ptr.free()
            addr_ptr.free()
            return False
        addr_ptr[].sin_addr = in_addr_ptr[]
        host_cstr.free()
        in_addr_ptr.free()

        var result = c_connect(self.fd, addr_ptr, 16)
        addr_ptr.free()
        return result == 0

    fn send(self, data: String) -> Int:
        """Send string data. Returns bytes sent or -1 on error."""
        var bytes = data.as_bytes()
        var buf = alloc[UInt8](len(bytes))
        for i in range(len(bytes)):
            buf[i] = bytes[i]
        var sent = c_send(self.fd, buf, len(bytes), 0)
        buf.free()
        return sent

    fn send_bytes(self, data: List[UInt8]) -> Int:
        """Send raw bytes. Returns bytes sent or -1 on error."""
        var buf = alloc[UInt8](len(data))
        for i in range(len(data)):
            buf[i] = data[i]
        var sent = c_send(self.fd, buf, len(data), 0)
        buf.free()
        return sent

    fn recv(self, size: Int = 1024) -> List[UInt8]:
        """Receive up to size bytes. Returns empty list on error/close."""
        var buf = alloc[UInt8](size)

        var received = c_recv(self.fd, buf, size, 0)
        if received <= 0:
            buf.free()
            return List[UInt8]()

        var result = List[UInt8](capacity=Int(received))
        for i in range(Int(received)):
            result.append(buf[i])
        buf.free()
        return result^

    fn recv_string(self, size: Int = 1024) -> String:
        """Receive data as string. Returns empty string on error/close."""
        var buf = alloc[UInt8](size + 1)  # +1 for null terminator

        var received = c_recv(self.fd, buf, size, 0)
        if received <= 0:
            buf.free()
            return ""

        buf[Int(received)] = 0  # null terminate
        return String(unsafe_from_utf8_ptr=buf)

    fn close(mut self):
        """Close the socket."""
        if not self._closed and self.fd >= 0:
            _ = c_close(self.fd)
            self._closed = True


# ============================================================================
# Demo: Echo Server
# ============================================================================


fn main():
    """Simple echo server demo."""
    print("Creating socket...")
    var server = Socket()

    if not server.is_valid():
        print("Failed to create socket")
        return

    print("Setting SO_REUSEADDR...")
    if not server.set_reuse_addr():
        print("Warning: Failed to set SO_REUSEADDR")

    print("Binding to 0.0.0.0:8080...")
    if not server.bind("0.0.0.0", 8080):
        print("Failed to bind")
        return

    print("Listening...")
    if not server.listen(5):
        print("Failed to listen")
        return

    print("Echo server running on port 8080")
    print("Test with: echo 'hello' | nc localhost 8080")
    print("Press Ctrl+C to stop")

    while True:
        print("\nWaiting for connection...")
        var client = server.accept()

        if not client.is_valid():
            print("Failed to accept connection")
            continue

        print("Client connected!")

        # Receive data
        var data = client.recv_string(1024)
        if len(data) > 0:
            print("Received: " + data.strip())

            # Echo back
            var sent = client.send("Echo: " + data)
            print("Sent " + String(sent) + " bytes")

        client.close()
        print("Client disconnected")
