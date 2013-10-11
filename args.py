def parse_portudp(data):
    port = int(data[0])
    tcp = True
    if len(data) > 1:
        if data[1] == 'udp':
            tcp = False
        elif data[1] == 'tcp':
            tcp = True
        else:
            raise Exception("Unknown method: " + data[1])
    return (port, tcp)

import sys
def parse_client():
    return (sys.argv[1],) + parse_portudp(sys.argv[2:])
    
def parse_server():
    return parse_portudp(sys.argv[1:])