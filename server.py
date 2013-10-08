import socket, ssl, sys

port = int(sys.argv[1])
tcp = True
if len(sys.argv) > 2:
    if sys.argv[2] == 'udp':
        tcp = False
    elif sys.argv[2] == 'tcp':
        tcp = True
    else:
        raise Exception("Unknown method: " + sys.argv[2])

if not tcp:
    raise Exception("UDP NYI")
    
    
users = {}
    
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("0.0.0.0", port))
sock.listen(0)

for _ in range(2): # por enquanto, para poder matar
    new_client, client_address = sock.accept()
    print(client_address)
    new_client.close()

sock.close()