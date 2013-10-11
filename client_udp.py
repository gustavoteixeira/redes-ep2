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

print_threaded = client_common.print_threaded
raw_input_wrapper = client_common.raw_input_wrapper
read_validusername = client_common.read_validusername
    
# COMMANDS
def command_say(server, args):
    pass

def command_users(server, args):
    pass

def command_chat(server, args):
    pass

def command_accept(server, args):
    pass
    
def command_refuse(server, args):
    pass

def command_close(server, args):
    pass
    
def command_help(server, args):
    print("The following commands are avaiable: " + reduce(lambda a, b: a + ", " + b, commands))
    
def command_exit(server, args):
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
        
        self.chatting = None
        self.pending = {}
        
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
                    message = self.chatting[1].get_message().split(' ', 1)
                    if message[0] == 'SAY':
                        if len(message) == 2:
                            print_threaded(self.chatting[0] + ": " + message[1])
                    elif message[0] == 'CLOSE':
                        self.stop_chatting(True)
                except common.SocketUnexpectedClosed:
                    self.stop_chatting(True)
            
        self.socket.close()
        if self.chatting:
            self.chatting[1].close()

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
        del mainsock # don't even keep the old reference
        
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
        