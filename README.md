# capidaptor
Allows legacy BNETv1 binary clients to connect to the new BNET chat API.

Currently supports CAPI v3.

# Requirements
- Python 3.5
- The '`websocket-client`' package from pip.

# Usage
1. Run main.py. The server will listen by default on all interfaces, port 6112.
2. Set your bot's product to WarCraft 3 (`WAR3`), the username to your API key, and the server to the address of the computer running this program.
3. Connect your bot.

# Limitations
### Functional
* Only WarCraft 3 and its expansion are currently supported. More products may be added in the future.
* The chat API is not product-aware, so everyone will appear as being on the CHAT (Telnet Chat) product.
* The chat API does not support changing channels, whispering people in different channels, or banning users that are not in the channel.
* Most of the traditional slash-commands are not supported. *Supported commands are: /whisper, /emote/, /ban, /kick, /unban, /designate, and their aliases.*
* The `/designate` command equivalent in the chat API also includes the functionality of the /rejoin command.

### Technical
* The proxy is designed to be compatible with legacy clients without requiring changes. This means it still has you go through the version checking and password hashing mechanisms. It does not care what values you send in the responses, but they still have to be sent.
* The 128-byte server signature sent during client authentication cannot be spoofed, so this check will always fail. Any bot that has a hard shutoff here will not work.
* Since the server does not maintain a database of passwords or accounts, it can't prove to the client that it knows their password. This check will also always fail, along with any clients that force validate it. (This may be changed in the future.)
* Since the API key is transmitted in plain text as a username, it can be intercepted or picked up in packet logs. If you believe your key was compromised, issue the `/register-bot` command from the account you originally registered the bot on to get a new one.
* Also since the username field is traditionally limited to 15 characters, any client with a hard cutoff for this field will not work.

# Tested Bots
[StealthBot](https://github.com/stealthbot/StealthBot)
