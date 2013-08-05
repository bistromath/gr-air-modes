#!/usr/bin/env python
#
# Copyright 2012 Nick Foster
# 
# This file is part of gr-air-modes
# 
# gr-air-modes is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# gr-air-modes is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with gr-air-modes; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

#multilateration client
#outputs stamps to server, receives multilaterated outputs back

import socket, pickle, time, sys
import air_modes
from gnuradio import gr

pickle_prot = 0
#pickle_prot = pickle.HIGHEST_PROTOCOL

class client_info:
    def __init__(self):
        self.name = ""
        self.position = []
        self.offset_secs = 0
        self.offset_frac_secs = 0.0
        self.time_source = None  

class mlat_client:
    def __init__(self, queue, position, server_addr, time_source):
        self._queue = queue
        self._pos = position
        self._name = socket.gethostname()
        #connect to server
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(1)
        self._sock.connect((server_addr, 19005))
        info = client_info()
        info.name = self._name
        info.position = self._pos
        info.time_source = time_source #"gpsdo" or None
        self._sock.send(pickle.dumps(info))
        reply = self._sock.recv(1024)
        if reply != "HELO": #i know, shut up
            raise Exception("Invalid reply from server: %s" % reply)
        self._sock.setblocking(0)
        self._remnant = None

    def __del__(self):
        self._sock.close()

    #send a stamped report to the server
    def output(self, message):
        self._sock.send(message+"\n")

    #this is called from the update() method list of the main app thread
    def get_mlat_positions(self):
        msg = None
        try:
            msg = self._sock.recv(1024)
        except socket.error:
            pass
        if msg:
            for line in msg.splitlines(True):
                if line.endswith("\n"):
                    if self._remnant:
                        line = self._remnant + line
                        self._remnant = None
                    self._queue.insert_tail(gr.message_from_string(line))

                else:
                    if self._remnant is not None:
                        raise Exception("Malformed data: " + line)
                    else:
                        self._remnant = line
