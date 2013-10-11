from __future__ import print_function
import socket, ssl, sys, threading, select
import common, args

server_running = True
HEARTBEAT_INTERVAL = None
users = {}
configuration = None

def run(config):
    global configuration
    configuration = config
    
    listensock = common.VerboseSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), "L")
    listensock.print_func = print if configuration.verbosity >= 1 else common.null_print
    listensock.bind(("0.0.0.0", configuration.port))
    listensock.listen(2)

    # MAIN LOOP
    
    listensock.close()