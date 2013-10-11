import socket, ssl, sys, threading, select
import common, args

server_running = True
HEARTBEAT_INTERVAL = None
users = {}

class ClientThread(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        (self.ip, self.port) = socket.getpeername()
        self.socket = common.VerboseSocket(socket, "C " + str(self.ip) + ":" + str(self.port))
        
        self.running = True
        self.username = None
        self.in_chat = None
        self.buffer = []
        self.notifications = []
        
    def fetch_messages(self):
        try:
            data = self.socket.receive()
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
            
        try:
            (try_username, listen_port) = args.split(' ', 1)
            listen_port = int(listen_port)
        except ValueError:
            self.socket.send("INPUT_ERROR\n")
            return
            
        if try_username in users:
            self.socket.send("USER_ALREADY_EXISTS\n")
            return
        
        self.username = try_username
        self.listen_port = listen_port
        users[self.username] = self
        self.socket.send("WELCOME\n")

    def command_heartbeat(self, args):
        self.socket.send("OK\n")
        pass
        
    def command_listusers(self, args):
        self.socket.send(reduce(lambda a, b: a + " " + b, users) + "\n")
        
    def command_requestchat(self, target_user):
        if target_user not in users:
            self.socket.send("UNKNOWN_USER\n")
            return
            
        if users[target_user].in_chat:
            self.socket.send("USER_IS_BUSY\n")
            return
            
        users[target_user].notifications.insert(0, "CHATREQUEST " + self.username)
        self.socket.send("OK\n")
    
    def command_enterchat(self, target_user):
        self.in_chat = target_user
        self.socket.send("OK\n")
    
    def command_leavechat(self, args):
        self.in_chat = None
        self.socket.send("OK\n")
        
    def command_killserver(self, args):
        global server_running
        server_running = False
        self.socket.send("OK\n")
        
    def command_queryuserinfo(self, target_user):
        if target_user not in users:
            self.socket.send("UNKNOWN_USER\n")
            return
        user = users[target_user]
        self.socket.send("%s %s\n" % (user.ip, user.listen_port))
        
    def command_logout(self, args):
        self.running = False
        self.socket.send("BYE\n")

    def run(self):
        self.socket.sock.settimeout(HEARTBEAT_INTERVAL)
        self.socket.debug("Thread Run")
        try:
            while self.running:
                (readvalid, writevalid, errorvalid) = select.select([self.socket], [self.socket], [], 5)
                
                if self.socket in writevalid:
                    while self.notifications:
                        self.socket.send("NOTIFICATION " + self.notifications.pop() + "\n")
                        
                if self.socket not in readvalid and not self.buffer:
                    continue
            
                message = self.get_message()
                if not message:
                    self.running = False
                    break
                result = message.split(' ', 1)
                arguments = ""
                if len(result) > 1: arguments = result[1]
                
                command = result[0].upper()
                
                if command not in ClientThread.commands:
                    self.socket.send("UNKNOWN_COMMAND\n")
                    
                elif command not in ClientThread.permission_checker:
                    self.socket.debug("Valid command without permission checker")
                    self.socket.send("INTERNAL_ERROR\n")
                    
                elif not ClientThread.permission_checker[command](self):
                    self.socket.send("PERMISSION_DENIED\n")
                    
                else:
                    ClientThread.commands[command](self, arguments)
                
        except Exception, e:
            self.socket.debug("Thread crash! Reason: " + str(e))
        except common.SocketUnexpectedClosed:
            self.socket.debug("Thread closed unexpectedly.")
            
        if self.username:
            del users[self.username]
        self.socket.close()
        self.socket.debug("Thread finished.")
    
    
    def permissionchecker_islogged(self):
        return self.username is not None
            
    permission_checker = {
        'LOGIN': lambda x: True,
        'HEARTBEAT': permissionchecker_islogged,
        'LISTUSERS': permissionchecker_islogged,
        'KILLSERVER': permissionchecker_islogged,
        'REQUESTCHAT': permissionchecker_islogged,
        'ENTERCHAT': permissionchecker_islogged,
        'LEAVECHAT': permissionchecker_islogged,
        'QUERYUSERINFO': permissionchecker_islogged,
        'LOGOUT': permissionchecker_islogged
    }
    commands = {
        'LOGIN': command_login,
        'HEARTBEAT': command_heartbeat,
        'LISTUSERS': command_listusers,
        'KILLSERVER': command_killserver,
        'REQUESTCHAT': command_requestchat,
        'ENTERCHAT': command_enterchat,
        'LEAVECHAT': command_leavechat,
        'QUERYUSERINFO': command_queryuserinfo,
        'LOGOUT': command_logout
    }

(server_listen_port, tcp) = args.parse_server()
if not tcp:
    raise Exception("UDP NYI")
    
listensock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "L")
listensock.bind(("0.0.0.0", server_listen_port))
listensock.listen(2)

while server_running:
    if listensock not in select.select([listensock], [], [], 5)[0]:
        continue
    ClientThread(listensock.accept()[0]).start()

listensock.close()