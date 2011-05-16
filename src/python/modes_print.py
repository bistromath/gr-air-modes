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


import time, os, sys
from string import split, join
import modes_parse
import math

class modes_output_print(modes_parse.modes_parse):
  def __init__(self, mypos):
      modes_parse.modes_parse.__init__(self, mypos)
      
  def parse(self, message):
    [msgtype, shortdata, longdata, parity, ecc, reference, time_secs, time_frac] = message.split()
    shortdata = long(shortdata, 16)
    longdata = long(longdata, 16)
    parity = long(parity, 16)
    ecc = long(ecc, 16)
    reference = float(reference)
    time_secs = long(time_secs)
    time_frac = float(time_frac)

    msgtype = int(msgtype)
    
    output = None;

    if msgtype == 0:
      output = self.print0(shortdata, parity, ecc)
    elif msgtype == 4:
      output = self.print4(shortdata, parity, ecc)
    elif msgtype == 5:
      output = self.print5(shortdata, parity, ecc)
    elif msgtype == 11:
      output = self.print11(shortdata, parity, ecc)
    elif msgtype == 17:
      output = self.print17(shortdata, longdata, parity, ecc)
    else:
      output = "No handler for message type " + str(msgtype) + " from %x" % ecc

    if reference == 0.0:
        refdb = -150.0
    else:
        refdb = 10.0*math.log10(reference)
        
    if output is not None: 
        output = "(%.0f %u %f) " % (refdb, time_secs, time_frac) + output
        print output

  def print0(self, shortdata, parity, ecc):
    [vs, cc, sl, ri, altitude] = self.parse0(shortdata, parity, ecc)
	
    retstr = "Type 0 (short A-A surveillance) from " + "%x" % ecc + " at " + str(altitude) + "ft"
    # the ri values below 9 are used for other things. might want to print those someday.
    if ri == 9:
      retstr = retstr + " (speed <75kt)"
    elif ri > 9:
      retstr = retstr + " (speed " + str(75 * (1 << (ri-10))) + "-" + str(75 * (1 << (ri-9))) + "kt)"

    if vs is True:
      retstr = retstr + " (aircraft is on the ground)"

    return retstr

  def print4(self, shortdata, parity, ecc):

    [fs, dr, um, altitude] = self.parse4(shortdata, parity, ecc)

    retstr = "Type 4 (short surveillance altitude reply) from " + "%x" % ecc + " at " + str(altitude) + "ft"

    if fs == 1:
      retstr = retstr + " (aircraft is on the ground)"
    elif fs == 2:
      retstr = retstr + " (AIRBORNE ALERT)"
    elif fs == 3:
      retstr = retstr + " (GROUND ALERT)"
    elif fs == 4:
      retstr = retstr + " (SPI ALERT)"
    elif fs == 5:
      retstr = retstr + " (SPI)"

    return retstr

  def print5(self, shortdata, parity, ecc):
    [fs, dr, um] = self.parse5(shortdata, parity, ecc)

    retstr = "Type 5 (short surveillance ident reply) from " + "%x" % ecc + " with ident " + str(shortdata & 0x1FFF)

    if fs == 1:
      retstr = retstr + " (aircraft is on the ground)"
    elif fs == 2:
      retstr = retstr + " (AIRBORNE ALERT)"
    elif fs == 3:
      retstr = retstr + " (GROUND ALERT)"
    elif fs == 4:
      retstr = retstr + " (SPI ALERT)"
    elif fs == 5:
      retstr = retstr + " (SPI)"

    return retstr

  def print11(self, shortdata, parity, ecc):
    [icao24, interrogator, ca] = self.parse11(shortdata, parity, ecc)

    retstr = "Type 11 (all call reply) from " + "%x" % icao24 + " in reply to interrogator " + str(interrogator)
    return retstr

  def print17(self, shortdata, longdata, parity, ecc):
    icao24 = shortdata & 0xFFFFFF
    subtype = (longdata >> 51) & 0x1F;

    retstr = None

    if subtype == 4:
      msg = self.parseBDS08(shortdata, longdata, parity, ecc)
      retstr = "Type 17 subtype 04 (ident) from " + "%x" % icao24 + " with data " + msg

    elif subtype >= 5 and subtype <= 8:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(shortdata, longdata, parity, ecc)
      if decoded_lat is not None:
        retstr = "Type 17 subtype 06 (surface report) from " + "%x" % icao24 + " at (" + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ") (" + "%.2f" % rnge + " @ " + "%.0f" % bearing + ")"

    elif subtype >= 9 and subtype <= 18:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(shortdata, longdata, parity, ecc)
      if decoded_lat is not None:
        retstr = "Type 17 subtype 05 (position report) from " + "%x" % icao24 + " at (" + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ") (" + "%.2f" % rnge + " @ " + "%.0f" % bearing + ") at " + str(altitude) + "ft"

#   this is a trigger to capture the bizarre BDS0,5 squitters you keep seeing on the map with latitudes all over the place
#     if icao24 == 0xa1ede9:
#       print "Buggy squitter with shortdata %s longdata %s parity %s ecc %s" % (str(shortdata), str(longdata), str(parity), str(ecc),)

    elif subtype == 19:
      subsubtype = (longdata >> 48) & 0x07
      if subsubtype == 0:
        [velocity, heading, vert_spd] = self.parseBDS09_0(shortdata, longdata, parity, ecc)
        retstr = "Type 17 subtype 09-0 (track report) from " + "%x" % icao24 + " with velocity " + "%.0f" % velocity + "kt heading " + "%.0f" % heading + " VS " + "%.0f" % vert_spd

      elif subsubtype == 1:
        [velocity, heading, vert_spd] = self.parseBDS09_1(shortdata, longdata, parity, ecc)
        retstr = "Type 17 subtype 09-1 (track report) from " + "%x" % icao24 + " with velocity " + "%.0f" % velocity + "kt heading " + "%.0f" % heading + " VS " + "%.0f" % vert_spd

      else:
        retstr = "Type 17 subtype 09-%i" % (subsubtype) + " not implemented"
    else:
      retstr = "Type 17 subtype " + str(subtype) + " not implemented"

    return retstr
