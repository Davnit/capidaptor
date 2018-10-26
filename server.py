
from bncs import ThinBncsClient, SID_NULL
from capi import CapiClient

from threading import Thread, Lock
from socket import socket, AF_INET, SOCK_STREAM
from datetime import datetime
import time


class Server(Thread):
    def __init__(self, port=6112, iface=''):
        self.port = port
        self.iface = iface

        self.out_format = "Client #%client_id: %message"
        self.debug_format = "DEBUG [%client_id]: %message"
        self.debug = False
        self.encoding_errors = 'namereplace' if self.debug else 'replace'
        self.ignore_unsupported_commands = False
        self.do_version_check = False

        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.bind((iface, port))
        self.socket.listen(5)

        self.clients = {}

        self.lock = Lock()

        # Setup and start the thread for checking connection status
        self.monitor = Thread(target=self._check_connections)
        self.monitor.daemon = True
        self.monitor.start()

        super().__init__()

    def run(self):
        print("[Server] ThinBNCS server started - listening on port %i" % self.port)
        while True:
            (client, address) = self.socket.accept()
            obj = Client(self, client, address, self.get_client_id())
            self.clients[obj.id] = obj

            obj.print("Connected from %s" % address[0])

            if obj.capi.connect():
                obj.bncs.start()
                obj.capi.start()
            else:
                obj.close("Unable to connect to the chat API.")

    def _check_connections(self):
        last_nulls = datetime.now()

        while True:
            now = datetime.now()
            send_nulls = (now - last_nulls).total_seconds() > 60

            for c in list(self.clients.values()):
                # Check for state issue that wasn't caught elsewhere
                if c.bncs.logged_on and not c.capi.connected():
                    c.close("Monitor found CAPI disconnected")
                elif not c.bncs.connected:
                    c.close("Monitor found BNCS disconnected")

                # Check for idle BNCS connections
                if c.bncs.connected and c.bncs.last_talk is not None:
                    idle_time = (now - c.bncs.last_talk).total_seconds()
                    if idle_time >= 90:
                        c.close("BNCS client not responding")
                    elif idle_time >= 30:
                        c.bncs.send_ping()

                    # Send BNCS NULL packets every minute regardless of activity
                    if send_nulls:
                        c.bncs.send(SID_NULL)

                # Check for idle CAPI connections
                if c.capi.connected() and c.capi.last_talk is not None:
                    idle_time = (now - c.capi.last_talk).total_seconds()
                    if idle_time >= 30:
                        c.close("CAPI server not responding")
                    else:
                        c.capi.send_ping()

            if send_nulls:
                last_nulls = datetime.now()

            time.sleep(10)

    def get_client_id(self):
        self.lock.acquire()

        x = 1
        while x in self.clients.keys():
            x += 1

        self.lock.release()
        return x

    def format_message(self, client, fmt, message):
        dt = datetime.now()
        r = fmt.replace("%message", str(message))
        r = r.replace("%client_id", str(client.id))
        r = r.replace("%ip", str(client.address[0]))
        r = r.replace("%name", str(client.capi.username or ''))
        r = r.replace("%channel", str(client.capi.channel or ''))

        # For time formatting codes, see: https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
        return dt.strftime(r)


class Client(object):
    def __init__(self, server, client, address, client_id):
        self.server = server
        self.socket = client
        self.address = address
        self.id = client_id

        self.bncs = ThinBncsClient(self, client)
        self.capi = CapiClient(self)

    def close(self, reason=None):
        self.server.lock.acquire()

        if self.bncs.connected:
            self.bncs.socket.close()
            self.bncs.connected = False

        if self.capi.connected():
            self.capi.socket.close()
            self.capi._connected = False

        if self.id in self.server.clients.keys():
            self.print("Connections closed%s" % ((": " + reason) if reason else ''))
            del self.server.clients[self.id]

        self.server.lock.release()

    def print(self, text):
        print(self.server.format_message(self, self.server.out_format, text))

    def debug(self, text):
        if self.server.debug:
            print(self.server.format_message(self, self.server.debug_format, text))

    def error(self, message):
        self.bncs.send_error(message)
