#
# Copyright 2010 Nick Foster
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


import time, os, sys, socket
from string import split, join
import modes_parse
from datetime import *

class modes_output_sbs1(modes_parse.modes_parse):
  def __init__(self, mypos):
    modes_parse.modes_parse.__init__(self, mypos)
    self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._s.bind(('', 30003))
    self._s.listen(1)
    self._s.setblocking(0) #nonblocking
    self._conns = [] #list of active connections

  def output(self, msg):
    sbs1_msg = self.parse(msg)
    if sbs1_msg is not None:
      for conn in self._conns[:]: #iterate over a copy of the list
        try:
          conn.send(sbs1_msg)
        except socket.error:
          self._conns.remove(conn)
          print "Connections: ", len(self._conns)

  def add_pending_conns(self):
    try:
      conn, addr = self._s.accept()
      self._conns.append(conn)
      print "Connections: ", len(self._conns)
    except socket.error:
      pass

  def __del__(self):
    self._s.close()
            
  def parse(self, message):
    #assembles a SBS-1-style output string from the received message
    #this version ignores anything that isn't Type 17 for now, because we just don't care

    [msgtype, shortdata, longdata, parity, ecc, reference, time_secs, time_frac] = message.split()

    shortdata = long(shortdata, 16)
    longdata = long(longdata, 16)
    parity = long(parity, 16)
    ecc = long(ecc, 16)
#	reference = float(reference)

    msgtype = int(msgtype)

    outmsg = None

    if msgtype == 17:
        outmsg = self.pp17(shortdata, longdata, parity, ecc)

    return outmsg

  def pp17(self, shortdata, longdata, parity, ecc):
    icao24 = shortdata & 0xFFFFFF	
    subtype = (longdata >> 51) & 0x1F

    retstr = None
    timenow = datetime.now()
    datestr = timenow.strftime("%Y/%m/%d")
    timestr = timenow.strftime("%H:%M:%S.000") #we'll get better timestamps later, hopefully with actual VRT time in them

    if subtype == 4:
      msg = self.parseBDS08(shortdata, longdata, parity, ecc)
      retstr = "MSG,1,0,0,%X,0,%s,%s,%s,%s,%s,,,,,,,,,,,\n" % (icao24, datestr, timestr, datestr, timestr, msg)

    elif subtype >= 5 and subtype <= 8:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(shortdata, longdata, parity, ecc)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,3,0,0,%X,0,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\n" % (icao24, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif subtype >= 9 and subtype <= 18 and subtype != 15: #i'm eliminating type 15 records because they don't appear to be valid position reports.
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(shortdata, longdata, parity, ecc)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,3,0,0,%X,0,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\n" % (icao24, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif subtype == 19:
      subsubtype = (longdata >> 48) & 0x07
      if subsubtype == 0:
        [velocity, heading, vert_spd] = self.parseBDS09_0(shortdata, longdata, parity, ecc)
        retstr = "MSG,4,0,0,%X,0,%s,%s,%s,%s,,,%.1f,%.1f,,,%i,,,,,\n" % (icao24, datestr, timestr, datestr, timestr, velocity, heading, vert_spd)

      elif subsubtype == 1:
        [velocity, heading, vert_spd] = self.parseBDS09_1(shortdata, longdata, parity, ecc)
        retstr = "MSG,4,0,0,%X,0,%s,%s,%s,%s,,,%.1f,%.1f,,,%i,,,,,\n" % (icao24, datestr, timestr, datestr, timestr, velocity, heading, vert_spd)

    #else:
      #print "debug (modes_sbs1): unknown subtype %i with data %x %x %x\n" % (subtype, shortdata, longdata, parity,)

    return retstr
