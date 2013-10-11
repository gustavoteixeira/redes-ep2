from __future__ import print_function
import socket, sys, re, select, readline, threading

import common, args

(host, port, tcp) = args.parse_client()
if not tcp:
    raise Exception("UDP NYI")

CHAT_PROMPT = "> "

# Globals
chat_running = True
rawinput_running = False
listen = None
serversock = None
commands = {}
your_username = None
    
def print_threaded(message):
    if not rawinput_running:
        print(message)
        return
    sys.stdout.write('\r'+' '*(len(readline.get_line_buffer())+2)+'\r')
    print(message)
    sys.stdout.write(CHAT_PROMPT + readline.get_line_buffer())
    sys.stdout.flush()

def raw_input_wrapper(prompt):
    global rawinput_running
    rawinput_running = True
    resp = raw_input(prompt)
    rawinput_running = False
    return resp

def read_validusername():
    while True:
        username = raw_input("Username: ")
        if re.match("^[a-zA-Z]+$", username):
            return username
        print("Invalid username. Valid is ^[a-zA-Z]+$")
    
class Communication(common.VerboseSocket):
    def __init__(self, socket, name):
        common.VerboseSocket.__init__(self, socket, name)
        self.messages = []
    
    def read_socket(self):
        for line in self.receive().splitlines():
            self.messages.insert(0, line)
                
    def peek_socket(self):
        (readvalid, _, _) = select.select([self], [], [], 0.01)
        if self in readvalid:
            self.read_socket()
    
    def get_message(self):
        while not self.messages:
            self.read_socket()
        return self.messages.pop()
        
    def send_message(self, message):
        self.send(message + "\n")
    
serversock = Communication(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "S")
serversock.connect((host, port))

class ExitMessage: pass
class StartChatMessage:
    def __init__(self, target_user):
        self.target_user = target_user

def command_users(server, args):
    server.send("LISTUSERS\n")
    userlist = server.get_message().split(' ')
    print("Users:")
    for user in userlist:
        print(">> %s" % user)
        
def command_chat(server, args):
    if len(args) != 1:
        print("Correct usage: 'chat USER'")
        return
    target_user = args[0]
    server.send_message("ISBUSY %s" % target_user)
    response = server.get_message()
    if response == "UNKNOWN_USER":
        print("User '%s' is not logged in." % target_user)
        return
    elif response == "IS_BUSY":
        print("User '%s' is busy." % target_user)
        return
    elif response != "IS_FREE":
        print("Internal server error.")
        return
    else:
        raise StartChatMessage(target_user)

def command_accept(server, args):
    target_user = args[0]
    if target_user not in listen.pending:
        print("User '%s' has not requested a chat with you. Use 'chat %s' instead." % (target_user, target_user))
        return
        
    socket = listen.pending[target_user]
    socket.send_message("OK")
    
    print("You are now chatting with '%s'!" % target_user)
    listen.chatting = (target_user, socket)
    del listen.pending[target_user]
    
def command_help(server, args):
    print("The following commands are avaiable: " + reduce(lambda a, b: a + ", " + b, commands))
    
def command_exit(server, args):
    server.send("LOGOUT\n")
    server.get_message()
    global chat_running
    chat_running = False
    
commands = {
    'users': command_users,
    'chat': command_chat,
    'accept': command_accept,
    'help': command_help,
    'exit': command_exit
}

class ClientListener(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = common.VerboseSocket(socket, "L")
        self.socket.bind(("0.0.0.0", 0))
        self.socket.listen(2)
        self.chatting = None
        self.pending = {}
        
    def get_port(self):
        return self.socket.sock.getsockname()[1]
        
    def handle_newrequest(self, socket):
        request = socket.get_message().split(' ')
        if len(request) == 2 and request[0] == "CHATREQUEST":
            username = request[1]
            self.pending[username] = socket
            print_threaded("You received a chat request from '%s'. If you accept, run 'accept %s'." % (username, username))
            return
        else:
            # invalid request
            socket.close()
        
    def is_chatting(self):
        return self.chatting
        
    def run(self):
        while chat_running:
            ready = select.select([self.socket], [], [], 1)[0]
            if self.socket in ready:
                continue
            self.handle_newrequest(Communication(self.socket.accept()[0], 'P'))
        self.socket.close()

try:
    listen = ClientListener(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    listen.start()
    
    # Login Process
    while True:
        your_username = read_validusername()
        serversock.send("LOGIN %s %s\n" % (your_username, listen.get_port()))
        
        response = serversock.receive()
        if response == "USER_ALREADY_EXISTS\n":
            print("Username in use.")
        elif response != "WELCOME\n":
            print("Unknown login error: " + response)
        else:
            print("Welcome, %s!" % your_username)
            break
    
    while chat_running:
        input = raw_input_wrapper(CHAT_PROMPT).strip()
        if input == "": continue
        
        if listen.is_chatting() and input[0] != '/':
            listen.chatting[1].send("SAY %s\n" % input)
            continue
        
        if listen.is_chatting(): input = input[1:]
        command = input.split(' ')
        if command[0].lower() not in commands:
            print("Unknown command: %s" % command[0].lower())
            continue
        
        try:
            commands[command[0].lower()](serversock, command[1:])
        except StartChatMessage, chat_data:
            if listen.is_chatting():
                print("You can chat with only one person each time.")
                continue
            if chat_data.target_user == your_username:
                print("You can't chat with yourself.")
                continue
            
            serversock.send_message("QUERYUSERINFO %s" % chat_data.target_user)
            peerdata = serversock.get_message().split(' ')
            peerdata[1] = int(peerdata[1])
            
            peer = Communication(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "P")
            peer.sock.settimeout(30)
            peer.connect((peerdata[0], peerdata[1]))
            peer.send_message("CHATREQUEST " + your_username)
            if peer.get_message() == "OK":
                listen.chatting = (chat_data.target_user, peer)
                print("User '%s' accepted your chat request" % chat_data.target_user)
            else:
                print("User '%s' refused your chat request" % chat_data.target_user)
                peer.close()
        
    serversock.close()
    
except common.SocketUnexpectedClosed:
    chat_running = False
    print("Lost connection to server.")
except Exeception, err:
    chat_running = False
    print("Unexpected python exception: " + err)
    