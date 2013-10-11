from __future__ import print_function
import args

configuration = args.parse_server()

if configuration.udp:
    import server_udp as serv
else:
    import server_tcp as serv

serv.run(configuration)
