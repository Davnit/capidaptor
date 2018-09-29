
from bncs import ThinBncsClient, SID_NULL
from capi import CapiClient

from threading import Thread, Lock, Timer
from socket import socket, AF_INET, SOCK_STREAM


class Server(Thread):
    def __init__(self, port=6112, iface=''):
        self.port = port
        self.iface = iface
        self.debug = False

        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.bind((iface, port))
        self.socket.listen(5)

        self.clients = {}

        self.lock = Lock()
        super().__init__()

        self._keep_alive_timer = Timer(300, self._send_keep_alives)
        self._keep_alive_timer.daemon = True
        self._keep_alive_timer.start()

    def run(self):
        print("[Server] ThinBNCS server started - listening on port %i" % self.port)
        while True:
            (client, address) = self.socket.accept()
            obj = Client(self, client, address, self.get_client_id())
            obj.print("Connected from %s" % address[0])

            self.clients[obj.id] = obj
            obj.bncs.start()

    def _send_keep_alives(self):
        self.lock.acquire()

        for c in self.clients.values():
            c.bncs.send(SID_NULL)
        self.lock.release()

    def get_client_id(self):
        self.lock.acquire()

        x = 1
        while x in self.clients.keys():
            x += 1
        self.lock.release()
        return x

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

        if self.capi.connected:
            self.capi.socket.close()
            self.capi.connected = False

        if self.id in self.server.clients.keys():
            self.print("Connections closed%s" % ((": " + reason) if reason else ''))
            del self.server.clients[self.id]

        self.server.lock.release()

    def print(self, text):
        print("Client #%i - %s" % (self.id, text))

    def debug(self, text):
        if self.server.debug:
            print("DEBUG: %s" % text)

    def error(self, message):
        self.bncs.send_error(message)
