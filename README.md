# ArkAgainstHumanity's Discord Bot Repo

### Features:

 * Can pull ARK server chat into discord channels
 * Allows sending messages to ARK chat (setup using Ark Server Tools, standalone support coming soon)
 * Can pull information from the server and display to a bot_commands channel
   * Online players
   * Current multiplier configs (read from server config to properly reflect boosted rates)
   * Performance Information (CPU/RAM)
   * Read logs and detect segfault crashes, alerting relevant channels


### Current ToDo list:

 * Add server update / mod update commands, restricting use to an admin channel
 * Make all of this configurable with an ini/yaml file
 * Add actual logging
 * Rely less on arkmanager for commands other than starting/stopping servers
 * Convert the bot into a class


### Notes
We wanted to disclaim that this bot was created and tailored to the ArkAgainstHumanity cluster. You are welcome to use parts of code from this repo but it will mostly not work without proper tuning. We will be moving to a more configurable and modular format as the code gets converted into a class. Use at your own risk.

With that said, this code is GPLv3, and the Steam API/RCON code can likely be used out of the box. It's probably similar to what the folks at battlemetrics are using :)

