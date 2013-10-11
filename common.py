from __future__ import print_function
import socket, sys, re
    
class SocketUnexpectedClosed:
    pass

class VerboseSocket:
    def __init__(self, sock, name, print_func = print):
        self.sock = sock
        self.name = name
        self.print_func = print_func
        
    def send(self, arg):
        self.sock.send(arg)
        self.debug(repr(arg), '>')
    
    def receive(self):
        data = self.sock.recv(2048)
        if len(data) == 0:
            raise SocketUnexpectedClosed()
        self.debug(repr(data), '<')
        return data
        
    def connect(self, target):
        self.debug("Connecting to %s:%s" % target)
        self.sock.connect(target)
        self.debug("Connected!")
        
    def bind(self, target):
        self.sock.bind(target)
        addr = self.sock.getsockname()
        self.debug("Bound to %s:%s" % addr)
        
    def close(self):
        self.sock.close()
        self.debug("Closed!")
    
    def accept(self):
        self.debug("Waiting for a client!")
        client = self.sock.accept()
        self.debug("A client connected! Remote is %s" % repr(client[1]))
        return client
        
    def listen(self, backlog = 1):
        self.sock.listen(backlog)
        self.debug("Listening, with a backlog of %s" % (backlog))
        
    def fileno(self):
        return self.sock.fileno()
        
    def debug(self, message, style = ' '):
        self.print_func("[%s%s] %s" % (style, self.name, message))
        
class Communication(VerboseSocket):
    def __init__(self, socket, name):
        VerboseSocket.__init__(self, socket, name)
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
        
def null_print(message):
    pass
