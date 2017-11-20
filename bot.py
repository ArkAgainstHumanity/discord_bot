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
import logging
import os
import re
import sys

from bs4 import BeautifulSoup
from configparser import ConfigParser
from discord.ext import commands
from multiprocessing import cpu_count
from pyarkon import RCONClient
from pysteamapi import SteamInfo
from requests import get
from subprocess import PIPE, Popen
from time import strftime

__author__ = "ArkAgainstHumanity"
__version__ = "0.41"

config = ConfigParser()
config_file = os.path.join(os.getcwd(), "conf", "bot.conf")
if not os.path.exists(config_file):
    print("Error: Config file does not exist at: {}".format(config_file))
    exit(1)

log = logging.getLogger(__name__)

config.read(config_file)
if config["discord"]["debug"].lower() == "yes":
    log.setLevel(logging.DEBUG)
else:
    log.setLevel(logging.INFO)

log_type = config["discord"]["logging"]
if log_type.lower() == "file":
    config_log_file = config["discord"]["logfile"]
    if config_log_file.startswith("/"):
        base_path = "/".join(config_log_file.split("/")[0:-1])
        if os.path.exists(base_path) and os.path.isdir(base_path):
            if not os.path.exists(config_log_file):
                open(config_log_file, "w+").close()
        else:
            print("Error: Log path {} does not exist, please create it first".format(base_path))
            exit(1)

    else:
        base_path = os.path.join(os.getcwd(), "log")
        if not os.path.exists(base_path):
            os.mkdir(base_path)

        config_log_file = os.path.join(base_path, config_log_file)
        open(config_log_file, "a").close()

    handler = logging.FileHandler(config_log_file)
    formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)

elif log_type.lower() == "stdout":
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(message)s")
    handler.setFormatter(formatter)
    log.addHandler(handler)

bot = commands.Bot(command_prefix="!")
# We'll make our own help command
bot.remove_command("help")

VERSION = re.compile(" \d{7,9} ")
PATCH_VERSION = re.compile("^v\d{3,4}\.\d{1,5}$")
CPU_COUNT = cpu_count()


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
                # do not concat the segment to the last line of new chunk
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


def remove_html_markup(s):
    # From: https://stackoverflow.com/a/14464496
    tag = False
    quote = False
    out = ""

    for c in s:
            if c == '<' and not quote:
                tag = True
            elif c == '>' and not quote:
                tag = False
            elif (c == '"' or c == "'") and tag:
                quote = not quote
            elif not tag:
                out = out + c

    return out


def get_rcon_info_from_settings(file_path):
    # We can't use ConfigParser for GameUserSettings.ini in the instances of having
    # duplicate keys. (Like multiple OverrideNamedEngramEntries)
    ret = {"port": None, "password": None}
    with open(file_path, "r") as settings_file:
        for line in settings_file:
            if line.startswith("RCONPort"):
                ret["port"] = line.split("=")[-1].strip()

            elif line.startswith("ServerAdminPassword"):
                ret["password"] = line.split("=")[-1].strip()

            if ret["port"] and ret["password"]:
                return ret

    return {}


async def check_world_crashes():
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    server_object = discord.utils.get(bot.servers, name=config["discord"]["server_name"])
    if not server_object:
        return None

    last_path = os.path.join(os.getcwd(), "log", "crashlog")
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
            with open(last_path, "w+") as lfile:
                lfile.write(next_last_message)

        await asyncio.sleep(60)

    return None


async def pull_world_chats():
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    server_object = discord.utils.get(bot.servers, name=config["discord"]["server_name"])
    if not server_object:
        return None

    """ Dict structure containing the map name as the key and the value
        being a Discord object for the channel to store chat logs in.
    """
    maps = {}
    for current_map in config["servers"]:
        maps[current_map] = config[current_map]["discord_channel"]

    while not bot.is_closed:
        # Iterate the maps and check for new chat messages to send to discord
        for current_map in maps:
            chats = []
            server_base = config[current_map]["server_path"]
            game_config_file = os.path.join(server_base, "ShooterGame", "Saved", "Config", "LinuxServer",
                                            "GameUserSettings.ini")

            server_ip = config[current_map]["server_ip"]
            rcon_info = get_rcon_info_from_settings(game_config_file)
            if not rcon_info:
                log.error("Unable to get RCON Port/Password")
                return False
            rcon = RCONClient(server_ip, int(rcon_info["port"]), rcon_info["password"])
            rcon.connect()
            chat_buffer = rcon.send_command(command="getchat")
            rcon.disconnect()
            if chat_buffer:
                # No chat logs to get!
                if chat_buffer == b"Server received, But no response!! \n ":
                    continue

                current_string = ""
                for byte in chat_buffer:
                    if byte == 10:  # New line
                        if current_string and current_string.strip():
                            chats.append(current_string)
                        current_string = ""
                    else:
                        if 31 < byte < 127:
                            # ASCII, just convert it
                            current_string += chr(byte)
                        else:
                            # Probably some unicode character, hex escape it
                            current_string += hex(byte).replace("0x", "\\x")
            if chats:
                for msg in chats:
                    chat_log = config[current_map]["save_chat"]
                    # Log here so we can log admin commands as well
                    if chat_log and chat_log.lower() == "yes":
                        chat_base_path = os.path.join(os.getcwd(), "log")
                        os.makedirs(chat_base_path, exist_ok=True)
                        out_file = os.path.join(chat_base_path, "{}-chat.txt".format(current_map))
                        with open(out_file, "a+") as chat_log_file:
                            chat_log_file.write("{} {}\n".format(strftime("[%Y/%m/%d %H:%M:%S]"), msg))
                    # Ignore a bunch of non-chat related server events in the 'getchat' RCON command
                    if msg.startswith(("AdminCmd: ", "SERVER: ", "Command processed")):
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
                    # Add a timestamp, and convert the message to a 'pre-block' for Discord
                    msg = "```{} {}```".format(strftime("[%Y/%m/%d %H:%M:%S]"), msg)
                    # Send the chat to discord!
                    channel_name = config[current_map]["discord_channel"]
                    channel_object = discord.utils.get(server_object.channels, name=channel_name)
                    await bot.send_message(channel_object, msg)

        await asyncio.sleep(15)


async def check_new_patch_notes():
    await bot.wait_until_ready()
    await asyncio.sleep(10)
    server_object = discord.utils.get(bot.servers, name=config["discord"]["server_name"])
    if not server_object:
        return None

    channel_object = discord.utils.get(server_object.channels, name="patch_notes")
    while not bot.is_closed:
        r = get("https://steamcommunity.com/app/346110/discussions/0/594820656447032287/")
        soup = BeautifulSoup(r.text, "html.parser")
        post = soup.find("div", class_="forum_op")
        data = post.find("div", class_="content").contents
        # TODO: Handle first-run file creation and add config settings
        with open(os.path.join(os.getcwd(), "log", "versionlog"), "r") as vfile:
            last_version = vfile.read()

        output = ""
        start_parse = False
        for line in data:
            tmp = remove_html_markup(line)
            if tmp:
                if PATCH_VERSION.match(tmp):
                    if output:
                        output = "```\n" + output + "\n```"
                        await bot.send_message(channel_object, output)
                    if not start_parse:
                        start_parse = True
                    if start_parse:
                        output = ""
                        output += tmp
                        if tmp == last_version:
                            break
                else:
                    if start_parse:
                        output += "\n" + tmp

        await asyncio.sleep(900)


@bot.event
async def on_ready():
    log.info("Bot %s has successfully logged in." % bot.user.name)


@bot.command(pass_context=True)
async def checkupdate(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    config_admin_ids = config["discord"]["admin_ids"]
    admin_ids = []
    if config_admin_ids:
        admin_ids = config_admin_ids.split(",")

    admins = []
    server_object = discord.utils.get(bot.servers, name="Ark Against Humanity")
    if admin_ids:
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

    ports = {}
    for server in config["servers"]:
        query_port = int(config[server]["query_port"])
        ports[query_port] = server

    _online = {}
    total = 0
    for port in ports:
        conn = SteamInfo("142.44.142.79", port)
        players = {}
        online_players = conn.get_a2s_players()
        for player in online_players:
            if player["player_name"]:
                total += 1
                players[player["duration"]] = player["player_name"]

        _online[port] = players

    out = "Total Players Online: {}\n".format(total)
    for port in sorted(ports.keys()):
        out += "\n__**{}:**__ {}".format(ports.get(port), len(_online[port].keys()))
        for player in sorted(_online[port].keys(), reverse=True):
            m, s = divmod(int(player), 60)
            h, m = divmod(m, 60)
            out += "\n  *{}* has been online for: {}h {}m {}s".format(_online[port][player], h, m, s)

    await bot.say(out)
    return None


@bot.command(pass_context=True)
async def multipliers(ctx):
    channel = str(ctx.message.channel.name)
    if channel not in ["admins", "bot_commands"]:
        return None

    important_multipliers = (
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

    gameini = "/home/ark/arkservers/theisland/ShooterGame/Saved/Config/LinuxServer/Game.ini"
    with open(gameini, "r") as gamefile:
        data = gamefile.read()

    lines = []
    if data:
        for line in data.splitlines():
            if line.startswith(important_multipliers):
                lines.append(line)

    gameini = "/home/ark/arkservers/theisland/ShooterGame/Saved/Config/LinuxServer/GameUserSettings.ini"
    with open(gameini, "r") as gamefile:
        data = gamefile.read()

    if data:
        for line in data.splitlines():
            if line.startswith(important_multipliers):
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
            "[Load Average]({0} / {1}.00)\n\n"
            "[Memory Consumption]({2})\n"
            "[TheIsland]({3})\n"
            "[TheCenter]({4})\n"
            "[Scorched]({5})\n"
            "[Ragnarok]({6})\n"
            "[CrystalIsles]({7})".format(load, CPU_COUNT, memory, islandmem, centermem, scorchedmem, ragnarokmem,
                                         crystalmem)
        )
        output += "\n```"
        await bot.say(output)

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
bot.loop.create_task(check_new_patch_notes())
bot.run(config["discord"]["apikey"])
