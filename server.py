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
    


HEARTBEAT_INTERVAL = 20
users = {}
    
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("0.0.0.0", port))
sock.listen(0)

for _ in range(2): # por enquanto, para poder matar
    print("== WATING FOR CLIENT!")
    new_client, client_address = sock.accept()
    new_client.settimeout(HEARTBEAT_INTERVAL)
    
    username = None
    client_running = True
    
    while client_running:
        try:
            data = new_client.recv(2048)
        except socket.timeout:
            break
        if len(data) == 0:
            break
        for command in filter(None, data.splitlines()):
            if command.split(' ', 1)[0].upper() == 'LOGIN':
                try_username = command.split(' ', 1)[1]
                if try_username in users:
                    new_client.send("USER_ALREADY_EXISTS\n")
                else:
                    username = try_username
                    users[username] = True
                    new_client.send("WELCOME\n")
                # STUFF TO DO ON LOGIN
            elif command.upper() == "LOGOUT":
                client_running = False
                break
            else: # command == "HEARTBEAT"
                pass
    if username:
        del users[username]
    new_client.close()

sock.close()