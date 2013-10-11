from __future__ import print_function
import socket, ssl, sys, threading, select, time
import common, args

server_running = True
HEARTBEAT_INTERVAL = None
users = {}
ip_username = {}
configuration = None

def get_command_list(s):
    return s

def command_login(sock, address, args):
    if address in ip_username:
        sock.sendto("ALREADY_LOGGED_IN\n", address)
        return

    try:
        username = args[0]
        listen = int(args[1])
        
        if username in users:
            sock.sendto("USER_ALREADY_EXISTS\n", address)
            return
            
    except (ValueError, IndexError):
        sock.sendto("INPUT_ERROR\n", address)
        return
        
    ip_username[address] = username
    users[username] = [address, listen, time.time()]
    sock.sendto("WELCOME\n", address)
    
def command_heartbeat(sock, address, args):
    if address not in ip_username: 
        sock.sendto("PERMISSION_DENIED\n", address)
        return
    users[ip_username[address]][2] = time.time()
    sock.sendto("OK\n", address)
    
def command_listusers(sock, address, args):
    if address not in ip_username: 
        sock.sendto("PERMISSION_DENIED\n", address)
        return
    sock.sendto(reduce(lambda a, b: a + " " + b, users) + "\n", address)
    
def command_queryuserinfo(sock, address, args):
    if address not in ip_username: 
        sock.sendto("PERMISSION_DENIED\n", address)
        return
    target_user = args[0] if len(args) > 0 else ""
    if target_user not in users:
        sock.sendto("UNKNOWN_USER\n", address)
        return
    user = users[target_user]
    sock.sendto("%s %s\n" % (user[0][0], user[1]), address)
    
def command_logout(sock, address, args):
    if address not in ip_username: 
        sock.sendto("PERMISSION_DENIED\n", address)
        return
    del users[ip_username[address]]
    del ip_username[address]
    sock.sendto("BYE\n", address)
    
def run(config):
    global configuration
    configuration = config
    
    sock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_DGRAM), "S")
    sock.print_func = print if configuration.verbosity >= 1 else common.null_print
    sock.bind(("0.0.0.0", configuration.port))
    
    while server_running:
        if sock in select.select([sock], [], [], 5)[0]:
            (data, address) = sock.recvfrom()
            for line in data.splitlines():
                command = line.split(' ')
                
                if ('command_' + command[0].lower()) in globals():
                    globals()['command_' + command[0].lower()](sock, address, command[1:])
                    
                if address in ip_username:
                    users[ip_username[address]][2] = time.time()
            
        starttime = time.time()
        for user in list(users.keys()):
            if starttime - users[user][2] > configuration.timeout:
                print("Killing '%s' from lack of heartbeat." % user)
                del ip_username[users[user][0]]
                del users[user]
    
    sock.close()