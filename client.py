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
        
    if listen.is_chatting():
        print("You can chat with only one person each time.")
        return
        
    target_user = args[0]
    
    if target_user == your_username:
        print("You can't chat with yourself.")
        return
    
    server.send_message("QUERYUSERINFO %s" % target_user)
    response = server.get_message()
    
    # Handle ISBUSY response
    if response == "UNKNOWN_USER":
        print("User '%s' is not logged in." % target_user)
        return
        
    userdata = response.split(' ')
    try:
        userdata[1] = int(userdata[1])
    except (ValueError, IndexError):
        print("Server sent bad data.")
        return
        
    peer = Communication(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "P")
    peer.sock.settimeout(30)
    peer.connect((userdata[0], userdata[1]))
    peer.send_message("CHATREQUEST " + your_username)
    if peer.get_message() == "OK":
        listen.set_chatting(target_user, peer)
        print("User '%s' accepted your chat request." % target_user)
        return
        
    if peer.get_message() == "BUSY":
        print("User '%s' is busy." % target_user)
    else:
        print("User '%s' refused your chat request." % target_user)
    peer.close()

def command_accept(server, args):
    target_user = args[0]
    if target_user not in listen.pending:
        print("User '%s' has not requested a chat with you. Use 'chat %s' instead." % (target_user, target_user))
        return
        
    socket = listen.pending[target_user]
    socket.send_message("OK")
    
    print("You are now chatting with '%s'!" % target_user)
    listen.set_chatting(target_user, socket)
    del listen.pending[target_user]
    
def command_refuse(server, args):
    target_user = args[0]
    if target_user not in listen.pending:
        print("No chat request from '%s' found." % (target_user))
        return
        
    socket = listen.pending[target_user]
    socket.send_message("REFUSED")
    socket.close()
    del listen.pending[target_user]
    print("Chat request from '%s' refused." % target_user)
    
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
    'refuse': command_refuse,
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
        
    def set_chatting(self, username, socket):
        self.chatting = (username, socket)
        socket.print_func = print_threaded
        
    def handle_newrequest(self, socket):
        request = socket.get_message().split(' ')
        if len(request) == 2 and request[0] == "CHATREQUEST":
            if self.chatting: #single chat only
                socket.send_message("BUSY")
                return
        
            username = request[1]
            self.pending[username] = socket
            print_threaded("You received a chat request from '{0}'. You may 'accept {0}' or 'refuse {0}'.".format(username))
        else:
            # invalid request
            socket.close()
        
    def is_chatting(self):
        return self.chatting
        
    def run(self):
        while chat_running:
            check = [self.socket]
            if self.chatting: check.append(self.chatting[1])
            ready = select.select(check, [], [], 1)[0]
            
            if self.socket in ready:
                self.handle_newrequest(Communication(self.socket.accept()[0], 'P'))
                
            if self.chatting and self.chatting[1] in ready:
                print_threaded(self.chatting[0] + ": " + self.chatting[1].get_message())
            
        self.socket.close()
        if self.chatting:
            self.chatting[1].close()

try:
    serversock = Communication(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "S")
    serversock.connect((host, port))

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
        
        commands[command[0].lower()](serversock, command[1:])
        
    serversock.close()
    
except common.SocketUnexpectedClosed:
    chat_running = False
    print("Lost connection to server.")
except Exception, err:
    chat_running = False
    import traceback
    print(traceback.format_exc())
    