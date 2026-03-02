import socket
import http.client

http_connection_to_server = http.client.HTTPConnection("localhost:8080")
http_connection_to_server.auto_open = 1

http_connection_to_server.putrequest("GET", "/hello")
http_connection_to_server.putheader("Accept", "text/plain")
http_connection_to_server.endheaders()
get_response = http_connection_to_server.getresponse()

print(get_response.status,
      get_response.reason)

get_data = get_response.read()
print(str(get_data))

# http_connection_to_server.close()
# http_connection_to_server.auto_open = 0
#
# http_connection_to_server.request("POST", "/hello", '{"name": "Darren"}')
#
# get_response = http_connection_to_server.getresponse()
#
# print(get_response.status,
#       get_response.reason)
#
# get_data = get_response.read()
# print(repr(get_data))

# http_connection_to_server.close()


# Pure Sockets
# socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# socket.socket.connect).
