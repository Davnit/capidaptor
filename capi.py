
import ssl
import json
from threading import Thread

import websocket

import bncs


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


class CapiUser(object):
    def __init__(self, user_id, name, flags=None, attributes=None):
        self.id = user_id
        self.name = name
        self.flags = flags or []
        self.attributes = attributes or {}


class CapiClient(Thread):
    def __init__(self, parent, endpoint=None):
        self.parent = parent
        self.endpoint = endpoint or "wss://connect-bot.classic.blizzard.com/v1/rpc/chat"
        self.api_key = None

        self.connected = False
        self.channel = None
        self.username = None

        self._last_request_id = 0
        self._requests = {}
        self._received_users = False
        self._users = {}

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

        self.socket = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
        super().__init__()
        self.daemon = True

    def get_user(self, identifier):
        # Identifier can be user id or toon name
        if isinstance(identifier, int):
            return self._users.get(identifier)
        elif isinstance(identifier, str):
            if identifier.startswith("*"):
                identifier = identifier[1:]

            for user in self._users.values():
                if user.name.lower() == identifier.lower():
                    return user
        return None

    def disconnect(self, reason=None):
        self.send_command("Botapichat.DisconnectRequest")
        self.parent.close(reason)

    def send_command(self, command, payload=None):
        rid = self._last_request_id = (self._last_request_id + 1)

        msg = {
            "command": command,
            "request_id": rid,
            "payload": payload or {}
        }

        try:
            self.socket.send(json.dumps(msg), websocket.ABNF.OPCODE_TEXT)
            self.parent.debug("Sent CAPI command: %s" % command)
        except websocket.WebSocketException as err:
            self.disconnect(str(err))
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
                else:
                    payload["user_id"] = user.id

            self.send_command(send_message_types.get(mtype), payload)

    def bankickunban(self, target, action="ban"):
        user = self.get_user(target)
        if action.lower() != "unban" and user is None:
            self.parent.error(bncs.ERROR_NOTLOGGEDON)
        else:
            action = bku_actions.get(action.lower())
            if action is None:
                raise ValueError("Invalid ban/kick/unban action - must be %s" % ', '.join(bku_actions.keys()))

            payload = {"toon_name": target} if user is None else {"user_id": user.id}
            self.send_command(action, payload)

    def run(self):
        while self.socket.connected:
            msg = self.socket.recv()
            if len(msg) == 0:
                break

            obj = json.loads(msg)

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
                    self._handlers.get(command)(request, payload, status)

        self.disconnect("Chat API thread exited")

    def authenticate(self, api_key):
        self.api_key = api_key

        self.socket.connect(self.endpoint)
        self.connected = True

        self.send_command("Botapiauth.AuthenticateRequest", {"api_key": api_key})
        self.start()

    def _handle_auth_response(self, request, response, error):
        if error:
            self.parent.bncs.send_logon_response(str(error))
            self.disconnect("CAPI authentication failed: %s" % error)
        else:
            # Login successful
            self.parent.bncs.send_logon_response(0x00)

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
        attributes = response.get("attributes")
        flags = response.get("flag")

        user = self.get_user(user_id) or CapiUser(user_id, toon_name, flags, attributes)

        if not self.channel:
            # We're not in a channel yet, so this should be our own info.
            self.username = user.name
            self.parent.bncs.enter_chat(self.username, account=self.api_key)
        else:
            if user.id in self._users:
                # Actually an update
                if (flags and user.flags != flags) or (attributes and user.attributes != attributes):
                    eid = bncs.EID_USERFLAGS

                    if flags:
                        user.flags = flags
                    if attributes:
                        user.attributes = attributes
                elif user.id == 1:
                    # It's us so we can switch to joins instead of show user
                    eid = bncs.EID_SHOWUSER
                    self._received_users = True
                else:
                    # It's an update where nothing changed??
                    self.parent.print("Received user update with no changes")
                    return
            else:
                eid = bncs.EID_JOIN if self._received_users else bncs.EID_SHOWUSER

            # Relay the event
            self.parent.bncs.send_chat(eid, user.name, bncs.PROD_CHAT, get_flag_int(user.flags))

        self._users[user.id] = user
        if len(user.attributes) > 0:
            self.parent.print("Attributes found for user '%s': %s" %
                              (user.name, ', '.join("%s = %s" % (k, v) for k, v in user.attributes.items())))

    def _handle_user_leave_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        if user:
            self.parent.bncs.send_chat(bncs.EID_LEAVE, user.name, bncs.PROD_CHAT, get_flag_int(user.flags))
            del self._users[user.id]
        else:
            self.parent.print("Received leave event for unknown user")

    def _handle_message_event(self, request, response, error):
        user = self.get_user(response.get("user_id"))
        mtype = response.get("type")
        message = response.get("message")

        eid = message_eids.get(mtype.lower())
        if eid is not None:
            self.parent.bncs.send_chat(eid, user.name, message, get_flag_int(user.flags))
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
