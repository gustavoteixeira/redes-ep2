import argparse

def _common_arguments(parser):
    parser.add_argument('--udp', default=False, action='store_true', help='Should be use UDP instead of TCP?')
    parser.add_argument('--verbosity', default=0, type=int, choices=[0, 1, 2],
        help='Verbosity level of the sockets.\n0 means quiet, 1 means the main socket and the listen socket in clients, 2 means all sockets')

def parse_client():
    parser = argparse.ArgumentParser(description='Client for a peer to peer chat with centralized tracker.')
    parser.add_argument('host', help='Host of the central tracker')
    parser.add_argument('port', type=int, help='Port of the central tracker')
    _common_arguments(parser)
    return parser.parse_args()
    
def parse_server():
    parser = argparse.ArgumentParser(description='Server for a peer to peer chat with centralized tracker.')
    parser.add_argument('port', type=int, help='Port to listen to connections')
    _common_arguments(parser)
    return parser.parse_args()