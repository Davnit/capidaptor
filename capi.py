
import bncs

import ssl
import json
from threading import Thread
from datetime import datetime

import websocket


status_codes = {
    0: {
        0: None     # Success
    },
    6: {
        5: "Request timed out",
        8: "Hit rate limit"
    },
    8: {
        1: "Not connected to chat",
        2: "Bad request"
    }
}

bku_actions = {
    "ban": "Botapichat.BanUserRequest",
    "kick": "Botapichat.KickUserRequest",
    "unban": "Botapichat.UnbanUserRequest",
    "op": "Botapichat.SendSetModeratorRequest"
}

send_message_types = {
    "whisper": "Botapichat.SendWhisperRequest",
    "channel": "Botapichat.SendMessageRequest",
    "emote": "Botapichat.SendEmoteRequest"
}


# BNCS translation
message_eids = {
    "channel": bncs.EID_TALK,
    "whisper": bncs.EID_WHISPER,
    "serverinfo": bncs.EID_INFO,
    "servererror": bncs.EID_ERROR,
    "emote": bncs.EID_EMOTE
}

user_flags = {
    "admin": bncs.FLAG_BNETADMIN,
    "moderator": bncs.FLAG_OPERATOR,
    "speaker": bncs.FLAG_SPEAKER,
    "muteglobal": bncs.FLAG_SQUELCHED,
    "mutewhisper": bncs.FLAG_SQUELCHED
}


def get_flag_int(flags):
    value = 0
    for f in flags:
        value += user_flags.get(f.lower(), 0)
    return value


def get_statstring(attributes):
    # If these attributes haven't been simplified, do it.
    if isinstance(attributes, list):
        user = CapiUser(None, None, attributes=attributes)
        attributes = user.attributes

    string = attributes.get("ProgramId", "CHAT")[::-1]
    return string


class CapiUser(object):
    def __init__(self, user_id, name, flags=None, attributes=None):
        self.id = user_id
        self.name = name
        self.flags = flags or []

        self.attributes = {}
        self.set_attributes(attributes)

    def set_attributes(self, attributes):
        # Normalize attributes into a simple dictionary.
        self.attributes = {}
        if isinstance(attributes, list):
            for item in attributes:
                if isinstance(item, dict):
                    key, value = item.get("key"), item.get("value")
                    self.attributes[key] = value
                else:
                    print("Unexpected attribute format (%s): %s" % (type(attributes).__name__, attributes))
                    break
        elif isinstance(attributes, dict):
            self.attributes = attributes
        elif attributes is not None:
            print("Unexpected attribute format (%s): %s" % (type(attributes).__name__, attributes))

    def get_flags(self):
        return get_flag_int(self.flags)

    def get_statstring(self):
        return get_statstring(self.attributes)


class CapiClient(Thread):
    def __init__(self, parent, endpoint=None):
        self.parent = parent
        self.endpoint = endpoint or "wss://connect-bot.classic.blizzard.com/v1/rpc/chat"
        self.api_key = None

        self.users = {}
        self.channel = None
        self.username = None
        self.last_talk = None

        self._connected = False
        self._disconnecting = False
        self._authenticating = False
        self._last_request_id = 0
        self._requests = {}
        self._received_users = False

        self._handlers = {
            "Botapiauth.AuthenticateResponse": self._handle_auth_response,
            "Botapichat.ConnectResponse": self._handle_connect_response,
            "Botapichat.ConnectEventRequest": self._handle_connect_event,
            "Botapichat.DisconnectEventRequest": self._handle_disconnect_event,
            "Botapichat.UserUpdateEventRequest": self._handle_user_update_event,
            "Botapichat.UserLeaveEventRequest": self._handle_user_leave_event,
            "Botapichat.MessageEventRequest": self._handle_message_event,
            "Botapichat.SendWhisperResponse": self._handle_send_whisper_response
        }

        super().__init__()
        self.daemon = True
        self.socket = None

    def connected(self):
        return (self._connected and self.socket is not None and self.socket.connected)

    def get_user(self, identifier):
        # Identifier can be user id or toon name
        if isinstance(identifier, int):
            return self.users.get(identifier)
        elif isinstance(identifier, str):
            if identifier.startswith("*"):
                identifier = identifier[1:]

            for user in self.users.values():
                if user.name.lower() == identifier.lower():
                    return user
        return None

    def connect(self):
        self.socket = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        try:
            self.socket.connect(self.endpoint)
        except (websocket.WebSocketException, TimeoutError, ConnectionError):
            return False

        self._connected = True
        self._disconnecting = False
        self.last_talk = datetime.now()
        return True

    def disconnect(self, reason=None):
        if self._disconnecting:
            return

        self._disconnecting = True
        self.send_command("Botapichat.DisconnectRequest")
        self.parent.close(reason)

    def send_ping(self):
        self.socket.ping(str(datetime.now()))

    def send_command(self, command, payload=None):
        if not self.connected():
            return False

        rid = self._last_request_id = (self._last_request_id + 1)

        msg = {
            "command": command,
            "request_id": rid,
            "payload": payload or {}
        }

        try:
            self.socket.send(json.dumps(msg), websocket.ABNF.OPCODE_TEXT)
            self.parent.debug("Sent CAPI command: %s" % command)
        except (TimeoutError, websocket.WebSocketException, ConnectionError) as ex:
            self.disconnect("CAPI send failed: %s" % ex)
            return False

        self._requests[rid] = msg
        return rid

    def send_chat(self, message, mtype="channel", target=None):
        payload = {"message": message}

        mtype = mtype.lower()
        if mtype not in send_message_types:
            raise ValueError("Invalid message type - must be %s" % ', '.join(send_message_types.keys()))
        else:
            if mtype == "whisper":
                user = self.get_user(target)
                if user is None:
                    self.parent.error(bncs.ERROR_NOTLOGGEDON)
                    return False
                else:
                    payload["user_id"] = user.id

            return self.send_command(send_message_types.get(mtype), payload)

    def bankickunban(self, target, action="ban"):
        user = self.get_user(target)
        if action.lower() != "unban" and user is None:
            self.parent.error(bncs.ERROR_NOTLOGGEDON)
            return False
        else:
            action = bku_actions.get(action.lower())
            if action is None:
                raise ValueError("Invalid ban/kick/unban action - must be %s" % ', '.join(bku_actions.keys()))

            payload = {"toon_name": target} if user is None else {"user_id": user.id}
            return self.send_command(action, payload)

    def run(self):
        while self.connected():
            try:
                opcode, data = self.socket.recv_data(True)
            except (TimeoutError, websocket.WebSocketException, ConnectionError) as ex:
                if isinstance(ex, websocket.WebSocketPayloadException):
                    self.parent.print("Received CAPI message with invalid UTF-8.")
                    # We can keep going after this it shouldn't be an issue.
                    continue
                else:
                    self.disconnect("CAPI receive failed: %s" % ex)
                    return

            self.last_talk = datetime.now()

            # Check for certain control messages.
            if opcode != websocket.ABNF.OPCODE_TEXT:
                # Ignore these we just needed to record the time.
                continue

            msg = data.decode('utf-8')

            try:
                obj = json.loads(msg)
            except json.JSONDecodeError:
                self.parent.print("Received CAPI message with invalid JSON: %s" % msg)
                # This might not be the end of the world. Don't give up just yet.
                continue

            if not (obj and isinstance(obj, dict)):
                self.parent.print("Received invalid CAPI message (length: %i)" % len(msg))
            else:
                rid = obj.get("request_id")
                command = obj.get("command")
                status = obj.get("status")
                payload = obj.get("payload")

                # Convert status codes to message
                if status:
                    area = status.get("area")
                    code = status.get("code")

                    status = status_codes.get(area)
                    status = status and status.get(code)
                    if not status:
                        status = "Unknown (%i-%i)" % (area, code)

                self.parent.debug("Received CAPI command: %s%s" %
                                  (command, ('' if status is None else (" (status: %s)" % str(status)))))

                if len(payload) > 0:
                    self.parent.debug("Payload: %s" % payload)

                if status:
                    self.parent.print("ERROR: '%s' received status: '%s'" % (command, status))

                # Find the request for this message.
                request = None
                if "Event" not in command:
                    # Events do not have requests directly associated with them.
                    if rid in self._requests:
                        request = self._requests.get(rid).get("payload")
                        del self._requests[rid]
                    else:
                        self.parent.print("Received unexpected response to request ID %i" % rid)

                # Run the command handler, if available.
                if command in self._handlers:
                    try:
                        self._handlers.get(command)(request, payload, status)
                    except Exception as ex:
                        self.parent.print("ERROR! Something happened while processing CAPI command '%s'." % command)
                        self.parent.print("ERROR!   Status: %s" % status)
                        self.parent.print("ERROR!   Payload: %s" % payload)
                        self.parent.print("ERROR!   Request: %s" % request)
                        self.parent.print("ERROR!   Exception: %s" % ex)

                        if self.parent.server.debug:
                            raise

        if self._authenticating:
            self.parent.bncs.send_logon_response(False, "API key invalid")
            self.parent.print("Authentication failed - API key rejected")
            self._authenticating = False
        else:
            self.disconnect("CAPI thread exited")

    def authenticate(self, api_key):
        self.api_key = api_key
        self._authenticating = True
        self.send_command("Botapiauth.AuthenticateRequest", {"api_key": api_key})

    def _handle_auth_response(self, request, response, error):
        self._authenticating = False
        if error:
            self.parent.bncs.send_logon_response(False, str(error))
            self.disconnect("CAPI authentication failed: %s" % error)
        else:
            # Login successful
            self.parent.bncs.send_logon_response(True)

    def _handle_connect_response(self, request, response, error):
        if error:
            self.disconnect("Failed to enter chat: %s" % error)

    def _handle_connect_event(self, request, response, error):
        self.channel = response.get("channel")
        self.parent.bncs.send_chat(bncs.EID_CHANNEL, self.username, self.channel)

    def _handle_disconnect_event(self, request, response, error):
        self.disconnect("Disconnected from chat API")

    def _handle_user_update_event(self, request, response, error):
        user_id = response.get("user_id")
        toon_name = response.get("toon_name")
        attributes = response.get("attribute")
        flags = response.get("flag")

        user = self.get_user(user_id) or CapiUser(user_id, toon_name, flags, attributes)

        if not self.channel:
            # We're not in a channel yet, so this should be our own info.
            self.username = user.name
            self.parent.bncs.enter_chat(self.username, get_statstring(user.attributes))
        else:
            if user.id in self.users:
                changes = False

                # Actually an update
                if flags or attributes:
                    eid = bncs.EID_USERFLAGS

                    if flags and user.flags != flags:
                        user.flags = flags
                        changes = True
                    if attributes:
                        old_attr = user.attributes
                        user.set_attributes(attributes)
                        if user.attributes != old_attr:
                            changes = True
                elif user.id == 1 and not self._received_users:
                    # It's us so we can switch to joins instead of show user
                    eid = bncs.EID_SHOWUSER
                    self._received_users = True
                    changes = True
                else:
                    eid = None      # Satisfies an assignment check

                if not changes:
                    # It's an update where nothing changed??
                    self.parent.print("Received user update with no changes")
                    return
            else:
                eid = bncs.EID_JOIN if self._received_users else bncs.EID_SHOWUSER

            # Relay the event
            self.parent.bncs.send_chat(eid, user.name, user.get_statstring(), user.get_flags())

        self.users[user.id] = user
        if len(user.attributes) > 0:
            if len(user.attributes) > 1 or "ProgramId" not in user.attributes:
                self.parent.print("Attribute(s) found for user '%s': %s" % (user.name, attributes))

    def _handle_user_leave_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        if user:
            self.parent.bncs.send_chat(bncs.EID_LEAVE, user.name, '', get_flag_int(user.flags))
            del self.users[user.id]
        else:
            self.parent.print("Received leave event for unknown user")

    def _handle_message_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        mtype = response.get("type")
        message = response.get("message")

        eid = message_eids.get(mtype.lower())
        if eid is not None:
            flags = get_flag_int(user.flags)
            # String encoding problems... try UTF-8, then latin-1 and use character replacing
            try:
                self.parent.bncs.send_chat(eid, user.name, message, flags)
            except UnicodeEncodeError:
                self.parent.bncs.send_chat(eid, user.name, message, flags,
                                           encoding='latin-1', errors=self.parent.server.encoding_errors)
        else:
            self.parent.print("Unrecognized chat message type (%s: %s)" % (mtype, message))

    def _handle_send_whisper_response(self, request, response, error):
        if error:
            self.parent.error("Whisper not sent: %s" % error)
        else:
            target = self.get_user(request.get("user_id"))
            message = request.get("message")
            if target:
                self.parent.bncs.send_chat(bncs.EID_WHISPERSENT, target.name, message)
