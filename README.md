# capidaptor
Python proxy server that allows legacy BNETv1 binary clients to connect to the new BNET chat API.

Currently supports CAPI v3.

# Requirements
- Python 3.5
- The '`websocket-client`' package from pip.

# Usage
### Installation
1. Install Python v3.5 or newer: https://www.python.org/
2. Run setup.py - `python setup.py install` (this will install the single dependency)
3. If running this on a Linux-like environment, it is recommended you add the command-line argument `--user` to the above.

### Running
1. Run main.py - `python main.py`. The server will listen by default on all interfaces, port 6112.
2. Set your bot to use one of the supported products: `STAR, SEXP, D2DV, D2XP, WAR3, W3XP, W2BN, DRTL, DSHR`
3. Set your bot's username to your API key, and the server to the address of the computer running this program.
4. Connect your bot.

### Command-Line Arguments
The program supports a few optional command-line arguments:
* `--interface interface[:port]` - changes the network interface that the server listens on. Default is all interfaces.
* `--ignore-unsupported` - silently ignores normal Battle.net commands that are not supported by the chat API instead of returning an error message.
* `--debug` - enables debugging mode which shows sent and received packets from both BNCS and CAPI as well as commands.
* `--do-version-check` - requests a version check from connecting clients instead of attempting to skip the process. The response to the check still doesn't matter.

# Limitations
### Functional
* The chat API is not product-aware, so everyone will appear as being on the CHAT (Telnet Chat) product.
* The chat API does not support changing channels, whispering people in different channels, or banning users that are not in the channel.
* Most of the traditional slash-commands are not supported. *Supported commands are: /whisper, /emote/, /ban, /kick, /unban, /designate, and their aliases.*
* The `/designate` command equivalent in the chat API also includes the functionality of the /rejoin command.

### Technical
* Since the API key is transmitted in plain text as a username, it can be intercepted or picked up in packet logs. If you believe your key was compromised, issue the `/register-bot` command from the account you originally registered the bot on to get a new one.
* Since the username field is traditionally limited to 15 characters, any client with a hard cutoff for this field will not work.
* The server will request an OLS login for all products, including ones that usually use NLS. NLS login requests will still be accepted, but the password hash cannot be confirmed since there are no accounts or stored passwords. The password that you send in either case does not matter.

# Tested Bots
* [StealthBot](https://github.com/stealthbot/StealthBot): **working**
* [SphtBot](https://davnit.net/islanti/readme.html): **working**
