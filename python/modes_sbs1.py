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
    self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self._s.bind(('', 30003))
    self._s.listen(1)
    self._s.setblocking(0) #nonblocking
    self._conns = [] #list of active connections
    self._aircraft_id_map = {} # dictionary of icao24 to aircraft IDs
    self._aircraft_id_count = 0 # Current Aircraft ID count

  def __del__(self):
    self._s.close()

  def get_aircraft_id(self, icao24):
    if icao24 in self._aircraft_id_map:
      return self._aircraft_id_map[icao24]

    # Adding this new ID to the dictionary
    self._aircraft_id_count += 1
    self._aircraft_id_map[icao24] = self._aircraft_id_count

    # Checking to see if we need to clean up in the event that the
    # dictionary is getting too large.
    if len(self._aircraft_id_map) > 1e4:
      minimum = ('', self._aircraft_id_count)
      for pair in self._aircraft_id_map:
        if pair[1] < minimum[1]:
          minimum = pair
      self._aircraft_id_map.pop(minimum[0])

    # Finally return the new pair
    return self._aircraft_id_count

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

  def current_time(self):
    timenow = datetime.now()
    return [timenow.strftime("%Y/%m/%d"), timenow.strftime("%H:%M:%S.%f")[0:-3]]

  def decode_fs(self, fs):
    if fs == 0:
      return "0,0,0,0"
    elif fs == 1:
      return "0,0,0,1"
    elif fs == 2:
      return "1,0,0,0"
    elif fs == 3:
      return "1,0,0,1"
    elif fs == 4:
      return "1,0,0,"
    elif fs == 5:
      return "0,0,0,"
    else:
      return ",,,"

  def parse(self, message):
    #assembles a SBS-1-style output string from the received message

    [msgtype, shortdata, longdata, parity, ecc, reference, timestamp] = message.split()

    shortdata = long(shortdata, 16)
    longdata = long(longdata, 16)
    parity = long(parity, 16)
    ecc = long(ecc, 16)
    msgtype = int(msgtype)
    outmsg = None

    if msgtype == 0:
      outmsg = self.pp0(shortdata, ecc)
    elif msgtype == 4:
      outmsg = self.pp4(shortdata, ecc)
    elif msgtype == 5:
      outmsg = self.pp5(shortdata, ecc)
    elif msgtype == 11:
      outmsg = self.pp11(shortdata, ecc)
    elif msgtype == 17:
      outmsg = self.pp17(shortdata, longdata)
    return outmsg

  def pp0(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [vs, cc, sl, ri, altitude] = self.parse0(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,7,0,%i,%06X,%i,%s,%s,%s,%s,,%s,,,,,,,,,," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr, altitude)
    if vs:
      retstr += "1\n"
    else:
      retstr += "0\n"
    return retstr

  def pp4(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [fs, dr, um, altitude] = self.parse4(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,5,0,%i,%06X,%i,%s,%s,%s,%s,,%s,,,,,,," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr, altitude)
    return retstr + self.decode_fs(fs) + "\n"

  def pp5(self, shortdata, ecc):
    # I'm not sure what to do with the identiifcation shortdata & 0x1FFF
    [datestr, timestr] = self.current_time()
    [fs, dr, um] = self.parse5(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,6,0,%i,%06X,%i,%s,%s,%s,%s,,,,,,,,," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr)
    return retstr + self.decode_fs(fs) + "\n"

  def pp11(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [icao24, interrogator, ca] = self.parse11(shortdata, ecc)
    aircraft_id = self.get_aircraft_id(icao24)
    return "MSG,8,0,%i,%06X,%i,%s,%s,%s,%s,,,,,,,,,,,,\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr)

  def pp17(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF
    aircraft_id = self.get_aircraft_id(icao24)
    subtype = (longdata >> 51) & 0x1F

    retstr = None
    #we'll get better timestamps later, hopefully with actual VRT time
    #in them
    [datestr, timestr] = self.current_time()

    if subtype >= 1 and subtype <= 4:
      # Aircraft Identification
      (msg, typestring) = self.parseBDS08(shortdata, longdata)
      retstr = "MSG,1,0,%i,%06X,%i,%s,%s,%s,%s,%s,,,,,,,,,,,\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, msg)

    elif subtype >= 5 and subtype <= 8:
      # Surface position measurement
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(shortdata, longdata)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,2,0,%i,%06X,%i,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif subtype >= 9 and subtype <= 18 and subtype != 15:
      # Airborne position measurements
      # WRONG (rnge, bearing), is this still true?
      # i'm eliminating type 15 records because they don't appear to be
      # valid position reports.
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(shortdata, longdata)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,3,0,%i,%06X,%i,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif subtype == 19:
      # Airborne velocity measurements
      # WRONG (heading, vert_spd), Is this still true?
      subsubtype = (longdata >> 48) & 0x07
      if subsubtype == 0:
        [velocity, heading, vert_spd] = self.parseBDS09_0(shortdata, longdata)
        retstr = "MSG,4,0,%i,%06X,%i,%s,%s,%s,%s,,,%.1f,%.1f,,,%i,,,,,\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, velocity, heading, vert_spd)

      elif subsubtype == 1:
        [velocity, heading, vert_spd] = self.parseBDS09_1(shortdata, longdata)
        retstr = "MSG,4,0,%i,%06X,%i,%s,%s,%s,%s,,,%.1f,%.1f,,,%i,,,,,\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, velocity, heading, vert_spd)

    return retstr
