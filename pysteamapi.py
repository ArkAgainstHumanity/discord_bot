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

import struct

from socket import AF_INET, SOCK_DGRAM, socket


class SteamInfo(object):
    def __init__(self, host="", port=""):
        self.connect = (host, port)
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.settimeout(5)

    @staticmethod
    def parse_until_null(data, start_idx):
        output = ""
        for char in data[start_idx:]:
            if char == 0:
                end_idx = start_idx + len(output) + 1
                return output, end_idx
            else:
                output += chr(char)

    @staticmethod
    def get_version(data):
        version = ""
        for char in data[::-1][1:]:
            if char == "(":
                break
            version += char

        return version[::-1]

    def get_a2s_info(self):
        output = {}
        self.sock.sendto(b"\xff\xff\xff\xffTSource Engine Query\x00", self.connect)
        data = self.sock.recv(1024*12)
        if not data[0:5] == b"\xff\xff\xff\xff\x49":
            print("Error: unexpected A2S_INFO response")
            return output

        output["protocol"] = data[5]
        idx = 6
        sname, idx = self.parse_until_null(data, idx)
        sversion = self.get_version(sname)
        verlen = (len(sversion) + 5) * -1
        output["server_name"] = sname[:verlen]
        output["server_version"] = sversion
        output["server_map"], idx = self.parse_until_null(data, idx)
        output["server_folder"], idx = self.parse_until_null(data, idx)
        output["server_game"], idx = self.parse_until_null(data, idx)
        output["steam_id"] = str(struct.unpack("h", data[idx:idx + 2])[0])
        idx += 2
        players = data[idx]
        total_players = data[idx + 1]
        output["players"] = "{}/{}".format(players, total_players)
        idx += 2
        output["bots"] = str(data[idx])
        idx += 1
        server_type = data[idx]
        if server_type == 100:  # "d"
            output["server_type"] = "dedicated"
        elif server_type == 108:  # "l"
            output["server_type"] = "non-dedicated"
        elif server_type == 112:  # "p"
            output["server_type"] = "proxy"
        else:
            output["server_type"] = "unknown"
        idx += 1
        environment = data[idx]
        if environment == 108:  # "l"
            output["server_os"] = "linux"
        elif environment == 119:  # "w"
            output["server_os"] = "windows"
        elif environment in [109, 111]:  # "m" or "o"
            output["server_os"] = "mac"
        else:
            output["server_os"] = "unknown"
        idx += 1
        visible = data[idx]
        if visible == 1:
            output["password"] = "yes"
        elif visible == 0:
            output["password"] = "no"
        else:
            output["password"] = "unknown"
        idx += 1
        vac = data[idx]
        if vac == 1:
            output["vac_enforced"] = "yes"
        elif vac == 0:
            output["vac_enforced"] = "no"
        else:
            output["vac_enforced"] = "unknown"
        idx += 1
        edf = data[idx]
        if edf & 0x80:
            output["server_game_port"] = str(struct.unpack("h", data[idx:idx + 2])[0])
            idx += 2
        else:
            output["server_game_port"] = "none"
        if edf & 0x10:
            output["server_steam_id"] = str(struct.unpack("q", data[idx:idx + 8])[0])
            idx += 8
        else:
            output["server_steam_id"] = "none"
        if edf & 0x40:
            port = struct.unpack("h", data[idx:idx + 2])[0]
            idx += 2
            proxy_name, idx = self.parse_until_null(data, idx)
            output["sourcetv"] = {"proxy_name": proxy_name, "port": port}
        else:
            output["sourcetv"] = {}
        if edf & 0x20:
            future_use, idx = self.parse_until_null(data, idx)
            output["future_use"] = repr(future_use)
        else:
            output["future_use"] = "none"
        if edf & 0x01:
            output["game_id"] = str(struct.unpack("q", data[idx:idx + 8])[0])
            idx += 8
        else:
            output["game_id"] = "none"

        return output

    def get_a2s_rules(self):
        self.sock.sendto(b"\xff\xff\xff\xff\x56\x00\x00\x00\x00", self.connect)
        data = self.sock.recv(1024*12)
        if len(data) > 5 and data[0:5] == b"\xff\xff\xff\xff\x41":
            knock_resp = b"\xff\xff\xff\xff\x56" + data[-4:]
            self.sock.sendto(knock_resp, self.connect)
            data = self.sock.recv(1024 * 12)
            if len(data) > 5 and data[0:5] == b"\xff\xff\xff\xff\x45":
                idx = 5
                rules_count = struct.unpack("h", data[idx:idx + 2])[0]
                idx += 2
                rules = {}
                for item in range(rules_count):
                    rule_name, idx = self.parse_until_null(data, idx)
                    rule_value, idx = self.parse_until_null(data, idx)
                    if rule_name.startswith("MOD"):
                        mod_id, mod_hash = rule_value.split(":")
                        rules[rule_name] = {"mod_id": mod_id, "mod_hash": mod_hash}
                    elif rule_name.startswith(("ALLOWDOWNLOAD", "Networking", "OFFICIAL", "SESSIONIS")):
                        if rule_value == "0":
                            rule_value = "false"
                        elif rule_value == "1":
                            rule_value = "true"
                        rules[rule_name] = rule_value
                    else:
                        rules[rule_name] = rule_value

                return rules

            else:
                print("Error: unexpected A2S_RULES response")
        else:
            print("Error: unexpected A2S_RULES knock")

        return {}

    def get_a2s_players(self):
        self.sock.sendto(b"\xff\xff\xff\xff\x55\xff\xff\xff\xff", self.connect)
        data = self.sock.recv(1024*12)
        if len(data) > 5 and data[0:5] == b"\xff\xff\xff\xff\x41":
            print("Received A2S_PLAYER knock response, ACK'ing...")
            knock_resp = b"\xff\xff\xff\xff\x55" + data[-4:]
            self.sock.sendto(knock_resp, self.connect)
            data = self.sock.recv(1024 * 12)
            if len(data) > 5 and data[0:5] == b"\xff\xff\xff\xff\x44":
                print("Received A2S_PLAYER response")
                idx = 5
                player_count = data[idx]
                idx += 1
                players = []
                for item in range(player_count):
                    player = {}
                    player["index"] = data[idx]
                    idx += 1
                    player["player_name"], idx = self.parse_until_null(data, idx)
                    player["score"] = struct.unpack("l", data[idx:idx + 4])[0]
                    idx += 4
                    player["duration"] = struct.unpack("f", data[idx:idx + 4])[0]
                    idx += 4
                    players.append(player)
                return players

            else:
                print("Error: unexpected A2S_PLAYER response")
        else:
            print("Error: unexpected A2S_PLAYER knock")

        return {}

    def get_all_steam_info(self):
        return {
            "A2S_INFO": self.get_a2s_info(),
            "A2S_RULES": self.get_a2s_rules(),
            "A2S_PLAYERS": self.get_a2s_players()
        }

    def get_player_info(self):
        return self.get_a2s_players()

    def close(self):
        self.sock.close()
