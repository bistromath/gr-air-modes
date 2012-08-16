#
# Copyright 2010, 2012 Nick Foster
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

import time, os, sys
from string import split, join
import air_modes
from air_modes.exceptions import *
import math

class output_print(air_modes.parse):
  def __init__(self, mypos):
      air_modes.parse.__init__(self, mypos)
      
  def parse(self, message):
    [data, ecc, reference, timestamp] = message.split()

    ecc = long(ecc, 16)
    reference = float(reference)
    timestamp = float(timestamp)

    if reference == 0.0:
      refdb = -150.0
    else:
      refdb = 20.0*math.log10(reference)
    output = "(%.0f %.10f) " % (refdb, timestamp);

    try:
      data = air_modes.modes_reply(long(data, 16))
      msgtype = data["df"]
      if msgtype == 0:
        output += self.print0(data, ecc)
      elif msgtype == 4:
        output += self.print4(data, ecc)
      elif msgtype == 5:
        output += self.print5(data, ecc)
      elif msgtype == 11:
        output += self.print11(data, ecc)
      elif msgtype == 17:
        output += self.print17(data)
      elif msgtype == 20 or msgtype == 21:
        output += self.print20(data, ecc)
      else:
        output += "No handler for message type %i from %x (but it's in modes_parse)" % (msgtype, ecc)
      return output
    except NoHandlerError as e:
      output += "No handler for message type %s from %x" % (e.msgtype, ecc)
      return output
    except MetricAltError:
      pass
    except CPRNoPositionError:
      pass

  def output(self, msg):
      print self.parse(msg)

  def print0(self, shortdata, ecc):
    [vs, cc, sl, ri, altitude] = self.parse0(shortdata)
	
    retstr = "Type 0 (short A-A surveillance) from %x at %ift" % (ecc, altitude)
    if ri == 0:
      retstr += " (No TCAS)"
    elif ri == 2:
      retstr += " (TCAS resolution inhibited)"
    elif ri == 3:
      retstr += " (Vertical TCAS resolution only)"
    elif ri == 4:
      retstr += " (Full TCAS resolution)"
    elif ri == 9:
      retstr += " (speed <75kt)"
    elif ri > 9:
      retstr += " (speed %i-%ikt)" % (75 * (1 << (ri-10)), 75 * (1 << (ri-9)))

    if vs is True:
      retstr += " (aircraft is on the ground)"

    return retstr

  def print4(self, shortdata, ecc):

    [fs, dr, um, altitude] = self.parse4(shortdata)

    retstr = "Type 4 (short surveillance altitude reply) from %x at %ift" % (ecc, altitude)

    if fs == 1:
      retstr += " (aircraft is on the ground)"
    elif fs == 2:
      retstr += " (AIRBORNE ALERT)"
    elif fs == 3:
      retstr += " (GROUND ALERT)"
    elif fs == 4:
      retstr += " (SPI ALERT)"
    elif fs == 5:
      retstr += " (SPI)"

    return retstr

  def print5(self, shortdata, ecc):
    [fs, dr, um, ident] = self.parse5(shortdata)

    retstr = "Type 5 (short surveillance ident reply) from %x with ident %i" % (ecc, ident)

    if fs == 1:
      retstr += " (aircraft is on the ground)"
    elif fs == 2:
      retstr += " (AIRBORNE ALERT)"
    elif fs == 3:
      retstr += " (GROUND ALERT)"
    elif fs == 4:
      retstr += " (SPI ALERT)"
    elif fs == 5:
      retstr += " (SPI)"

    return retstr

  def print11(self, data, ecc):
    [icao24, interrogator, ca] = self.parse11(data, ecc)
    retstr = "Type 11 (all call reply) from %x in reply to interrogator %i with capability level %i" % (icao24, interrogator, ca+1)
    return retstr

  def print17(self, data):
    icao24 = data["aa"]
    bdsreg = data["me"].get_type()

    retstr = None

    if bdsreg == 0x08:
      (msg, typestring) = self.parseBDS08(data)
      retstr = "Type 17 BDS0,8 (ident) from %x type %s ident %s" % (icao24, typestring, msg)

    elif bdsreg == 0x06:
      [ground_track, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(data)
      retstr = "Type 17 BDS0,6 (surface report) from %x at (%.6f, %.6f) ground track %i" % (icao24, decoded_lat, decoded_lon, ground_track)
      if rnge is not None and bearing is not None:
        retstr += " (%.2f @ %.0f)" % (rnge, bearing)

    elif bdsreg == 0x05:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(data)
      retstr = "Type 17 BDS0,5 (position report) from %x at (%.6f, %.6f)" % (icao24, decoded_lat, decoded_lon)
      if rnge is not None and bearing is not None:
        retstr += " (" + "%.2f" % rnge + " @ " + "%.0f" % bearing + ")"
      retstr += " at " + str(altitude) + "ft"

    elif bdsreg == 0x09:
      subtype = data["bds09"].get_type()
      if subtype == 0:
        [velocity, heading, vert_spd, turnrate] = self.parseBDS09_0(data)
        retstr = "Type 17 BDS0,9-%i (track report) from %x with velocity %.0fkt heading %.0f VS %.0f turn rate %.0f" \
                 % (subtype, icao24, velocity, heading, vert_spd, turnrate)
      elif subtype == 1:
        [velocity, heading, vert_spd] = self.parseBDS09_1(data)
        retstr = "Type 17 BDS0,9-%i (track report) from %x with velocity %.0fkt heading %.0f VS %.0f" % (subtype, icao24, velocity, heading, vert_spd)
      elif subtype == 3:
        [mag_hdg, vel_src, vel, vert_spd, geo_diff] = self.parseBDS09_3(data)
        retstr = "Type 17 BDS0,9-%i (air course report) from %x with %s %.0fkt magnetic heading %.0f VS %.0f geo. diff. from baro. alt. %.0fft" \
                 % (subtype, icao24, vel_src, vel, mag_hdg, vert_spd, geo_diff)
    
      else:
        retstr = "Type 17 BDS0,9-%i from %x not implemented" % (subtype, icao24)

    elif bdsreg == 0x62:
      emerg_str = self.parseBDS62(data)
      retstr = "Type 17 BDS6,2 (emergency) from %x type %s" % (icao24, emerg_str)
      
    else:
      retstr = "Type 17 subtype %i from %x not implemented" % (subtype, icao24)

    return retstr

  def print20(self, data, ecc):
    msgtype = data["df"]
    if(msgtype == 20):
      [fs, dr, um, alt] = self.parse4(data)
    else:
      [fs, dr, um, ident] = self.parse5(data)
    bds1 = data["bds1"]
    bds2 = data["bds2"]

    if bds2 != 0:
      retstr = "No handler for BDS2 == %i from %x" % (bds2, ecc)

    elif bds1 == 0:
      retstr = "No handler for BDS1 == 0 from %x" % ecc
    elif bds1 == 1:
      retstr = "Type 20 link capability report from %x: ACS: 0x%x, BCS: 0x%x, ECS: 0x%x, continues %i" \
                % (ecc, data["acs"], data["bcs"], data["ecs"], data["cfs"])
    elif bds1 == 2:
      retstr = "Type 20 identification from %x with text %s" % (ecc, self.parseMB_id(data))
    elif bds2 == 3:
      retstr = "Type 20 TCAS report from %x: " % ecc
      tti = data["tti"]
      if tti == 1:
        (resolutions, complements, rat, mte, threat_id) = self.parseMB_TCAS_threatid(data)
        retstr += "threat ID: %x advised: %s complement: %s" % (threat_id, resolutions, complements)
      elif tti == 2:
        (resolutions, complements, rat, mte, threat_alt, threat_range, threat_bearing) = self.parseMB_TCAS_threatloc(data)
        retstr += "range: %i bearing: %i alt: %i advised: %s complement: %s" % (threat_range, threat_bearing, threat_alt, resolutions, complements)
      else:
        retstr += " (no handler for TTI=%i)" % tti
      if mte == 1:
        retstr += " (multiple threats)"
      if rat == 1:
        retstr += " (resolved)"
    else:
      retstr = "No handler for BDS1 == %i from %x" % (bds1, ecc)

#    if(msgtype == 20):
#      retstr += " at %ift" % altitude
#    else:
#      retstr += " ident %x" % ident
      
    return retstr
