import args

configuration = args.parse_client()

if configuration.udp:
    import client_udp as cli
else:
    import client_tcp as cli

cli.run(configuration)
