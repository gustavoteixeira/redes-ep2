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
    
class SocketUnexpectedClosed:
    pass

class VerboseSocket:
    def __init__(self, sock, name):
        self.sock = sock
        self.name = name
        
    def send(self, arg):
        self.sock.send(arg)
        print("[>%s] %s" % (self.name, repr(arg)))
    
    def receive(self):
        data = self.sock.recv(2048)
        if len(data) == 0:
            raise SocketUnexpectedClosed()
        print("[<%s] %s" % (self.name, repr(data)))
        return data
        
    def connect(self, target):
        print("[ %s] Connecting to %s:%s" % (self.name, target[0], target[1]))
        self.sock.connect(target)
        print("[ %s] Connected!" % (self.name))
        
    def bind(self, target):
        self.sock.bind(target)
        addr = self.sock.getsockname()
        print("[ %s] Bound to %s:%s" % (self.name, addr[0], addr[1]))
        
    def close(self):
        self.sock.close()
        print("[ %s] Closed!" % (self.name))
    
    def accept(self):
        print("[ %s] Waiting for a client!" % (self.name))
        client = self.sock.accept()
        print("[ %s] A client connected! Remote is %s" % (self.name, client.getpeername()))
        return client


listensock = VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "L")
listensock.bind(("0.0.0.0", 0))
listensock.sock.listen(0)

serversock = VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "S")
serversock.connect((host, port))

class ExitMessage: pass
class ListenMessage: pass

def command_users(server, args):
    server.send("LISTUSERS\n")
    userlist = server.receive().strip().splitlines()
    print("Users:")
    for user in userlist:
        print(">> %s" % user)
        
def command_chat(server, args):
    try:
        target_user = args[0]
    except IndexError:
        print("Correct usage: 'chat USER'")
        return
    server.send("REQUESTCHAT %s\n" % target_user)
    response = server.receive()
    if response == "UNKNOWN_USER\n":
        print("User '%s' is not logged in." % target_user)
        return
    elif response == "USER_IS_BUSY\n":
        print("User '%s' is busy." % target_user)
        return
    elif response != "OK\n":
        print("Internal server error.")
        return
    else:
        raise ListenMessage()

def command_exit(server, args):
    server.send("LOGOUT\n")
    server.receive()
    raise ExitMessage()
    
commands = {
    'users': command_users,
    'chat': command_chat,
    'exit': command_exit
}

try:
    your_username = None
    while True:
        while True:
            your_username = raw_input("Username: ")
            if not re.match("^[a-zA-Z]+$", your_username):
                print("Invalid username. Valid is ^[a-zA-Z]+$")
            else:
                break
        serversock.send("LOGIN %s %s\n" % (your_username, listensock.sock.getsockname()[1]))
        
        response = serversock.receive()
        if response == "USER_ALREADY_EXISTS\n":
            print("Username in use.")
        elif response != "WELCOME\n":
            print("Unknown login error: " + response)
        else:
            print("Welcome, %s!" % your_username)
            break
    
    chat_running = True
    while chat_running:
        input = raw_input("> ").strip()
        if input == "": continue
        #if input[0] != '/':
        #    print("Cara, soh tem comandos com / agora.")
        #    continue
        command = input.split(' ')
        
        if command[0].lower() not in commands:
            print("Unknown command: %s" % command[0].lower())
            continue
        
        try:
            commands[command[0].lower()](serversock, command[1:])
        except ExitMessage:
            chat_running = False
        except ListenMessage, listen_data:
            listensock.sock.settimeout(10)
            p2psocket = listensock.accept()
            p2psocket.close()
        
    serversock.close()
    listensock.close()
except SocketUnexpectedClosed:
    print("Lost connection to server.")