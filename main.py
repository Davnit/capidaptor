
from server import Server

import sys


if len(sys.argv) > 1 and ':' in sys.argv[1]:
    iface = tuple(sys.argv[1].split(':', maxsplit=1))
    s = Server(iface[1], iface[0])
else:
    s = Server()

s.start()
