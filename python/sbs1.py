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
import air_modes
from datetime import *
from air_modes.exceptions import *

class output_sbs1(air_modes.parse):
  def __init__(self, mypos, port):
    air_modes.parse.__init__(self, mypos)
    self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self._s.bind(('', port))
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
      minimum = min(self._aircraft_id_map.values()) + (len(self._aircraft_id_map) - 1e4)
      for icao, _id in self._aircraft_id_map:
        if _id < minimum:
            del self._aircraft_id_map[icao]

    # Finally return the new pair
    return self._aircraft_id_count

  def output(self, msg):
    try:
      sbs1_msg = self.parse(msg)
      if sbs1_msg is not None:
        for conn in self._conns[:]: #iterate over a copy of the list
          conn.send(sbs1_msg)
    except socket.error:
      self._conns.remove(conn)
      print "Connections: ", len(self._conns)
    except ADSBError:
      pass

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
      return "1,0,1,"
    elif fs == 5:
      return "0,0,1,"
    else:
      return ",,,"

  def parse(self, message):
    #assembles a SBS-1-style output string from the received message

    [data, ecc, reference, timestamp] = message.split()

    data = air_modes.modes_reply(long(data, 16))
    ecc = long(ecc, 16)
    msgtype = data["df"]
    outmsg = None

    if msgtype == 0:
      outmsg = self.pp0(data, ecc)
    elif msgtype == 4:
      outmsg = self.pp4(data, ecc)
    elif msgtype == 5:
      outmsg = self.pp5(data, ecc)
    elif msgtype == 11:
      outmsg = self.pp11(data, ecc)
    elif msgtype == 17:
      outmsg = self.pp17(data)
    else:
      raise NoHandlerError(msgtype)
    return outmsg

  def pp0(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [vs, cc, sl, ri, altitude] = self.parse0(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,7,0,%i,%06X,%i,%s,%s,%s,%s,,%s,,,,,,,,,," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr, altitude)
    if vs:
      retstr += "1\r\n"
    else:
      retstr += "0\r\n"
    return retstr

  def pp4(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [fs, dr, um, altitude] = self.parse4(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,5,0,%i,%06X,%i,%s,%s,%s,%s,,%s,,,,,,," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr, altitude)
    return retstr + self.decode_fs(fs) + "\r\n"

  def pp5(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [fs, dr, um, ident] = self.parse5(shortdata)
    aircraft_id = self.get_aircraft_id(ecc)
    retstr = "MSG,6,0,%i,%06X,%i,%s,%s,%s,%s,,,,,,,,%04i," % (aircraft_id, ecc, aircraft_id+100, datestr, timestr, datestr, timestr, ident)
    return retstr + self.decode_fs(fs) + "\r\n"

  def pp11(self, shortdata, ecc):
    [datestr, timestr] = self.current_time()
    [icao24, interrogator, ca] = self.parse11(shortdata, ecc)
    aircraft_id = self.get_aircraft_id(icao24)
    return "MSG,8,0,%i,%06X,%i,%s,%s,%s,%s,,,,,,,,,,,,\r\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr)

  def pp17(self, data):
    icao24 = data["aa"]
    aircraft_id = self.get_aircraft_id(icao24)
    bdsreg = data["me"].get_type()

    retstr = None
    #we'll get better timestamps later, hopefully with actual VRT time
    #in them
    [datestr, timestr] = self.current_time()

    if bdsreg == 0x08:
      # Aircraft Identification
      (msg, typestring) = self.parseBDS08(data)
      retstr = "MSG,1,0,%i,%06X,%i,%s,%s,%s,%s,%s,,,,,,,,,,,\r\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, msg)

    elif bdsreg == 0x06:
      # Surface position measurement
      [ground_track, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(data)
      altitude = 0
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,2,0,%i,%06X,%i,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\r\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif bdsreg == 0x05:
      # Airborne position measurements
      # WRONG (rnge, bearing), is this still true?
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(data)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "MSG,3,0,%i,%06X,%i,%s,%s,%s,%s,,%i,,,%.5f,%.5f,,,,0,0,0\r\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, altitude, decoded_lat, decoded_lon)

    elif bdsreg == 0x09:
      # Airborne velocity measurements
      # WRONG (heading, vert_spd), Is this still true?
      subtype = data["bds09"].get_type()
      if subtype == 0 or subtype == 1:
        parser = self.parseBDS09_0 if subtype == 0 else self.parseBDS09_1
        [velocity, heading, vert_spd] = parser(data)
        retstr = "MSG,4,0,%i,%06X,%i,%s,%s,%s,%s,,,%.1f,%.1f,,,%i,,,,,\r\n" % (aircraft_id, icao24, aircraft_id+100, datestr, timestr, datestr, timestr, velocity, heading, vert_spd)

    return retstr
