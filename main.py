
from server import Server

import argparse


parser = argparse.ArgumentParser(prog='capidaptor')
parser.add_argument('--interface', help='Specifies the interface and port to listen on')
parser.add_argument('--debug', help='Enables debugging mode', action='store_true')

args = parser.parse_args()

if args.interface is None:
    s = Server()
else:
    if ':' in args.interface:
        iface = tuple(args.interface.split(':', maxsplit=1))
        s = Server(iface[1], iface[0])
    else:
        s = Server(args.interface)

if args.debug:
    s.debug = True

s.start()
