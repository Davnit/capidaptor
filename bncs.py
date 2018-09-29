
import buffer

from threading import Thread
import random


protocols = [
    0x01    # GAME
]

products = {
    "STAR": (0x0000000000000000, "ver-IX86-1.mpq", "C=10 A=20 B=30 4 A=A-S B=B+C C=C^A A=A^B"),
    "D2DV": (0x01D1B882907FAA00, "ver-IX86-4.mpq", "C=68487743 A=4248224505 B=2968823989 4 A=A-S B=B+C C=C^A A=A^B"),
    "WAR3": (0x01D1B88295445E00, "ver-IX86-6.mpq", "C=490570630 B=252301178 A=4087433830 4 A=A^S B=B-C C=C-A A=A+B")
}
products["SEXP"] = products["STAR"]
products["D2XP"] = products["D2DV"]
products["W3XP"] = products["WAR3"]


SID_NULL = 0x00
SID_ENTERCHAT = 0x0A
SID_CHATCOMMAND = 0x0E
SID_CHATEVENT = 0x0F
SID_PING = 0x25
SID_GETICONDATA = 0x2D
SID_GETFILETIME = 0x33
SID_LOGONRESPONSE2 = 0x3A
SID_QUERYREALMS2 = 0x40
SID_AUTH_INFO = 0x50
SID_AUTH_CHECK = 0x51
SID_AUTH_ACCOUNTLOGON = 0x53
SID_AUTH_ACCOUNTLOGONPROOF = 0x54

EID_SHOWUSER = 0x01
EID_JOIN = 0x02
EID_LEAVE = 0x03
EID_WHISPER = 0x04
EID_TALK = 0x05
EID_CHANNEL = 0x07
EID_USERFLAGS = 0x09
EID_WHISPERSENT = 0x0A
EID_INFO = 0x12
EID_ERROR = 0x13
EID_EMOTE = 0x17

PROD_CHAT = "TAHC"

FLAG_OPERATOR = 0x02
FLAG_SPEAKER = 0x04
FLAG_BNETADMIN = 0x08
FLAG_SQUELCHED = 0x20

ERROR_NOTLOGGEDON = "That user is not logged on."


class ThinBncsClient(Thread):
    def __init__(self, parent, socket):
        self.parent = parent
        self.socket = socket

        self.connected = True
        self.protocol = None
        self.product = None
        self.logged_on = False
        self.username = None

        self.logon_type = 0

        self._handlers = {
            SID_AUTH_INFO: self._handle_auth_info,
            SID_AUTH_CHECK: self._handle_auth_check,
            SID_AUTH_ACCOUNTLOGON: self._handle_auth_accountlogon,
            SID_ENTERCHAT: self._handle_enterchat,
            SID_CHATCOMMAND: self._handle_chatcommand,
            SID_LOGONRESPONSE2: self._handle_logon_response2,
            SID_QUERYREALMS2: self._handle_query_realms2,
            SID_GETFILETIME: self._handle_get_filetime,
            SID_GETICONDATA: self._handle_get_icon_data
        }

        random.seed()
        self._server_token = random.getrandbits(32)
        self._client_token = None

        super().__init__()
        self.daemon = True

    def disconnect(self, reason=None):
        self.parent.close(reason)

    def send(self, pid, payload=None):
        if not self.connected:
            return

        pak = buffer.DataBuffer()
        pak.insert_byte(0xFF)
        pak.insert_byte(pid)

        if payload:
            pak.insert_word(len(payload) + 4)
            pak.insert_raw(payload.data if isinstance(payload, buffer.DataBuffer) else payload)
        else:
            pak.insert_word(4)

        self.socket.sendall(pak.data)
        self.parent.debug("Sent BNCS packet 0x%02x (len: %i)" % (pid, len(pak)))

    def receive(self):
        if not self.connected:
            return None, None

        # Get packet header
        header = self.socket.recv(4)
        if len(header) == 4:
            pak = buffer.DataReader(header)
            if pak.get_byte() != 0xFF:
                self.disconnect("Invalid BNCS packet header")
                return None, pak

            pid = pak.get_byte()
            length = pak.get_word()

            if length > 4:
                pak.data += self.socket.recv(length - 4)

            self.parent.debug("Received BNCS packet 0x%02x (len: %i)" % (pid, length))
            return pid, pak
        else:
            self.disconnect("Failed to receive packet header")
            return None, None

    def run(self):
        # First byte from the client determines the protocol
        p = self.socket.recv(1)
        if p[0] in protocols:
            self.protocol = p[0]
        else:
            self.disconnect("Unsupported protocol selection (0x%02x)" % p[0])
            return

        # Receive packets
        while self.connected:
            pid, pak = self.receive()
            if pid is None:
                break

            if pid in self._handlers.keys():
                self._handlers.get(pid)(pak)

        self.disconnect("BNCS thread exited")

    def send_chat(self, eid, username, text, flags=0, ping=0):
        pak = buffer.DataBuffer()
        pak.insert_dword(eid)
        pak.insert_dword(flags)
        pak.insert_dword(ping)
        pak.insert_dword(0)             # IP Address
        pak.insert_dword(0xbaadf00d)    # Account number
        pak.insert_dword(0xbaadf00d)    # Registration authority
        pak.insert_string(username)
        pak.insert_string(text)
        self.send(SID_CHATEVENT, pak)

    def send_error(self, message):
        self.send_chat(EID_ERROR, "CAPI Gateway", message)

    def send_logon_response(self, status=0, proof=None):
        # Status can be a number (0 = success, 2 = fail) or custom error message string.
        is_str = isinstance(status, str)

        pak = buffer.DataBuffer()
        if self.logon_type == 0:
            pak.insert_dword(0x06 if is_str else status)
            if is_str:
                pak.insert_string(status)
            self.send(SID_LOGONRESPONSE2, pak)
        elif self.logon_type in [1, 2]:
            pak.insert_dword(0x0F if is_str else status)
            pak.insert_raw(proof or (b'\0' * 20))
            pak.insert_string(status if is_str else '')
            self.send(SID_AUTH_ACCOUNTLOGONPROOF, pak)

        if status == 0x00:
            self.parent.print("BNCS login complete - authenticated to chat API")
            self.logged_on = True

    def enter_chat(self, username, stats=None, account=None):
        self.username = username

        pak = buffer.DataBuffer()
        pak.insert_string(username)
        pak.insert_string(stats or PROD_CHAT)
        pak.insert_string(account or username)
        self.send(SID_ENTERCHAT, pak)

    def _handle_auth_info(self, pak):
        if self.product:
            self.disconnect("Sent repeat client auth.")
            return

        pak.get_raw(8)      # First 8 bytes not needed
        self.product = pak.get_raw(4).decode('ascii')[::-1]
        if self.product not in products:
            self.disconnect("Unsupported product (%s)" % self.product)
            return

        # Send ping packet
        pak = buffer.DataBuffer()
        pak.insert_dword(random.getrandbits(32))
        self.send(SID_PING, pak)

        # Send version check request
        pi = products.get(self.product)
        pak = buffer.DataBuffer()
        pak.insert_dword(self.logon_type)       # Logon type
        pak.insert_dword(self._server_token)    # Server token
        pak.insert_dword(0)                     # UDP value
        pak.insert_long(pi[0])                  # CRev archive filetime
        pak.insert_string(pi[1])                # CRev archive filename
        pak.insert_string(pi[2])                # CRev formula

        if self.product in ["WAR3", "W3XP"]:
            pak.insert_raw(b'\0' * 128)         # W3 server signature

        self.send(SID_AUTH_INFO, pak)

    def _handle_auth_check(self, pak):
        self._client_token = pak.get_dword()

        # Send auth check response
        pak = buffer.DataBuffer()
        pak.insert_dword(0x00)      # Success
        pak.insert_string('')
        self.send(SID_AUTH_CHECK, pak)

    def _handle_auth_accountlogon(self, pak):
        if self.logged_on:
            self.disconnect("Attempt to login again")
            return

        pak.get_raw(32)     # Client key
        self.logon_type = 2

        # Start the CAPI login process
        self.parent.capi.authenticate(pak.get_string())

        # Send login response
        pak = buffer.DataBuffer()
        pak.insert_dword(0)             # Logon accepted
        pak.insert_raw(b'\0' * 32)      # Account salt
        pak.insert_raw(b'\0' * 32)      # Server key
        self.send(SID_AUTH_ACCOUNTLOGON, pak)

    def _handle_enterchat(self, pak):
        if not self.logged_on or not self.parent.capi.connected:
            self.disconnect("Attempt to enter chat before login")
            return

        self.parent.capi.send_command("Botapichat.ConnectRequest")

    def _handle_chatcommand(self, pak):
        text = pak.get_string()
        if text.startswith("/"):
            parts = text[1:].split(' ', maxsplit=1)
            cmd = parts[0].lower()

            # BNCS commands
            if cmd == "join":
                self.send_error("Channel is restricted")
            elif cmd in ["w", "m", "msg", "whisper"]:
                if len(parts) == 1:
                    self.send_error(ERROR_NOTLOGGEDON)
                else:
                    arg = parts[1].split(' ', maxsplit=1)
                    if len(arg) == 1:
                        self.send_error("What do you want to say?")
                    else:
                        self.parent.capi.send_chat(arg[1], "whisper", arg[0])
            elif cmd in ["me", "emote"]:
                self.parent.capi.send_chat(parts[1] if len(parts) > 1 else '', "emote")
            elif cmd in ["ban", "kick", "unban", "designate"]:
                if len(parts) == 1:
                    self.send_error(ERROR_NOTLOGGEDON)
                else:
                    # The chat API doesn't support ban/kick messages, but BNCS clients may still send them.
                    arg = parts[1].split(' ', maxsplit=1)
                    if cmd == "designate":      # Not really a reason for changing this it just seems nicer.
                        cmd = "op"

                    self.parent.capi.bankickunban(arg[0], cmd)
            else:
                if cmd == "unignore" and len(parts) == 2:
                    name = parts[1].lower()
                    if name in [self.username.lower(), "*" + self.username.lower()]:
                        return

                self.send_error("That is not a valid command.")
        else:
            self.parent.capi.send_chat(text)

    def _handle_logon_response2(self, pak):
        if self.logged_on:
            self.disconnect("Attempt to login again")
            return

        pak.get_raw(28)     # Tokens and password hash
        self.logon_type = 0

        # Start CAPI login process
        self.parent.capi.authenticate(pak.get_string())

    def _handle_query_realms2(self, pak):
        pak = buffer.DataBuffer()
        pak.insert_dword(0)
        pak.insert_dword(0)
        self.send(SID_QUERYREALMS2, pak)

    def _handle_get_filetime(self, pak):
        req_id = pak.get_dword()
        unknown = pak.get_dword()
        filename = pak.get_string()

        # No files ever exist.
        pak = buffer.DataBuffer()
        pak.insert_dword(req_id)
        pak.insert_dword(unknown)
        pak.insert_long(0)
        pak.insert_string(filename)
        self.send(SID_GETFILETIME, pak)

    def _handle_get_icon_data(self, pak):
        # Packet has no contents
        pak = buffer.DataBuffer()
        pak.insert_long(0)
        pak.insert_string('icons.bni')
        self.send(SID_GETICONDATA, pak)
