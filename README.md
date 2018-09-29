# capidaptor
Python proxy server that allows legacy BNETv1 binary clients to connect to the new BNET chat API.

Currently supports CAPI v3.

# Requirements
- Python 3.5
- The '`websocket-client`' package from pip.

# Usage
### Installation
Run setup.py - `python setup.py install` (this will install the single dependency)

### Running
1. Run main.py - `python main.py`. The server will listen by default on all interfaces, port 6112.
2. Set your bot to use one of the supported products: `WAR3, D2DV, STAR`
3. Set your bot's username to your API key, and the server to the address of the computer running this program.
4. Connect your bot.

### Arguments
The program supports a few optional command-line arguments:
* `--interface interface[:port]` - changes the network interface that the server listens on. Default is all interfaces.
* `--ignore-unsupported` - silently ignores normal Battle.net commands that are not supported by the chat API instead of returning an error message.
* `--debug` - enables debugging mode which shows sent and received packets from both BNCS and CAPI as well as commands.

# Limitations
### Functional
* The chat API is not product-aware, so everyone will appear as being on the CHAT (Telnet Chat) product.
* The chat API does not support changing channels, whispering people in different channels, or banning users that are not in the channel.
* Most of the traditional slash-commands are not supported. *Supported commands are: /whisper, /emote/, /ban, /kick, /unban, /designate, and their aliases.*
* The `/designate` command equivalent in the chat API also includes the functionality of the /rejoin command.

### Technical
* The proxy is designed to be compatible with legacy clients without requiring changes. This means it still has you go through the version checking and password hashing mechanisms. It does not care what values you send in the responses, but they still have to be sent.
* The 128-byte server signature sent during client authentication cannot be spoofed, so this check will always fail. Any bot that has a hard shutoff here will not work.
* Since the API key is transmitted in plain text as a username, it can be intercepted or picked up in packet logs. If you believe your key was compromised, issue the `/register-bot` command from the account you originally registered the bot on to get a new one.
* Also since the username field is traditionally limited to 15 characters, any client with a hard cutoff for this field will not work.
* The server will request an OLS login for all products, including ones that usually use NLS. NLS login requests will be accepted, but the password hash cannot be confirmed since there are no accounts or stored passwords. The password that you send in either case does not matter.

# Tested Bots
[StealthBot](https://github.com/stealthbot/StealthBot): **working**

[SphtBot](https://davnit.net/islanti/readme.html): **working**
