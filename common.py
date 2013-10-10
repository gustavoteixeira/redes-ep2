import socket, sys, re
    
class SocketUnexpectedClosed:
    pass

class VerboseSocket:
    def __init__(self, sock, name):
        self.sock = sock
        self.name = name
        
    def send(self, arg):
        self.sock.send(arg)
        print("[>%s] %s" % (self.name, repr(arg)))
    
    def receive(self):
        data = self.sock.recv(2048)
        if len(data) == 0:
            raise SocketUnexpectedClosed()
        print("[<%s] %s" % (self.name, repr(data)))
        return data
        
    def connect(self, target):
        print("[ %s] Connecting to %s:%s" % (self.name, target[0], target[1]))
        self.sock.connect(target)
        print("[ %s] Connected!" % (self.name))
        
    def bind(self, target):
        self.sock.bind(target)
        addr = self.sock.getsockname()
        print("[ %s] Bound to %s:%s" % (self.name, addr[0], addr[1]))
        
    def close(self):
        self.sock.close()
        print("[ %s] Closed!" % (self.name))
    
    def accept(self):
        print("[ %s] Waiting for a client!" % (self.name))
        client = self.sock.accept()
        print("[ %s] A client connected! Remote is %s" % (self.name, client[1]))
        return client
        
    def listen(self, backlog = 1):
        self.sock.listen(backlog)
        print("[ %s] Listening, with a backlog of %s" % (self.name, backlog))
        
    def fileno(self):
        return self.sock.fileno()