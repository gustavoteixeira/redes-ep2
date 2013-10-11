from __future__ import print_function
import socket, sys, re, select, readline, threading
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

print_threaded = client_common.print_threaded
raw_input_wrapper = client_common.raw_input_wrapper
read_validusername = client_common.read_validusername

class ServerMessageHandler:
    def __init__(self):
        self.handlers = []
        
    def __call__(self, data):
        if not self.handlers:
            print_threaded("Unexpected ServerMessageHandler call.")
        else:
            self.handlers.pop()(data)
    
    def add_handler(self, handler):
        self.handlers.insert(0, handler)
    
# COMMANDS
def command_say(master, args):
    pass

def command_users(master, args):
    def users_print(data):
        userlist = data.strip().split(' ')
        print_threaded("Users:")
        for user in userlist:
            print_threaded(">> %s" % user)

    master.queue_write("LISTUSERS\n", server_address)
    server_handler.add_handler(users_print)

def command_chat(master, args):
    pass

def command_accept(master, args):
    pass
    
def command_refuse(master, args):
    pass

def command_close(master, args):
    pass
    
def command_help(master, args):
    print("The following commands are avaiable: " + reduce(lambda a, b: a + ", " + b, commands))
    
def command_exit(master, args):
    pass
    
commands = {
    'say': command_say,
    'users': command_users,
    'chat': command_chat,
    'accept': command_accept,
    'refuse': command_refuse,
    'close': command_close,
    'help': command_help,
    'exit': command_exit
}

class SocketMaster(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.socket = socket
        
        self.expect = {}
        self.pending_write = []

           
    def is_chatting(self):
        return False
        
    def queue_write(self, message, address):
        self.pending_write.insert(0, (message, address))
        
    def run(self):
        while chat_running:
            (readcheck, writecheck, _) = select.select([self.socket], [self.socket], [], configuration.heartbeat / 10)
            
            if self.socket in readcheck:
                (data, address) = self.socket.recvfrom()
                if address in self.expect:
                    self.expect[address](data)
                else:
                    print_threaded("Unexpected message '%s' from '%s'\n" % (repr(data), repr(address)))
                
            if self.socket in writecheck:
                if self.pending_write:
                    write = self.pending_write.pop()
                    self.socket.sendto(write[0], write[1])

def run(config):
    global configuration, chat_running, listen, your_username, server_address, server_handler
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
            your_username = read_validusername()
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
             
        # Ok, send it to a thread and don't consider it ours anymore
        sockmaster = SocketMaster(mainsock)
        sockmaster.start()
        del mainsock # don't even keep the old reference
        
        server_handler = ServerMessageHandler()
        sockmaster.expect[server_address] = server_handler
        
        while chat_running:
            client_common.input_handler(sockmaster.is_chatting, commands, sockmaster)
            
        print("Bye.")
        
    except common.SocketUnexpectedClosed:
        chat_running = False
        print("Lost connection to server.")
    except Exception, err:
        chat_running = False
        import traceback
        print(traceback.format_exc())
        