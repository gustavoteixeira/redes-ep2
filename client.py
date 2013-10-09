import socket, sys, re

host = sys.argv[1]
port = int(sys.argv[2])
tcp = True
if len(sys.argv) > 3:
    if sys.argv[3] == 'udp':
        tcp = False
    elif sys.argv[3] == 'tcp':
        tcp = True
    else:
        raise Exception("Unknown method: " + sys.argv[2])
        
if not tcp:
    raise Exception("UDP NYI")
    
listensock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listensock.bind(("0.0.0.0", 0))
listensock.listen(0)
listenaddr = listensock.getsockname()


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("[+] Connecting to %s:%s..." % (host, port))
sock.connect((host, port))
print("[+] Connected!")

your_username = None
while True:
    while True:
        your_username = raw_input("Username: ")
        if not re.match("^[a-zA-Z]+$", your_username):
            print("Invalid username. Valid is ^[a-zA-Z]+$")
        else:
            break
    sock.send("LOGIN %s %s\n" % (your_username, listenaddr[1]))
    
    response = sock.recv(2048)
    if response == "USER_ALREADY_EXISTS\n":
        print("Username in use.")
    elif response != "WELCOME\n":
        print("Unknown login error: " + response)
    else:
        break
    
while True:
    command = raw_input("> ")
    command = command.strip()
    sock.send(command + "\n")
    response = sock.recv(2048)
    if len(response) == 0: break
    print("[+] " + response)
    
sock.close()