from __future__ import print_function
import socket, sys, re, select, readline, threading, time, os
import common, client_common

# Globals
configuration = None
UDP_TIMEOUT = 30

chat_running = True
listen = None
commands = {}
your_username = None
server_address = None
server_handler = None
address_name = {}

print_threaded = client_common.print_threaded
raw_input_wrapper = client_common.raw_input_wrapper
read_validusername = client_common.read_validusername

#
def fetch_name(address):
    return address_name[address] if (address in address_name) else "Unknown"
    
def add_name(address, data):
    if data != "UNKNOWN_USER":
        address_name[address] = data
      
# COMMANDS
def command_say(master, args):
    if master.is_chatting():
       master.queue_write("SAY %s\n" % (" ".join(args)), master.chatting[1])
    else:
        print("You're not chatting with anyone.")

def command_users(master, args):
    def users_print(data):
        userlist = data.strip().split(' ')
        print_threaded("Users:")
        for user in userlist:
            print_threaded(">> %s" % user)

    master.add_handler(users_print)
    master.queue_write("LISTUSERS\n", server_address)

def command_chat(master, args):
    if len(args) != 1:
        print("Correct usage: 'chat USER'")
        return
        
    if master.is_chatting():
        print("You can chat with only one person each time.")
        return
        
    target_user = args[0]
    
    if target_user == your_username:
        print("You can't chat with yourself.")
        return
        
    def info_handler(data):
        response = data.strip()
        if response == "UNKNOWN_USER":
            print_threaded("User '%s' is not logged in." % target_user)
            return
            
        userdata = response.split(' ')
        try:
            userdata[1] = int(userdata[1])
        except (ValueError, IndexError):
            print_threaded("Server sent bad data.")
            return
        userdata = (userdata[0], userdata[1])
        add_name(userdata, target_user)
        master.queue_write("CHATREQUEST " + your_username + "\n", userdata)
        print_threaded("Sending chat request to '%s'." % target_user)
        
    master.add_handler(info_handler)
    master.queue_write("QUERYUSERINFO %s\n" % target_user, server_address)

def command_accept(master, args):
    if master.transfer:
        if len(args) != 1:
            print("Usage: /accept local_filename")
            return
        filename = args[0]
        try:
            open_file = open(filename, "wb")
        except IOError:
            print("Cannot open file '%s' for writing." % filename)
    
        transfer = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), "F")
        transfer.connect(master.transfer[1])
        master.queue_write("TRANSFEROK %s\n" % transfer.sock.getsockname()[1], master.chatting[1])
        transfer.sock.settimeout(30)
        
        print("Writing file from %s to %s..." % (master.chatting[1], filename))
        try:
            bytes_received = 0
            while bytes_received < master.transfer[0]:
                bytes = transfer.sock.recv(min(2048, master.transfer[0] - bytes_received))
                open_file.write(bytes)
                bytes_received += len(bytes)
                print("%s% done", 100 * (bytes_received/master.transfer[0]))
            transfer.close()
        except socket.timeout:
            print("Conection failure.")
        open_file.close()
        
    else:
        target_user = args[0]
        if target_user not in master.pending_chats:
            print("User '%s' has not requested a chat with you. Use 'chat %s' instead." % (target_user, target_user))
            return
            
        master.queue_write("CHATOK\n", master.pending_chats[target_user])
        master.set_chatting(target_user, master.pending_chats[target_user])
        del master.pending_chats[target_user]
        print("You are now chatting with '%s'!" % target_user)
    
def command_refuse(master, args):
    if master.transfer:
        master.queue_write("TRANSFERREFUSED\n", master.transfer[1])
        master.transfer = None
        print("File request refused.")
    else:
        target_user = args[0]
        if target_user not in master.pending_chats:
            print("No chat request from '%s' found." % (target_user))
            return
            
        master.queue_write("CHATREFUSED\n", master.pending_chats[target_user])
        del master.pending_chats[target_user]
        print("Chat request from '%s' refused." % target_user)

def command_close(master, args):
    if master.is_chatting():
        master.stop_chatting()
    else:
        print("You're not chatting with anyone.")

def command_sendfile(master, args):
    if not master.is_chatting():
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
    
    transfer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    transfer.bind(("0.0.0.0", 0))
    new_listen = transfer.getsockname()[1]
    
    master.transfer = [open_file, transfer, True] # file_object, socket, 'I'm the one sending'
    
    master.queue_write("SENDFILE %s %s %s\n" % (target_file, size, new_listen), master.chatting[1])
        
def command_help(master, args):
    print("The following commands are avaiable: " + reduce(lambda a, b: a + ", " + b, commands))
    
def command_exit(master, args):
    if master.is_chatting():
        master.stop_chatting()
    master.add_handler(lambda data: data == "BYE\n")
    master.queue_write("LOGOUT\n", server_address)
    global chat_running
    chat_running = False
    
commands = {
    'say': command_say,
    'users': command_users,
    'chat': command_chat,
    'accept': command_accept,
    'refuse': command_refuse,
    'close': command_close,
    'sendfile': command_sendfile,
    'help': command_help,
    'exit': command_exit
}

class SocketMaster(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = socket
        
        self.server_handler = []
        self.expect = {}
        self.pending_write = []
        self.pending_chats = {}
        self.chatting = None
        self.transfer = None

           
    def is_chatting(self):
        return self.chatting
        
    def add_handler(self, handler):
        self.server_handler.insert(0, handler)
        
    def queue_write(self, message, address):
        self.pending_write.insert(0, (message, address))
        
    def stop_chatting(self, forced = False):
        if not self.chatting: return
        
        client_common.CHAT_PROMPT = "> "
        
        if not forced:
            self.queue_write("CLOSE\n", self.chatting[1])
            print_threaded("You finished your chat with '%s'." % self.chatting[0])
        else:
            print_threaded("Your chat with '%s' was closed by the remote host." % self.chatting[0])
        
        self.chatting = None
        
    def set_chatting(self, username, address):
        self.chatting = (username, address)
        client_common.CHAT_PROMPT = your_username + ": "
    
    def handle_input(self):
        (data, address) = self.socket.recvfrom()
        if address == server_address:
            if not self.server_handler:
                print_threaded("Unexpected server message.")
            else:
                self.server_handler.pop()(data)
            return
            
        # All other addresses
        commands = data.strip().split(' ')
        if commands[0] == "CHATOK":
            self.set_chatting(fetch_name(address), address)
            print_threaded("%s accepted your chat request." % fetch_name(address))
            
        elif commands[0] == "BUSY":
            print_threaded("%s is busy." % fetch_name(address))
            
        elif commands[0] == "CHATREFUSED":
            print_threaded("%s refused your chat request." % fetch_name(address))
            
        elif commands[0] == "SAY":
            print_threaded("%s: %s" % (fetch_name(address), ' '.join(commands[1:])))
            
        elif commands[0] == "CLOSE":
            self.stop_chatting(True)
            
        elif commands[0] == "CHATREQUEST":
            if len(commands) != 2: return
            
            other_username = commands[1]
            if not other_username: return
            
            if self.is_chatting():
                self.queue_write("BUSY\n", address)
            else:
                add_name(address, other_username)
                print_threaded("%s requested a chat with you." % other_username)
                self.pending_chats[other_username] = address
                
        elif commands[0] == "SENDFILE":
            print_threaded(repr(commands))
            if len(commands) != 4: return
            (filename, size, new_listen) = commands[1:]
            
            try:
                self.transfer = [int(size), (address[0], int(new_listen)), False] # False means "I'm not sending"
            except ValueError as e:
                return
            print_threaded("%s requested to send a file '%s' with size %s to you." % (fetch_name(address), filename, size))
            print_threaded("Accept it with /accept local_filename or /refuse.")
            
        elif commands[0] == "TRANSFEROK":
            print_threaded("received TRANSFEROK -- " + repr(self.transfer))
            if not self.transfer or not self.transfer[2]: return
            try:
                self.transfer.append(int(commands[1]))
            except (ValueError, IndexError) as e:
                print_threaded("problem getting the port" + str(e))
                return
            
        elif commands[0] == "TRANSFERREFUSED":
            if not self.transfer: return
            print_threaded("%s refused your file transfer." % (fetch_name(address)))
            self.transfer[0].close()
            self.transfer[1].close()
            self.transfer = None
            
        else:
            print_threaded("Unexpected message '%s' from '%s'\n" % (repr(data), repr(address)))
    
    def run(self):
        last_beat = time.time()
        while True:
            (readcheck, writecheck, _) = select.select([self.socket], [self.socket], [], configuration.heartbeat / 10)
            
            if not (chat_running or self.pending_write):
                break
            
            if time.time() - last_beat > configuration.heartbeat:
                self.queue_write("HEARTBEAT\n", server_address)
                self.add_handler(lambda data: data == "OK\n")
                last_beat = time.time()
            
            if self.socket in readcheck:
                self.handle_input()
                
            if self.socket in writecheck:
                while self.pending_write:
                    write = self.pending_write.pop()
                    self.socket.sendto(write[0], write[1])

def run(config):
    global configuration, chat_running, listen, your_username, server_address
    configuration = config
    UDP_TIMEOUT = configuration.heartbeat / 2
    server_address = (socket.gethostbyname(configuration.host), configuration.port)
    try:
        mainsock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), "M")
        mainsock.print_func = print_threaded if configuration.verbosity >= 1 else common.null_print
        mainsock.bind(("0.0.0.0", 0))
        mainsock.sock.settimeout(UDP_TIMEOUT)
        
        # Keep the socket exclusive while we login
        while True:
            your_username = read_validusername() if not config.username else config.username
            mainsock.sendto("LOGIN %s %s\n" % (your_username, mainsock.sock.getsockname()[1]), server_address)
            
            (response, address) = mainsock.recvfrom()
            if address != server_address:
                print("Message not sent by server...")
            elif response == "USER_ALREADY_EXISTS\n":
                print("Username in use.")
            elif response != "WELCOME\n":
                print("Unknown login error: " + response)
            else:
                print("Welcome, %s!" % your_username)
                break
            if not config.username:
                return
             
        # Ok, send it to a thread and don't consider it ours anymore
        sockmaster = SocketMaster(mainsock)
        sockmaster.start()
        del mainsock # don't even keep the old reference
        
        while chat_running:
            if sockmaster.transfer and sockmaster.transfer[2]:
                for i in range(30):
                    if len(sockmaster.transfer) < 4:
                        time.sleep(1)
                if len(sockmaster.transfer) < 4:
                    print("Aborting file transfer...")
                    sockmaster.transfer = None
                else:
                    sockmaster.transfer[1].connect((sockmaster.chatting[1][0], sockmaster.transfer[3]))
                    print("Starting file transfer...")
                    while True:
                        data = sockmaster.transfer[0].read(2048)
                        if len(data) == 0: break
                        sockmaster.transfer[1].send(data)
                    print("File transfer complete.")
                    sockmaster.transfer[1].close()
                    sockmaster.transfer = None
        
            client_common.input_handler(sockmaster.is_chatting, commands, sockmaster)
            
        print("Bye.")
        
    except common.SocketUnexpectedClosed:
        chat_running = False
        print("Lost connection to server.")
    except Exception, err:
        chat_running = False
        import traceback
        print(traceback.format_exc())
        