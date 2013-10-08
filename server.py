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
    


HEARTBEAT_INTERVAL = None    
users = {}
    
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("0.0.0.0", port))
sock.listen(0)

for _ in range(2): # por enquanto, para poder matar
    print("== WATING FOR CLIENT!")
    new_client, client_address = sock.accept()
    new_client.settimeout(HEARTBEAT_INTERVAL)
    
    while True:
        data = new_client.recv(2048)
        if len(data) == 0:
            break
        for command in filter(None, data.splitlines()):
            print(0, command)
    new_client.close()

sock.close()