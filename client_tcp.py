from __future__ import print_function
import socket, ssl, sys, re, select, readline, threading, time, os, datetime
import common, client_common

# Globals
configuration = None

chat_running = True
listen = None
commands = {}
your_username = None

print_threaded = client_common.print_threaded
raw_input_wrapper = client_common.raw_input_wrapper
read_validusername = client_common.read_validusername
    
# COMMANDS
def command_say(server, args):
    if listen.is_chatting():
       listen.chatting[1].send("SAY %s\n" % (" ".join(args)))
    else:
        print("You're not chatting with anyone.")

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
        
    peer = common.Communication(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "P")
    peer.print_func = print_threaded if configuration.verbosity >= 2 else common.null_print
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
    if listen.transfer:
        if len(args) != 1:
            print("Usage: /accept local_filename")
            return
        filename = args[0]
        try:
            open_file = open(filename, "wb")
        except IOError:
            print("Cannot open file '%s' for writing." % filename)
    
        transfer = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "F")
        transfer.connect(listen.transfer[1])
        listen.chatting[1].send_message("TRANSFEROK %s\n" % transfer.sock.getsockname()[1])
        transfer.sock.settimeout(30)
        
        print("Writing file from %s to %s..." % (listen.chatting[0], filename))
        start = datetime.datetime.now()
        try:
            bytes_received = 0
            while bytes_received < listen.transfer[0]:
                bytes = transfer.sock.recv(min(2048, listen.transfer[0] - bytes_received))
                if len(bytes) == 0:
                    raise "DEU MERDA"
                open_file.write(bytes)
                bytes_received += len(bytes)
                print("%s% done", 100 * (bytes_received/listen.transfer[0]))
            transfer.close()
        except (socket.timeout, string) as x:
            print("Conection failure: " + repr(x))
        diff = datetime.datetime.now() - start
        print("Finished received file in " + str(diff))
        open_file.close()
    else:
        target_user = args[0]
        if target_user not in listen.pending:
            print("User '%s' has not requested a chat with you. Use 'chat %s' instead." % (target_user, target_user))
            return
            
        sock = listen.pending[target_user]
        sock.send_message("OK")
        
        print("You are now chatting with '%s'!" % target_user)
        listen.set_chatting(target_user, sock)
        del listen.pending[target_user]
    
def command_refuse(server, args):
    if listen.transfer:
        listen.chatting[1].send_message("TRANSFERREFUSED\n")
        listen.transfer = None
        print("File request refused.")
    else:
        target_user = args[0]
        if target_user not in listen.pending:
            print("No chat request from '%s' found." % (target_user))
            return
            
        socket = listen.pending[target_user]
        socket.send_message("REFUSED")
        socket.close()
        del listen.pending[target_user]
        print("Chat request from '%s' refused." % target_user)
    
def command_sendfile(server, args):
    if not listen.is_chatting():
        print("You're not chatting with anyone.")
        return
        
    if len(args) != 1:
        print("Usage: /sendfile filename")
        return
    
    target_file = args[0]
    try:
        open_file = open(target_file, "rb")
    except IOError:
        print("Couldn't open file '%s'" % target_file)
        return
    
    size = os.fstat(open_file.fileno()).st_size
    
    transfer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    transfer.bind(("0.0.0.0", 0))
    new_listen = transfer.getsockname()[1]
    
    listen.transfer = [open_file, transfer, True] # file_object, socket, 'I'm the one sending'
    
    listen.chatting[1].send_message("SENDFILE %s %s %s\n" % (target_file, size, new_listen))
    
def command_close(server, args):
    if listen.is_chatting():
        listen.stop_chatting()
    else:
        print("You're not chatting with anyone.")
    
def command_help(server, args):
    print("The following commands are avaiable: " + reduce(lambda a, b: a + ", " + b, commands))
    
def command_exit(server, args):
    server.send("LOGOUT\n")
    server.get_message()
    global chat_running
    chat_running = False
    
commands = {
    'say': command_say,
    'users': command_users,
    'chat': command_chat,
    'accept': command_accept,
    'refuse': command_refuse,
    'sendfile' : command_sendfile,
    'close': command_close,
    'help': command_help,
    'exit': command_exit
}

class ClientListener(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = common.VerboseSocket(socket, "L")
        self.socket.print_func = print_threaded if configuration.verbosity >= 1 else common.null_print
        self.socket.bind(("0.0.0.0", 0))
        self.socket.listen(2)
        self.chatting = None
        self.pending = {}
        self.transfer = None
        
    def get_port(self):
        return self.socket.sock.getsockname()[1]
        
    def stop_chatting(self, forced = False):
        if not self.chatting: return
        
        client_common.CHAT_PROMPT = "> "
        
        if not forced:
            self.chatting[1].send_message("CLOSE")
            print_threaded("You finished your chat with '%s'." % self.chatting[0])
        else:
            print_threaded("Your chat with '%s' was closed by the remote host." % self.chatting[0])
        
        self.chatting[1].close()
        self.chatting = None
        
    def set_chatting(self, username, socket):
        self.chatting = (username, socket)
        client_common.CHAT_PROMPT = your_username + ": "
        
    def handle_newrequest(self, socket):
        socket.print_func = print_threaded if configuration.verbosity >= 2 else common.null_print
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
                self.handle_newrequest(common.Communication(self.socket.accept()[0], 'P'))
                
            if self.chatting and self.chatting[1] in ready:
                try:
                    message = self.chatting[1].get_message().split(' ')
                    if message[0] == 'SAY':
                        if len(message) == 2:
                            print_threaded(self.chatting[0] + ": " + message[1])
                    elif message[0] == 'CLOSE':
                        self.stop_chatting(True)
                        
                    elif message[0] == "SENDFILE":
                        if len(message) != 4: return
                        (filename, size, new_listen) = message[1:]
                        
                        try:
                            self.transfer = [int(size), (self.chatting[1].getpeername()[0], int(new_listen)), False] # False means "I'm not sending"
                        except ValueError as e:
                            return
                        print_threaded("%s requested to send a file '%s' with size %s to you." % (self.chatting[0], filename, size))
                        print_threaded("Accept it with /accept local_filename or /refuse.")
                        
                    elif message[0] == "TRANSFEROK":
                        print_threaded("received TRANSFEROK -- " + repr(self.transfer))
                        if not self.transfer or not self.transfer[2]: return
                        try:
                            self.transfer.append(int(message[1]))
                        except (ValueError, IndexError) as e:
                            print_threaded("problem getting the port" + str(e))
                            return
                        
                    elif message[0] == "TRANSFERREFUSED":
                        if not self.transfer: return
                        print_threaded("%s refused your file transfer." % (self.chatting[0]))
                        self.transfer[0].close() # file
                        self.transfer[1].close() # socket
                        self.transfer = None
                        
                    
                except common.SocketUnexpectedClosed:
                    self.stop_chatting(True)
            
        self.socket.close()
        if self.chatting:
            self.chatting[1].close()

def run(config):
    global configuration, chat_running, listen, your_username
    configuration = config
    try:

        serversock = ssl.wrap_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))

        serversock = common.Communication(serversock, "S")
        serversock.print_func = print_threaded if configuration.verbosity >= 1 else common.null_print
        serversock.connect((configuration.host, configuration.port))

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
            if listen.transfer and listen.transfer[2]:
                listen.transfer[1].settimeout(30)
                listen.transfer[1].listen(1)
                try:
                    file_transfer = listen.transfer[1].accept()[0]
                except socket.timeout:
                    print("Aborting file transfer...")
                    listen.transfer = None
                    continue
                    
                print("Starting file transfer...")
                file_transfer.settimeout(None)
                while True:
                    stuff = select.select([], [file_transfer], [], 10)
                    if file_transfer not in stuff[1]: continue
                    data = listen.transfer[0].read(2048)
                    if len(data) == 0: break
                    file_transfer.send(data)
                print("File transfer complete.")
                listen.transfer[1].close()
                file_transfer.close()
                listen.transfer = None
            client_common.input_handler(listen.is_chatting, commands, serversock)
            
        print("Bye.")
        serversock.close()
        
    except common.SocketUnexpectedClosed:
        chat_running = False
        print("Lost connection to server.")
    except Exception, err:
        chat_running = False
        import traceback
        print(traceback.format_exc())
        
