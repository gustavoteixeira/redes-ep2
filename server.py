from socket import *
import socket, ssl, sys, threading

server_running = True
HEARTBEAT_INTERVAL = 20
users = {}

class ClientThread(threading.Thread):
    def __init__(self, ip, port, socket):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = socket
        self.running = True
        self.username = None
        self.buffer = []
        
    def fetch_messages(self):
        try:
            data = self.socket.recv(2048)
        except socket.timeout:
            return False
        if len(data) == 0:
            return False
        for message in filter(None, data.splitlines()):
            self.buffer.insert(0, message)
        return True
        
    def get_message(self):
        while not self.buffer:
            if not self.fetch_messages():
                return None
        return self.buffer.pop()
        
    def command_login(self, args):
        if self.username:
            self.socket.send("ALREADY_LOGGED_IN\n")
            return
            
        try_username = args.split(' ', 1)[0]
        if try_username in users:
            self.socket.send("USER_ALREADY_EXISTS\n")
            return
        
        self.username = try_username
        users[self.username] = self
        self.socket.send("WELCOME\n")

    def command_heartbeat(self, args):
        pass
        
    def command_listusers(self, args):
        for user in users:
            self.socket.send(user + "\n")
        self.socket.send("\n")
        
    def command_killserver(self, args):
        global server_running
        server_running = False
        
    def command_logout(self, args):
        self.running = False

    def run(self):
        print("[+] New thread started for %s:%s" % (self.ip, self.port))
        try:
            while self.running:
                message = self.get_message()
                if not message:
                    self.running = False
                    break
                result = message.split(' ', 1)
                command = result[0]
                arguments = ""
                if len(result) > 1: arguments = result[1]
                command = command.upper()
                if command not in ClientThread.commands:
                    self.socket.send("UNKNOWN_COMMAND\n")
                else:
                    ClientThread.commands[command](self, arguments)
        except Exception, e:
            print("[+] Thread for %s:%s crashed! Reason: %s" % (self.ip, self.port, e))
        if self.username:
            del users[self.username]
        self.socket.close()
        print("[+] Thread for %s:%s finished" % (self.ip, self.port))
    
    commands = {
        'LOGIN': command_login,
        'HEARTBEAT': command_heartbeat,
        'LISTUSERS': command_listusers,
        'KILLSERVER': command_killserver,
        'LOGOUT': command_logout
    }


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
    
serversock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversock.bind(("0.0.0.0", server_listen_port))
serversock.listen(0)
threads = []

while server_running:
    print("== WAITING FOR CLIENT! ==")
    (clientsock, (ip, port)) = serversock.accept()
    clientsock.settimeout(HEARTBEAT_INTERVAL)
    newthread = ClientThread(ip, port, clientsock)
    newthread.start()
    threads.append(newthread)

for thread in threads:
    thread.join()

serversock.close()