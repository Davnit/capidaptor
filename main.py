#!/usr/bin/env python3

from server import Server

import argparse


parser = argparse.ArgumentParser(prog='capidaptor')
parser.add_argument('--interface', help='Specifies the interface and port to listen on')
parser.add_argument('--debug', help='Enables debugging mode', action='store_true')
parser.add_argument('--ignore-unsupported', help='Silently drops unsupported commands', action='store_true')
parser.add_argument('--do-version-check', help='Sends version check requests to clients.', action='store_true')
parser.add_argument('--out-format', help='Specifies the format to use when printing console messages.')
parser.add_argument('--debug-format', help='Specifies the format to use when printing debug messages.')

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

if args.ignore_unsupported:
    s.ignore_unsupported_commands = True

if args.do_version_check:
    s.do_version_check = True

if args.out_format:
    s.out_format = args.out_format

if args.debug_format:
    s.debug_format = args.debug_format

s.start()
