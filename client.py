from __future__ import print_function
import socket, sys, re, select, readline, thread

import common, args

(host, port, tcp) = args.parse_client()
        
if not tcp:
    raise Exception("UDP NYI")

CHAT_PROMPT = "> "
RUNNING_RAWINPUT = False
    
def print_threaded(message):
    if not RUNNING_RAWINPUT:
        print(message)
        return
    sys.stdout.write('\r'+' '*(len(readline.get_line_buffer())+2)+'\r')
    print(message)
    sys.stdout.write(CHAT_PROMPT + readline.get_line_buffer())
    sys.stdout.flush()

def raw_input_wrapper(prompt):
    global RUNNING_RAWINPUT
    RUNNING_RAWINPUT = True
    resp = raw_input(prompt)
    RUNNING_RAWINPUT = False
    return resp

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

def command_exit(server, args):
    server.send("LOGOUT\n")
    server.get_message()
    raise ExitMessage()
    
commands = {
    'users': command_users,
    'chat': command_chat,
    'exit': command_exit
}

def notification_chatrequest(server, args):
    target_user = args[0]
    print_threaded("You received a chat request from '%s'. If you accept, run 'accept %s'." % (target_user, target_user))
    return

    
    accept = False
    while True:
        resp = raw_input("Chat request from '%s', accept? (y/n) " % target_user).lower()
        if resp == 'y' or resp == 'n':
            accept = (resp == 'y')
            break
    if not accept:
        # Modo FDP, ignorar simplismente.
        return
    
    serversock.send("QUERYUSERINFO %s\n" % target_user)
    (target_ip, target_port) = serversock.receive().strip().split(' ')
    p2psock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "P")
    p2psock.connect((target_ip, int(target_port)))
    p2psock.send("nope.avi\n")
    p2psock.close()

notification_handlers = {
    'CHATREQUEST': notification_chatrequest
}

def notification_handler():
    while True:
        notification = serversock.get_notification()
        if not notification:
            continue
        
        notification = notification.split(' ')
        if notification[0].upper() != "NOTIFICATION":
            print_threaded("Unexpected message from server: %s" % repr(notification))
        elif notification[1].upper() not in notification_handlers:
            print_threaded("Unknown notification: %s" % repr(notification[1]))
        else:
            notification_handlers[notification[1].upper()](serversock, notification[2:])

try:
    your_username = None
    
    # Login Process
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
    notification_thread = thread.start_new_thread(notification_handler, ())
    while chat_running:
        input = raw_input_wrapper(CHAT_PROMPT).strip()
        
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
            try:
                listensock.sock.settimeout(10)
                p2psocket = common.VerboseSocket(listensock.accept()[0], "P")
                print(p2psocket.receive())
                p2psocket.close()
            except socket.timeout:
                print("Chat request refused.")
        
    serversock.close()
    listensock.close()
except common.SocketUnexpectedClosed:
    print("Lost connection to server.")