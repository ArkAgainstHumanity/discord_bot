#!/usr/bin/python3.5
#
# Copyright (C) 2017 ArkAgainstHumanity
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import discord
import json
import os
import re

from discord.ext import commands
from subprocess import PIPE, Popen

__author__ = "ArkAgainstHumanity"
__version__ = "0.3"

bot = commands.Bot(command_prefix="!")
# We'll make our own help command
bot.remove_command("help")

VERSION = re.compile(" \d{7,9} ")


def reverse_readline(filename, buf_size=2048):
    """a generator that returns the lines of a file in reverse order"""
    with open(filename) as fh:
        segment = None
        offset = 0
        fh.seek(0, os.SEEK_END)
        file_size = remaining_size = fh.tell()
        while remaining_size > 0:
            offset = min(file_size, offset + buf_size)
            fh.seek(file_size - offset)
            buf = fh.read(min(remaining_size, buf_size))
            remaining_size -= buf_size
            lines = buf.split('\n')
            # the first line of the buffer is probably not a complete line so
            # we'll save it and append it to the last line of the next buffer
            # we read
            if segment is not None:
                # if the previous chunk starts right from the beginning of line
                # do not concact the segment to the last line of new chunk
                # instead, yield the segment first
                if buf[-1] is not '\n':
                    lines[-1] += segment
                else:
                    yield segment
            segment = lines[0]
            for index in range(len(lines) - 1, 0, -1):
                if len(lines[index]):
                    yield lines[index]
        # Don't yield None if the file was empty
        if segment is not None:
            yield segment


async def check_world_crashes():
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    server_object = discord.utils.get(bot.servers, name="Ark Against Humanity")
    if not server_object:
        return None

    last_path = os.path.join(os.getcwd(), "chat", "crashlog")
    crash_path = "/var/log/arktools/arkserver.log"
    general_chat = discord.utils.get(server_object.channels, name="general")
    admin_chat = discord.utils.get(server_object.channels, name="admins")
    while not bot.is_closed:
        first_run = False
        if not os.path.exists(last_path):
            first_run = True

        if not first_run:
            with open(last_path, "r") as lfile:
                last_message = lfile.read()
        else:
            last_message = ""

        next_last_message = ""

        if first_run:
            ctr = 0
            for line in reverse_readline(crash_path):
                if ctr < 1:
                    next_last_message = line
                if "Signal 11 caught" in line:
                    log_time, msg = line.split(": ")
                    bad_map = msg.split()[0].replace("[", "").replace("]", "")
                    desc = "{} crashed at {} UTC".format(bad_map, log_time)
                    embed = discord.Embed(title="Server Crash", description=desc, color=0xff0000)
                    await bot.send_message(general_chat, embed=embed)
                    await bot.send_message(admin_chat, embed=embed)
                    break
                ctr += 1
        else:
            ctr = 0
            for line in reverse_readline(crash_path):
                if line == last_message:
                    break
                if ctr < 1:
                    next_last_message = line
                if "Signal 11 caught" in line:
                    log_time, msg = line.split(": ")
                    bad_map = msg.split()[0].replace("[", "").replace("]", "")
                    desc = "{} crashed at {} UTC".format(bad_map, log_time)
                    embed = discord.Embed(title="Server Crash", description=desc, color=0xff0000)
                    await bot.send_message(general_chat, embed=embed)
                    await bot.send_message(admin_chat, embed=embed)
                ctr += 1

        if next_last_message:
            with open(last_path, "w") as lfile:
                lfile.write(next_last_message)

        await asyncio.sleep(60)

    return None

async def pull_world_chats():
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    server_object = discord.utils.get(bot.servers, name="Ark Against Humanity")
    if not server_object:
        return None

    """ Dict structure containing the map name as the key and the value
        being a tuple of:
            (Discord.channels Object, chat_log_path, last_log_path)
    """
    maps = {
        "theisland": (
            discord.utils.get(server_object.channels, name="server_theisland"),
            "/var/log/ark/chat/theisland_chat.txt",
            os.path.join(os.getcwd(), "chat", "theisland")
        ),
        "thecenter": (
            discord.utils.get(server_object.channels, name="server_thecenter"),
            "/var/log/ark/chat/thecenter_chat.txt",
            os.path.join(os.getcwd(), "chat", "thecenter"),
        ),
        "scorched": (
            discord.utils.get(server_object.channels, name="server_scorched"),
            "/var/log/ark/chat/scorched_chat.txt",
            os.path.join(os.getcwd(), "chat", "scorched")
        ),
        "ragnarok": (
            discord.utils.get(server_object.channels, name="server_ragnarok"),
            "/var/log/ark/chat/ragnarok_chat.txt",
            os.path.join(os.getcwd(), "chat", "ragnarok")
        ),
        "crystalisles": (
            discord.utils.get(server_object.channels, name="server_crystalisles"),
            "/var/log/ark/chat/crystalisles_chat.txt",
            os.path.join(os.getcwd(), "chat", "crystalisles")
        )
    }

    # Sanity check, for dev discord testing
    if not maps["theisland"][0]:
        return None

    while not bot.is_closed:
        # Iterate the maps and check for new chat messages to send to discord
        for current_map in maps:
            chats = []
            first_run = False
            if not os.path.exists(maps[current_map][2]):
                first_run = True

            # If this is not the first run, we know we've stored the last message previously
            if not first_run:
                with open(maps[current_map][2], "r") as lfile:
                    last_message = lfile.read()
            else:
                last_message = ""

            # If it is the first run, just load the last 10 lines
            if first_run:
                ctr = 0
                for line in reverse_readline(maps[current_map][1]):
                    if ctr == 10:
                        break
                    chats.append(line)
                    ctr += 1
            else:
                for line in reverse_readline(maps[current_map][1]):
                    # check if the message was the last known message and stop reading if it is
                    if line == last_message:
                        break
                    chats.append(line)
            if chats:
                # Store the last message if we had any
                with open(maps[current_map][2], "w") as lfile:
                    lfile.write(chats[0])
                # Reverse the order, since we are reading the file backwards
                for msg in chats[::-1]:
                    check = msg.split("]")
                    # Sanity check
                    if len(check) < 2:
                        continue
                    # Ignore Admin/Server command 'chat' logs
                    if check[1].startswith(("AdminCmd: ", "SERVER: ", "Command processed")):
                        continue
                    if all(x in msg for x in ["ERROR", "is requested but not installed", "arkmanager"]):
                        continue
                    if all(x in msg for x in ["ERROR", "Your SteamCMD", "not"]):
                        continue
                    if all(x in msg for x in ["ERROR", "You have not rights", "log directory"]):
                        continue
                    if all(x in msg for x in ["Running command", "for instance"]):
                        continue
                    # Sanitize the message
                    if "```" in msg:
                        msg = msg.replace("```", "'''")
                    msg = "```{}```".format(msg)
                    # Send the chat to discord!
                    await bot.send_message(maps[current_map][0], msg)

        # Sleep for 1 minute, since the chat logs are puller once per minute.
        await asyncio.sleep(60)


@bot.event
async def on_ready():
    print("Bot %s has successfully logged in." % bot.user.name)


@bot.command(pass_context=True)
async def checkupdate(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    admin_ids = [
        "_redacted_",
        "_redacted_",
        "_redacted_",
        "_redacted_",
        "_redacted_",
    ]
    admins = []
    server_object = discord.utils.get(bot.servers, name="Ark Against Humanity")
    for member in server_object.members:
        if str(member.id) in admin_ids:
            admins.append(member.mention)
    # Check for updates
    msg = await bot.say("Checking for update...")
    p = Popen(["arkmanager", "checkupdate", "@theisland"], stdout=PIPE)
    out = p.stdout.read()
    outputs = str(out).split("\\n")
    current = VERSION.findall(outputs[2])
    available = VERSION.findall(outputs[3])
    if outputs[4] == "Your server needs to be restarted in order to receive the latest update.":
        output = "Current Version:{0}\nAvailable Version:{1}\n{2}\n( {3} )".format(
            current[0], available[0], outputs[4], " ".join(admins))
    else:
        output = "Current Version:{0}\nAvailable Version:{1}\n{2}".format(current[0], available[0], outputs[4])

    await bot.edit_message(msg, "Checking for update...\n" + output)
    return None


@bot.command(pass_context=True)
async def online(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    p = Popen(["arkmanager", "rconcmd", "\"listplayers\"", "@all"], stdout=PIPE)
    out = p.stdout.read().decode("ascii")
    servers = {}
    total = 0
    parse = False
    for line in out.splitlines():
        if line.startswith("Running command"):
            server = line.split("'")[-2]
            servers[server] = []
            continue
        if line in ['"', ' "', '"No Players Connected ']:
            if parse:
                parse = False
            else:
                parse = True
            continue
        if parse:
            player = "".join(line[line.index(".")+2:].split(",")[:-1])
            servers[server].append(player)
            total += 1
    output = "```\nTotal Players Online: {0}\n".format(total)
    for server in servers:
        output += server + ": " + str(len(servers[server])) + "\n"
        for player in servers[server]:
            output += "    " + player + "\n"
    output += "\n```"
    await bot.say(output)
    return None


@bot.command(pass_context=True)
async def multipliers(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    multipliers = (
        "MatingIntervalMultiplier",
        "EggHatchSpeedMultiplier",
        "BabyMatureSpeedMultiplier",
        "BabyFoodConsumptionSpeedMultiplier",
        "LayEggIntervalMultiplier",
        "BabyCuddleIntervalMultiplier",
        "BabyCuddleGracePeriodMultiplier",
        "BabyCuddleLoseImprintQualitySpeedMultiplier",
        "CropDecaySpeedMultiplier",
        "HairGrowthSpeedMultiplier",
        "DinoCountMultiplier",
        "TamingSpeedMultiplier",
        "XPMultiplier",
        "HarvestAmountMultiplier",
    )
    # /home/ark/arkservers/theisland/ShooterGame/Saved/Config/LinuxServer
    gameini = "/home/ark/arkservers/theisland/ShooterGame/Saved/Config/LinuxServer/Game.ini"
    with open(gameini, "r") as gamefile:
        data = gamefile.read()

    lines = []
    if data:
        for line in data.splitlines():
            if line.startswith(multipliers):
                lines.append(line)

    gameini = "/home/ark/arkservers/theisland/ShooterGame/Saved/Config/LinuxServer/GameUserSettings.ini"
    with open(gameini, "r") as gamefile:
        data = gamefile.read()

    if data:
        for line in data.splitlines():
            if line.startswith(multipliers):
                lines.append(line)
    out = "```python\n{}\n```".format("\n".join(lines))
    await bot.say(out)
    return None


@bot.command(pass_context=True)
async def events(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    with open(os.path.join(os.getcwd(), "events.txt"), "r") as efile:
        data = efile.read()

    if data:
        await bot.say(data)

    return None


@bot.command(pass_context=True)
async def performance(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    p = Popen(["echo q | htop --sort-key PERCENT_MEM | aha --black --line-fix"], stdout=PIPE, shell=True)
    out = p.stdout.read().decode("ascii", "ignore").replace("\x0f", "")
    stripped = re.sub("<[^>]*>", "", out)
    load = ""
    memory = ""
    islandmem = "N/A"
    centermem = "N/A"
    scorchedmem = "N/A"
    ragnarokmem = "N/A"
    crystalmem = "N/A"
    allmem = False
    for line in stripped.splitlines():
        if not line.strip():
            continue
        if "Load average" in line:
            load = line.split(": ")[-1].split()[0]
        elif "Mem[" in line:
            memory = line[line.index("[")+1:line.index("]")].replace("|", "").lstrip()
        elif "ShooterGameServer TheIsland" in line:
            islandmem = line.split()[5]
        elif "ShooterGameServer TheCenter" in line:
            centermem = line.split()[5]
        elif "ShooterGameServer ScorchedEarth" in line:
            scorchedmem = line.split()[5]
        elif "ShooterGameServer Ragnarok" in line:
            ragnarokmem = line.split()[5]
        elif "ShooterGameServer Crystal" in line:
            crystalmem = line.split()[5]
        if load and ragnarokmem and scorchedmem and centermem and islandmem and crystalmem and memory:
            allmem = True

    if allmem:
        output = (
            "```markdown\n"
            "[Load Average]({0} / 12.00)\n\n"
            "[Memory Consumption]({1})\n"
            "[TheIsland]({2})\n"
            "[TheCenter]({3})\n"
            "[Scorched]({4})\n"
            "[Ragnarok]({5})\n"
            "[CrystalIsles]({6})".format(load, memory, islandmem, centermem, scorchedmem, ragnarokmem, crystalmem)
        )
        output += "\n```"
        await bot.say(output)
    else:
        missed = []
        if not load:
            missed.append("load")
        if not memory:
            missed.append("memory")
        if not islandmem:
            missed.append("island")
        if not centermem:
            missed.append("center")
        if not scorchedmem:
            missed.append("scorched")
        if not ragnarokmem:
            missed.append("ragnarok")
        if not crystalmem:
            missed.append("crystal")
        print("Missed: {}".format(",".join(missed)))
    return None


@bot.command(pass_context=True)
async def vote(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    out = (
        "ARKServers: (Vote requires website login)\n"
        "    <https://arkservers.net/1/name/asc/?term=ArkAgainstHumanity[PVEx3>\n\n"
        "TOP ARKServers: (Vote requires website login)\n"
        "    <https://toparkservers.com/1/search/?term=ArkAgainstHumanity%5BPVEx3>\n\n"
        "ARK-Servers: (Vote requires steam login)\n"
        "    <https://ark-servers.net/group/229/>"
    )
    await bot.say(out)
    return None


@bot.command(pass_context=True)
async def mods(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    out = (
        "Death Helper: "
        "<https://steamcommunity.com/sharedfiles/filedetails/changelog/566885854>\n"
        "Pet Finder: "
        "<https://steamcommunity.com/sharedfiles/filedetails/changelog/566887000>\n"
        "Stairs Mod with Rounded Walls: "
        "<https://steamcommunity.com/sharedfiles/filedetails/changelog/520879363>\n"
        "Structures Plus: "
        "<https://steamcommunity.com/sharedfiles/filedetails/changelog/731604991>\n"
        "Super Spyglass: "
        "<https://steamcommunity.com/sharedfiles/filedetails/changelog/793605978>\n"
        "Iso: Crystal Isles (Map, optional): "
        "<https://steamcommunity.com/sharedfiles/filedetails/?id=804312798>"
    )
    await bot.say(out)
    return None


@bot.command(pass_context=True)
async def getarkname(ctx):
    channel = str(ctx.message.channel.name)
    user_name = str(ctx.message.author.name)
    if channel not in ["bot_commands"]:
        return None

    user_id = str(ctx.message.author.id)
    user_file = os.path.join(os.getcwd(), "data", "users.json")
    with open(user_file, "r") as ufile:
        data = ufile.read()

    jdata = json.loads(data)
    if user_id in jdata:
        output = "{}: Your ARK chat name is {}.".format(user_name, jdata[user_id]["name"])
    else:
        output = "{}: You have not set an ARK chat name. Use !setarkname your_name to set one.".format(user_name)
    await bot.say(output)

    return None


@bot.command(pass_context=True)
async def setarkname(ctx, *args):
    channel = str(ctx.message.channel.name)
    user_name = str(ctx.message.author.name)
    if channel not in ["bot_commands", "admins"]:
        return None

    if len(args) > 1:
        await bot.say("{}: Looks like you have some spaces in your name, or tried to give me more than one :)".format(
            user_name
        ))
        return None

    if len(args) == 0:
        await bot.say("{}: Looks like you forgot to give me a name :)".format(user_name))
        return None

    user_id = str(ctx.message.author.id)
    name = args[0]

    charset = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789_-+=()[].,"
    )
    bad_chars = []
    for char in name:
        if char not in charset:
            bad_chars.append(char)
    if bad_chars:
        if len(bad_chars) == 1:
            output = "Sorry {}, the name {} is invalid due to the following character: {}".format(
                ctx.message.author.name, name, bad_chars[0]
            )
        else:
            output = "Sorry {}, the name {} is invalid due to the following characters: {}".format(
                ctx.message.author.name, name, ", ".join(bad_chars)
            )
        await bot.say(output)
        return None

    user_file = os.path.join(os.getcwd(), "data", "users.json")
    with open(user_file, "r") as ufile:
        data = ufile.read()

    jdata = json.loads(data)
    if user_id not in jdata:
        jdata[user_id] = {"name": name, "changes": 1}
        await bot.say("{}: Your ARK chat name has been set to {}. You can change this 1 time in the future "
                      "using this command.".format(user_name, name))
        with open(user_file, "w") as ufile:
            ufile.write(json.dumps(jdata))
        return None

    if jdata[user_id]["changes"] == 0:
        await bot.say("{}: You are not allowed to change your ARK chat name anymore".format(user_name))
        return None

    old_name = jdata[user_id]["name"]
    if old_name == name:
        await bot.say("{}: You can't change your name if it's the same!".format(user_name))
        return None

    jdata[user_id]["name"] = name
    jdata[user_id]["changes"] -= 1
    await bot.say("{}: You have changed your name from {} to {}.".format(user_name, old_name, name))
    with open(user_file, "w") as ufile:
        ufile.write(json.dumps(jdata))
    return None


@bot.command(pass_context=True)
async def say(ctx, *args):
    channel = str(ctx.message.channel.name)
    if not channel.startswith("server_"):
        return None

    out = " ".join(list(args))
    if "\\" in out or "\"" in out:
        await bot.say("Unable to send message as a restricted character was observed (\", \\)")
        return None

    user_file = os.path.join(os.getcwd(), "data", "users.json")
    with open(user_file, "r") as ufile:
        data = ufile.read()

    jdata = json.loads(data)
    user_name = str(ctx.message.author.name)
    user_id = str(ctx.message.author.id)
    if user_id not in jdata:
        await bot.say("{}: You have not set your ARK chat name. Do so by issuing a !setarkname your_name command "
                      "in the bot_commands channel.".format(user_name))

    name = jdata[user_id]["name"]
    server = "@{}".format(channel.replace("server_", ""))
    msg = "\"serverchat {}: {}\"".format(name, out)
    p = Popen(["arkmanager rconcmd {} {}".format(msg, server)], stdout=PIPE, shell=True)
    out = p.stdout.read().decode("ascii")
    if "Command processed" in out:
        await bot.add_reaction(ctx.message, "\U0001F44C")
    else:
        await bot.say("Unknown output: {}".format(out))
    return None

@bot.command(pass_context=True)
async def status(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    p = Popen(["arkmanager", "status", "@all"], stdout=PIPE)
    out = p.stdout.read().decode("ascii", "ignore").replace("\x0f", "")
    current = ""
    running = ""
    listening = ""
    servers = {}
    for line in out.splitlines():
        if "Running command" in line:
            current = line.split("'")[3]
        elif "Server running" in line:
            running = line.split(":")[1].split()[1]
        elif "Server listening" in line:
            listening = line.split(":")[1].split()[1]
        if current and running and listening:
            if running == "Yes" and listening == "Yes":
                servers[current] = discord.Embed(title=current, description="Server is online", color=0x00ff00)
            elif running == "Yes" and listening == "No":
                servers[current] = discord.Embed(title=current, description="Server is still booting", color=0xffff00)
            elif running == "No" and listening == "No":
                servers[current] = discord.Embed(title=current, description="Server is offline", color=0xff0000)
            current = ""
            running = ""
            listening = ""

    # Display server embeds in the same order in which we update
    await bot.say(embed=servers["theisland"])
    await bot.say(embed=servers["thecenter"])
    await bot.say(embed=servers["scorched"])
    await bot.say(embed=servers["ragnarok"])
    await bot.say(embed=servers["crystalisles"])

    return None


@bot.command(pass_context=True)
async def help(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    out = (
        "```Commands:\n"
        "!help          Shows this prompt\n"
        "!checkupdate   Checks for an update to the ARK server/maps (not mods)\n"
        "!online        Show who's online and on which server\n"
        "!multipliers   Show AAH's default configured multipliers\n"
        "!mods          Show links to mod changelog\n"
        "!events        Show any upcoming event(s)\n"
        "!performance   Check if you are crashing the server...\n"
        "!status        Display the status of the servers\n"
        "!vote          Show a list of places to vote for AAH servers\n"
        "!getarkname    Show the name that you set to be used for the !say command\n"
        "!setarkname    Set a name to be used for the !say command\n"
        "!say           A message to be sent to a server, only works in server_ channels\n"
        "\nPing us if you have any feature requests!```"
    )
    await bot.say(out)
    return None

bot.loop.create_task(pull_world_chats())
bot.loop.create_task(check_world_crashes())
bot.run("_Put_your_discord_api_key_here")