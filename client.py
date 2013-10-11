from __future__ import print_function
import socket, sys, re, select, readline, thread

import common, args

(host, port, tcp) = args.parse_client()
if not tcp:
    raise Exception("UDP NYI")

CHAT_PROMPT = "> "

# Globals
chat_running = True
rawinput_running = False
listensock = None
serversock = None
commands = {}
pending_chatrequests = {}
chatting = None
    
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
    
class ServerCommunication(common.VerboseSocket):
    def __init__(self, socket):
        common.VerboseSocket.__init__(self, socket, "S")
        self.messages = []
        self.notifications = []
    
    def read_socket(self):
        for line in self.receive().splitlines():
            if line.split(' ', 1)[0].upper() == 'NOTIFICATION':
                self.notifications.insert(0, line.split(' ', 1)[1])
            else:
                self.messages.insert(0, line)
                
    def peek_socket(self):
        (readvalid, _, _) = select.select([self], [], [], 0.01)
        if self in readvalid:
            self.read_socket()
    
    def get_message(self):
        while not self.messages:
            self.read_socket()
        return self.messages.pop()
        
    def get_notification(self):
        self.peek_socket()
        if self.notifications:
            return self.notifications.pop()
        return None
    
listensock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "L")
listensock.bind(("0.0.0.0", 0))
listensock.listen(0)

serversock = ServerCommunication(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
serversock.connect((host, port))

class ExitMessage: pass
class ListenMessage: pass

def command_users(server, args):
    server.send("LISTUSERS\n")
    userlist = server.get_message().split(' ')
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
    response = server.get_message()
    if response == "UNKNOWN_USER":
        print("User '%s' is not logged in." % target_user)
        return
    elif response == "USER_IS_BUSY":
        print("User '%s' is busy." % target_user)
        return
    elif response != "OK":
        print("Internal server error.")
        return
    else:
        raise ListenMessage()

def command_accept(server, args):
    target_user = args[0]
    if target_user not in pending_chatrequests:
        print("User '%s' has not requested a chat with you. Use 'chat %s' instead." % (target_user, target_user))
        return
        
    serversock.send("QUERYUSERINFO %s\n" % target_user)
    (target_ip, target_port) = serversock.get_message().split(' ')
    
    global chatting
    chatting = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "P")
    chatting.connect((target_ip, int(target_port)))
    chatting.send("nope.avi\n")
    print("You are now chatting with '%s'!" % target_user)
    
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

def notification_chatrequest(server, args):
    target_user = args[0]
    print_threaded("You received a chat request from '%s'. If you accept, run 'accept %s'." % (target_user, target_user))
    pending_chatrequests[target_user] = True

notification_handlers = {
    'CHATREQUEST': notification_chatrequest
}

def notification_handler():
    while chat_running:
        notification = serversock.get_notification()
        if not notification:
            continue
        
        notification = notification.split(' ')
        if notification[0].upper() not in notification_handlers:
            print_threaded("Unknown notification: %s" % repr(notification[1]))
        else:
            notification_handlers[notification[0].upper()](serversock, notification[1:])

try:
    your_username = None
    
    # Login Process
    while True:
        your_username = read_validusername()
        serversock.send("LOGIN %s %s\n" % (your_username, listensock.sock.getsockname()[1]))
        
        response = serversock.receive()
        if response == "USER_ALREADY_EXISTS\n":
            print("Username in use.")
        elif response != "WELCOME\n":
            print("Unknown login error: " + response)
        else:
            print("Welcome, %s!" % your_username)
            break
    
    notification_thread = thread.start_new_thread(notification_handler, ())
    while chat_running:
        input = raw_input_wrapper(CHAT_PROMPT).strip()
        if input == "": continue
        
        if chatting and input[0] != '/':
            chatting.send("SAY %s\n" % input)
        else:
            if chatting: input = input[1:]
            command = input.split(' ')
            if command[0].lower() not in commands:
                print("Unknown command: %s" % command[0].lower())
                continue
            
            try:
                commands[command[0].lower()](serversock, command[1:])
            except ListenMessage, listen_data:
                try:
                    listensock.sock.settimeout(10)
                    chatting = common.VerboseSocket(listensock.accept()[0], "P")
                except socket.timeout:
                    print("Chat request refused.")
        
    serversock.close()
    listensock.close()
except common.SocketUnexpectedClosed:
    print("Lost connection to server.")