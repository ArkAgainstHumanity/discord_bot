from pyarkon import RCONClient
from pysteamapi import SteamInfo

# RCON example
test = RCONClient("127.0.0.1", 27015, "password")
test.connect()
blah = test.send_command(command="listplayers")
print("Recv: " + repr(blah))
blah = test.send_command(command="saveworld")
print("Recv: " + repr(blah))
blah = test.send_command(command="SetMessageOfTheDay Our server is awesome!")
print("Recv: " + repr(blah))
blah = test.send_command(command="ShowMessageOfTheDay")
print("Recv: " + repr(blah))
test.disconnect()

# Steam API example
stuff = SteamInfo("127.0.0.1", 27015)
print(stuff.get_player_info())
print(stuff.get_all_steam_info())
stuff.close()
