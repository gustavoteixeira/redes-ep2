from socket import *
import socket, ssl, sys, threading

class ClientThread(threading.Thread):

    def __init__(self, ip, port, socket):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = socket
        print "[+] New thread started for "+str(ip)+":"+str(port)+"\n"

    def run(self):
        try:
            data = self.socket.recv(2048)
        except socket.timeout:
            return
        if len(data) == 0:
            return
        for command in filter(None, data.splitlines()):
            if command.split(' ', 1)[0].upper() == 'LOGIN':
                try_username = command.split(' ', 1)[1]
                if try_username in users:
                    self.socket.send("USER_ALREADY_EXISTS\n")
                else:
                    username = try_username
                    users[username] = True
                    self.socket.send("WELCOME\n")
                # STUFF TO DO ON LOGIN
            elif command.upper() == "LOGOUT":
                client_running = False
                self.socket.close()
                return
            else: # command == "HEARTBEAT"
                pass


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
threads = []

while 1:#for _ in range(2): # por enquanto, para poder matar
    print("== WAITING FOR CLIENT! ==")
    (clientsock, (ip, port)) = sock.accept()
    clientsock.settimeout(HEARTBEAT_INTERVAL)
    newthread = ClientThread(ip, port, clientsock)
    newthread.start()
    threads.append(newthread)
    
    username = None
    client_running = True
    
    '''while client_running:
        
    if username:
        del users[username]
    new_client.close()'''

for thread in threads:
    thread.join()

sock.close()