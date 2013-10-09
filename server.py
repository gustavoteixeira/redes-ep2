from socket import *
import socket, ssl, sys, threading

class ClientThread(threading.Thread):

    def __init__(self, ip, port, socket):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = socket
        self.running = True
        self.buffer = []
        
    def fetch_commands(self):
        try:
            data = self.socket.recv(2048)
        except socket.timeout:
            return False
        if len(data) == 0:
            return False
        for command in filter(None, data.splitlines()):
            self.buffer.insert(0, command)
        return True
        
    def get_command(self):
        while not self.buffer:
            if not self.fetch_commands():
                return None
        return self.buffer.pop()
        

    def run(self):
        print("[+] New thread started for %s:%s" % (self.ip, self.port))
        while self.running:
            command = self.get_command()
            if not command:
                self.running = False
                break
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
                self.running = False
            else: # command == "HEARTBEAT"
                pass
        self.socket.close()
        print("[+] Thread for %s:%s finished" % (self.ip, self.port))


server_listen_port = int(sys.argv[1])
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
    
serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversock.bind(("0.0.0.0", server_listen_port))
serversock.listen(0)
threads = []

while True:
    print("== WAITING FOR CLIENT! ==")
    (clientsock, (ip, port)) = serversock.accept()
    clientsock.settimeout(HEARTBEAT_INTERVAL)
    newthread = ClientThread(ip, port, clientsock)
    newthread.start()
    threads.append(newthread)

for thread in threads:
    thread.join()

serversock.close()