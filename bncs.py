
import buffer

from threading import Thread
from datetime import datetime
import random
import json
import shlex


protocols = [
    0x01    # GAME
]

products = ["STAR", "SEXP", "D2DV", "D2XP", "WAR3", "W3XP", "W2BN", "DRTL", "DSHR"]

check_revision_data = (0x0000000000000000, "ver-IX86-1.mpq", "C=10 A=20 B=30 4 A=A-S B=B+C C=C^A A=A^B")

unsupported_commands = ["away", "dnd", "friends", "options", "squelch", "unsquelch", "who", "whoami", "whois",
                        "ignore", "unignore", "where", "whereis", "clan", "f", "c", "o", "beep", "mail", "nobeep",
                        "stats", "time", "users", "help", "?"]

SID_NULL = 0x00
SID_CLIENTID = 0x05
SID_STARTVERSIONING = 0x06
SID_REPORTVERSION = 0x07
SID_ENTERCHAT = 0x0A
SID_CHATCOMMAND = 0x0E
SID_CHATEVENT = 0x0F
SID_LOGONCHALLENGEEX = 0x1D
SID_PING = 0x25
SID_LOGONCHALLENGE = 0x28
SID_LOGONRESPONSE = 0x29
SID_GETICONDATA = 0x2D
SID_GETFILETIME = 0x33
SID_CDKEY2 = 0x36
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

FLAG_OPERATOR = 0x02
FLAG_SPEAKER = 0x04
FLAG_BNETADMIN = 0x08
FLAG_SQUELCHED = 0x20

ERROR_NOTLOGGEDON = "That user is not logged on."
GATEWAY_USER = "CAPI Gateway"

IGNORE_PACKETS = [SID_NULL, SID_PING]


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
        self.last_talk = datetime.now()

        self._handlers = {
            # Modern version checking
            SID_AUTH_INFO: self._handle_auth_info,
            SID_AUTH_CHECK: self._handle_auth_check,

            # NLS Login
            SID_AUTH_ACCOUNTLOGON: self._handle_auth_accountlogon,

            # OLS Login
            SID_LOGONRESPONSE2: self._handle_logon_response,

            # Legacy Login
            SID_STARTVERSIONING: self._handle_start_versioning,
            SID_REPORTVERSION: self._handle_report_version,
            SID_LOGONRESPONSE: self._handle_logon_response,

            # Chat
            SID_ENTERCHAT: self._handle_enterchat,
            SID_CHATCOMMAND: self._handle_chatcommand,

            # Misc functions
            SID_QUERYREALMS2: self._handle_query_realms2,
            SID_GETFILETIME: self._handle_get_filetime,
            SID_GETICONDATA: self._handle_get_icon_data,
            SID_CDKEY2: self._handle_cd_key2
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
            return False

        pak = buffer.DataBuffer()
        pak.insert_byte(0xFF)
        pak.insert_byte(pid)

        if payload:
            pak.insert_word(len(payload) + 4)
            pak.insert_raw(payload.data if isinstance(payload, buffer.DataBuffer) else payload)
        else:
            pak.insert_word(4)

        try:
            self.socket.sendall(pak.data)
        except (ConnectionError, TimeoutError) as ex:
            self.parent.close("BNCS send failed: %s" % ex)
            return False

        if pid not in IGNORE_PACKETS:
            self.parent.debug("Sent BNCS packet 0x%02x (len: %i)" % (pid, len(pak)))

        return True

    def receive(self):
        if not self.connected:
            return None, None

        try:
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

                if pid not in IGNORE_PACKETS:
                    self.parent.debug("Received BNCS packet 0x%02x (len: %i)" % (pid, length))

                self.last_talk = datetime.now()
                return pid, pak
            else:
                self.disconnect("Client closed the connection")
                return None, None
        except (ConnectionError, TimeoutError) as ex:
            self.disconnect("BNCS receive failed: %s" % ex)
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
                try:
                    self._handlers.get(pid)(pid, pak)
                except Exception as ex:
                    self.parent.print("ERROR! Something happened while processing BNCS packet 0x%02x." % pid)
                    self.parent.print("ERROR! Packet data dump:\n%s" % buffer.format_buffer(pak))
                    self.parent.print("ERROR! Exception: %s" % ex)

                    if self.parent.server.debug:
                        raise

        self.disconnect("BNCS thread exited")

    def send_chat(self, eid, username, text, flags=0, ping=0, encoding='utf-8', errors=None):
        pak = buffer.DataBuffer()
        pak.insert_dword(eid)
        pak.insert_dword(flags)
        pak.insert_dword(ping)
        pak.insert_dword(0)             # IP Address
        pak.insert_dword(0xbaadf00d)    # Account number
        pak.insert_dword(0xbaadf00d)    # Registration authority
        pak.insert_string(username)
        pak.insert_string(text, encoding, errors)
        self.send(SID_CHATEVENT, pak)

    def send_error(self, message):
        self.send_chat(EID_ERROR, GATEWAY_USER, message)

    def send_logon_response(self, success, error=None, proof=None):
        # Status can be a number (0 = success, 2 = fail) or custom error message string.

        if success:
            self.parent.print("BNCS login complete - authenticated to chat API")
            self.logged_on = True

        pak = buffer.DataBuffer()
        if self.logon_type == -1:
            # Legacy login
            pak.insert_dword(0x01 if success else 0x00)
            self.send(SID_LOGONRESPONSE, pak)
        elif self.logon_type == 0:
            # Old login (OLS)
            pak.insert_dword(0x00 if success else 0x02)
            self.send(SID_LOGONRESPONSE2, pak)
        elif self.logon_type in [1, 2]:
            # New login (NLS)
            if success:
                pak.insert_dword(0x00)
            elif error:
                pak.insert_dword(0x0F)
            else:
                pak.insert_dword(0x02)

            pak.insert_raw(proof or (b'\0' * 20))
            pak.insert_string(error or '')
            self.send(SID_AUTH_ACCOUNTLOGONPROOF, pak)

    def enter_chat(self, username, stats, account=None):
        self.username = username
        if account is None:
            account = username
            if username.startswith("[B]"):
                account = username[3:]

        pak = buffer.DataBuffer()
        pak.insert_string(username)
        pak.insert_string(stats)
        pak.insert_string(account)
        self.send(SID_ENTERCHAT, pak)

    def send_ping(self):
        pak = buffer.DataBuffer()
        pak.insert_dword(random.getrandbits(32))
        self.send(SID_PING, pak)

    def _handle_auth_info(self, pid, pak):
        if self.product is not None:
            self.disconnect("Sent repeat client auth.")
            return

        pak.get_raw(8)      # First 8 bytes not needed
        self.product = pak.get_dword(True)
        if self.product not in products:
            self.disconnect("Unsupported product (%s)" % self.product)
            return

        # Send ping packet
        pak = buffer.DataBuffer()
        pak.insert_dword(random.getrandbits(32))
        self.send(SID_PING, pak)

        pak = buffer.DataBuffer()
        if self.parent.server.do_version_check:
            # Send version check request
            pi = check_revision_data
            pak.insert_dword(self.logon_type)       # Logon type
            pak.insert_dword(self._server_token)    # Server token
            pak.insert_dword(0)                     # UDP value
            pak.insert_long(pi[0])                  # CRev archive filetime
            pak.insert_string(pi[1])                # CRev archive filename
            pak.insert_string(pi[2])                # CRev formula

            if self.product in ["WAR3", "W3XP"]:
                pak.insert_raw(b'\0' * 128)         # W3 server signature

            self.send(SID_AUTH_INFO, pak)
        else:
            # Skip sending the request and immediately send the result.
            pak.insert_dword(0x00)      # Success
            pak.insert_string('')
            self.send(SID_AUTH_CHECK, pak)

    def _handle_auth_check(self, pid, pak):
        self._client_token = pak.get_dword()

        # Send auth check response
        pak = buffer.DataBuffer()
        pak.insert_dword(0x00)      # Success
        pak.insert_string('')
        self.send(SID_AUTH_CHECK, pak)

    def _handle_auth_accountlogon(self, pid, pak):
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

    def _handle_enterchat(self, pid, pak):
        if not (self.logged_on and self.parent.capi.connected()):
            self.disconnect("Attempt to enter chat before login")
            return

        self.parent.capi.send_command("Botapichat.ConnectRequest")

    def _handle_chatcommand(self, pid, pak):
        text = pak.get_string()
        if text.startswith("/"):
            parts = shlex.split(text[1:])
            cmd = parts[0].lower()

            # BNCS commands
            if cmd in ["channel", "join"]:
                self.send_error("That channel is restricted")
            elif cmd in ["w", "m", "msg", "whisper"]:
                if len(parts) == 1:
                    self.send_error(ERROR_NOTLOGGEDON)
                else:
                    if len(parts) == 2:
                        self.send_error("What do you want to say?")
                    else:
                        self.parent.capi.send_chat(' '.join(parts[2:]), "whisper", parts[1])
            elif cmd in ["me", "emote"]:
                self.parent.capi.send_chat(' '.join(parts[1:]) if len(parts) > 1 else '', "emote")
            elif cmd in ["ban", "kick", "unban", "designate"]:
                if len(parts) == 1:
                    self.send_error(ERROR_NOTLOGGEDON)
                else:
                    if cmd == "designate":      # Not really a reason for changing this it just seems nicer.
                        cmd = "op"

                    # The chat API does not support messages in ban/kick messages.
                    self.parent.capi.bankickunban(parts[1], cmd)
            elif cmd == "capi":
                if len(parts) > 1:
                    if parts[1].lower() == "debug":
                        last_message = self.parent.capi.last_talk
                        self.send_chat(EID_INFO, GATEWAY_USER, "Last CAPI message received: %s (%s seconds ago)" %
                                       (last_message, int((datetime.now() - last_message).total_seconds())))
                        self.send_chat(EID_INFO, GATEWAY_USER, "CAPI connected: %s" % self.parent.capi.connected())
                        self.send_chat(EID_INFO, GATEWAY_USER, "Connection monitor active: %s" %
                                       self.parent.server.monitor.is_alive())
                    elif parts[1].lower() == "send":
                        if len(parts) == 2:
                            self.send_error("You must specify a message to send.")
                        else:
                            payload_start = text.index(parts[2]) + len(parts[2])
                            payload_start = text.index(' ', payload_start) + 1
                            payload = json.loads(text[payload_start:]) if len(parts) > 3 else None
                            self.parent.capi.send_command(parts[2], payload)
                else:
                    self.send_chat(EID_INFO, GATEWAY_USER, "Available sub-commands: debug, send")
            else:
                if cmd in unsupported_commands:
                    if not self.parent.server.ignore_unsupported_commands:
                        if cmd in ["unsquelch", "unignore"] and len(parts) > 1:
                            name = parts[1].lower()
                            if name in [self.username.lower(), "*" + self.username.lower()]:
                                # Send flag updates for every user in the channel
                                for user in self.parent.capi.users.values():
                                    self.send_chat(EID_USERFLAGS, user.name, user.get_statstring(), user.get_flags())
                                return

                        self.send_error("That command is not supported by the chat API.")

                    self.parent.debug("Unsupported command: %s" % repr(parts))
                else:
                    self.send_error("That is not a valid command.")
                    self.parent.debug("Invalid command: %s" % repr(parts))
        else:
            self.parent.capi.send_chat(text)

    def _handle_logon_response(self, pid, pak):
        if self.logged_on:
            self.disconnect("Attempt to login again")
            return

        self._client_token = pak.get_dword()
        pak.get_raw(24)     # Server token and password hash
        self.logon_type = (0 if pid == SID_LOGONRESPONSE2 else -1)

        # Start CAPI login process
        self.parent.capi.authenticate(pak.get_string())

    def _handle_query_realms2(self, pid, pak):
        pak = buffer.DataBuffer()
        pak.insert_dword(0)
        pak.insert_dword(0)
        self.send(SID_QUERYREALMS2, pak)

    def _handle_get_filetime(self, pid, pak):
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

    def _handle_get_icon_data(self, pid, pak):
        # Packet has no contents
        pak = buffer.DataBuffer()
        pak.insert_long(0)
        pak.insert_string('icons.bni')
        self.send(SID_GETICONDATA, pak)

    def _handle_start_versioning(self, pid, pak):
        if self.product is not None:
            self.disconnect("Sent repeat client auth")
            return

        pak.get_dword()
        self.product = pak.get_dword(True)
        if self.product not in products:
            self.disconnect("Unsupported product (%s)" % self.product)
            return

        # Send SID_CLIENTID
        pak = buffer.DataBuffer()
        pak.insert_dword(0)
        pak.insert_dword(0)
        pak.insert_dword(0)
        pak.insert_dword(0)
        self.send(SID_CLIENTID, pak)

        # Send SID_LOGONCHALLENGEEX2
        pak = buffer.DataBuffer()
        pak.insert_dword(0)                     # UDP Value
        pak.insert_dword(self._server_token)    # Server token
        self.send(SID_LOGONCHALLENGEEX, pak)

        pak = buffer.DataBuffer()
        if self.parent.server.do_version_check:
            # Send SID_STARTVERSIONING
            pi = check_revision_data
            pak.insert_long(pi[0])                  # MPQ filetime
            pak.insert_string(pi[1])                # MPQ filename
            pak.insert_string(pi[2])                # Value string
            self.send(SID_STARTVERSIONING, pak)
        else:
            # Skip the version check
            pak.insert_dword(0x02)      # Result: success
            pak.insert_string('')
            self.send(SID_REPORTVERSION, pak)

    def _handle_report_version(self, pid, pak):
        pak.get_dword()
        self.product = pak.get_dword(True)
        if self.product not in products:
            self.disconnect("Unsupported product (%s)" % self.product)
            return

        # Send version response
        pak = buffer.DataBuffer()
        pak.insert_dword(0x02)      # Result: success
        pak.insert_string('')       # Patch path
        self.send(SID_REPORTVERSION, pak)

    def _handle_cd_key2(self, pid, pak):
        pak.get_raw(20)     # Key properties and server token
        self._client_token = pak.get_dword()

        pak = buffer.DataBuffer()
        pak.insert_dword(0x01)      # Result: OK
        pak.insert_string('')
        self.send(SID_CDKEY2, pak)
