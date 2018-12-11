# capidaptor
Transparent python proxy server that allows legacy BNETv1 binary clients to connect to the new BNET chat API.

Currently supports CAPI v3.

# How To Use (Basic)
1. Acquire an API key from Battle.net (the following needs to be done from the actual game for WarCraft 3).
   1. Login to the account that owns the channel you want to run a bot in and join the channel. You must have an email address registered to your account. If you do not have an email registered, use the `/set-email [email]` command.
   2. Use the `/register-bot` command from that account.
   3. Check your email for your API key.
2. Download capidaptor.exe from the [releases](https://github.com/Davnit/capidaptor/releases) page.
3. Run your bot and set the following settings:
   * Server: *localhost*
   * Username: *your API key*
   * Password: *1234* (it doesn't matter it won't be used at all)
   * Product: *Diablo Retail (DRTL)* if available otherwise choose a product that you have a valid CD key for (it won't be used) and put that in for your CD key.
   * Connection method: *Local hashing* - (You do not need any hash files unless your bot checks for them before connecting. If it does you can either use BNLS - I recommend jbls.davnit.net - or put in some dummy files. They won't be used and their contents don't matter.)
4. Connect your bot. It should show something like this:
```
 [19:18:14] Connecting your bot...
 [19:18:14] [BNCS] Connecting to the Battle.net server at localhost...
 [19:18:14] [BNCS] Connected to 127.0.0.1!
 [19:18:15] [BNCS] Client version accepted!
 [19:18:15] [BNCS] Sending logon information...
 [19:18:15] [BNCS] Logon successful.
 [19:18:15] [BNCS] Logged on as [B]pyro[bot] using Telnet Chat.
 [19:18:15] -- Joined channel: clan bot --
```
and in the capidaptor window you should see something like this:
```
[Server] ThinBNCS server started - listening on port 6112
Client #1: Connected from 127.0.0.1
Client #1: BNCS login complete - authenticated to chat API
```

# Advanced Usage
You can also run the code yourself by installing python and downloading the source.
You'll need the following:
* [Python 3.5 or later](https://www.python.org/)
* The `websocket-client` package from PIP.

Run setup.py with `python setup.py install --user` to install the dependencies.

To run the program simply run main.py with `python main.py`

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
