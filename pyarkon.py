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

import socket
import struct
import traceback

from random import getrandbits


class RCONClient(object):
    def __init__(self, host="", port="", password="", retries=10):
        self.host = host
        self.port = port
        self.password = password
        self.retries = retries
        self.connection = None
        self.is_authenticated = False

    def connect(self):
        print("Starting connection")
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.settimeout(15)
        unknown_log = False
        refused_log = False
        aborted_log = False
        while self.retries:
            try:
                self.connection.connect((self.host, self.port))
                print("Connection established!")
                return True
            except socket.timeout:
                self.retries -= 1
            except socket.error as e:
                if e.errno == 10061:
                    if not refused_log:
                        print("Connection was refused")
                        refused_log = True
                if e.errno == 10053:
                    if not aborted_log:
                        print("Connection was aborted")
                        aborted_log = True
                else:
                    print("Unknown error:\n" + traceback.format_exc())

            except Exception as e:
                self.retries -= 1
                if not unknown_log:
                    print("Unknown exception when connecting to RCON service:\n{}".format(e))
                    unknown_log = True
            if not self.retries:
                print("Exceeded the maximum connection retries for {}:{}, aborting.".format(self.host, self.port))

        return False

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def receive_and_parse_data(self, client_bytes=b"\x00\x00\x00\x00"):
        data = self.connection.recv(1024*12)
        if len(data) < 12:
            return None

        idx = 0
        size = struct.unpack("i", data[idx:idx+4])[0]
        idx += 4
        client_id = struct.unpack("4s", data[idx:idx+4])[0]
        idx += 4
        _ = struct.unpack("i", data[idx:idx+4])[0]  # Command, not needed for anything currently
        idx += 4
        packet_data = struct.unpack("{}s".format(size-10), data[idx:idx+size-10])[0]
        # TODO: Parse multi-packet, not sure if ARK's RCON service even uses multi-packet though...
        if not packet_data:
            pass

        idx += size - 10
        if client_bytes:
            if client_id != client_bytes:
                return b"-1"

        if packet_data:
            return packet_data

        return None

    def send_command(self, command=""):
        if not self.is_authenticated:
            print("Trying to authenticate")
            self.is_authenticated = True
            self.send_command(command=self.password)

        client_id = bytearray(getrandbits(8) for _ in range(4))
        packet_length = bytearray([12 + len(command) + 2, 00, 00, 00])
        bytes_command = bytearray(command, "utf8")

        data = bytearray()
        data += packet_length
        data += client_id
        if command == self.password:
            data.append(0x03)
        else:
            data.append(0x02)
        data += b"\x00\x00\x00"  # Padding for command type
        data += bytes_command    # The actual command
        data += b"\x00\x00"      # Termination
        if command == self.password:
            output = data.replace(bytes_command, b"_redacted_password_")
            print("Sent: " + repr(output))
        else:
            print("Sent: " + repr(data))

        self.connection.send(data)
        resp = self.receive_and_parse_data(client_bytes=client_id)

        if command == self.password:
            if resp == b"-1":
                print("Bad RCON password specified")
            else:
                print("RCON password accepted")

        if resp:
            return resp

        return None
