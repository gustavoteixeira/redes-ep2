import socket, sys

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
    
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((host, port))


sock.send("1234 \n asdf\nqwer\n\n")
sock.close()