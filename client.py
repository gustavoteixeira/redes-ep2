import socket, sys, re

import common

host = sys.argv[1]
port = int(sys.argv[2])
tcp = True
if len(sys.argv) > 3:
    if sys.argv[3] == 'udp':
        tcp = False
    elif sys.argv[3] == 'tcp':
        tcp = True
    else:
        raise Exception("Unknown method: " + sys.argv[2])
        
if not tcp:
    raise Exception("UDP NYI")
    

listensock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "L")
listensock.bind(("0.0.0.0", 0))
listensock.listen(0)

serversock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "S")
serversock.connect((host, port))

class ExitMessage: pass
class ListenMessage: pass

def command_users(server, args):
    server.send("LISTUSERS\n")
    userlist = server.receive().strip().splitlines()
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
    response = server.receive()
    if response == "UNKNOWN_USER\n":
        print("User '%s' is not logged in." % target_user)
        return
    elif response == "USER_IS_BUSY\n":
        print("User '%s' is busy." % target_user)
        return
    elif response != "OK\n":
        print("Internal server error.")
        return
    else:
        raise ListenMessage()

def command_exit(server, args):
    server.send("LOGOUT\n")
    server.receive()
    raise ExitMessage()
    
commands = {
    'users': command_users,
    'chat': command_chat,
    'exit': command_exit
}

try:
    your_username = None
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
    while chat_running:
        input = raw_input("> ").strip()
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
            listensock.sock.settimeout(10)
            p2psocket = listensock.accept()
            p2psocket.close()
        
    serversock.close()
    listensock.close()
except common.SocketUnexpectedClosed:
    print("Lost connection to server.")