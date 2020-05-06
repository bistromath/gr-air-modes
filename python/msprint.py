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
import air_modes
from air_modes.exceptions import *
import math

#TODO get rid of class and convert to functions
#no need for class here
class output_print:
  def __init__(self, cpr, publisher, callback=None):
    self._cpr = cpr
    self._callback = callback
    #sub to every function that starts with "handle"
    self._fns = [int(l[6:]) for l in dir(self) if l.startswith("handle")]
    for i in self._fns:
      publisher.subscribe("type%i_dl" % i, getattr(self, "handle%i" % i))
    
    publisher.subscribe("modes_dl", self.catch_nohandler)

  @staticmethod
  def prefix(msg):
    return "(%i %.8f) " % (msg.rssi, msg.timestamp)

  def _print(self, msg):
    if self._callback is None:
        print(msg)
    else:
        self._callback(msg)

  def catch_nohandler(self, msg):
    if msg.data.get_type() not in self._fns:
      retstr = output_print.prefix(msg)
      retstr += "No handler for message type %i" % msg.data.get_type()
      if "aa" not in msg.data.fields:
        retstr += " from %.6x" % msg.ecc
      else:
        retstr += " from %.6x" % msg.data["aa"]
      self._print(retstr)
      
  def handle0(self, msg):
    try:
      retstr = output_print.prefix(msg)
      retstr += "Type 0 (short A-A surveillance) from %x at %ift" % (msg.ecc, air_modes.decode_alt(msg.data["ac"], True))
      ri = msg.data["ri"]
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
      else:
        raise ADSBError

    except ADSBError:
        return

    if msg.data["vs"] == 1:
      retstr += " (aircraft is on the ground)"

    self._print(retstr)

  @staticmethod
  def fs_text(fs):
    if fs == 1:
      return " (aircraft is on the ground)"
    elif fs == 2:
      return " (AIRBORNE ALERT)"
    elif fs == 3:
      return " (GROUND ALERT)"
    elif fs == 4:
      return " (SPI ALERT)"
    elif fs == 5:
      return " (SPI)"
    else:
      raise ADSBError

  def handle4(self, msg):
    try:
      retstr = output_print.prefix(msg)
      retstr += "Type 4 (short surveillance altitude reply) from %x at %ift" % (msg.ecc, air_modes.decode_alt(msg.data["ac"], True))
      retstr += output_print.fs_text(msg.data["fs"])    
    except ADSBError:
      return
    self._print(retstr)

  def handle5(self, msg):
    try:
      retstr = output_print.prefix(msg)
      retstr += "Type 5 (short surveillance ident reply) from %x with ident %i" % (msg.ecc, air_modes.decode_id(msg.data["id"]))
      retstr += output_print.fs_text(msg.data["fs"])
    except ADSBError:
      return
    self._print(retstr)

  def handle11(self, msg):
    try:
      retstr = output_print.prefix(msg)
      retstr += "Type 11 (all call reply) from %x in reply to interrogator %i with capability level %i" % (msg.data["aa"], msg.ecc & 0xF, msg.data["ca"]+1)
    except ADSBError:
      return
    self._print(retstr)

  #the only one which requires state
  def handle17(self, msg):
    icao24 = msg.data["aa"]
    bdsreg = msg.data["me"].get_type()

    retstr = output_print.prefix(msg)
    try:
        if bdsreg == 0x08:
          (ident, typestring) = air_modes.parseBDS08(msg.data)
          retstr += "Type 17 BDS0,8 (ident) from %x type %s ident %s" % (icao24, typestring, ident)

        elif bdsreg == 0x06:
          [ground_track, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS06(msg.data, self._cpr)
          retstr += "Type 17 BDS0,6 (surface report) from %x at (%.6f, %.6f) ground track %i" % (icao24, decoded_lat, decoded_lon, ground_track)
          if rnge is not None and bearing is not None:
            retstr += " (%.2f @ %.0f)" % (rnge, bearing)

        elif bdsreg == 0x05:
          [altitude, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS05(msg.data, self._cpr)
          retstr += "Type 17 BDS0,5 (position report) from %x at (%.6f, %.6f)" % (icao24, decoded_lat, decoded_lon)
          if rnge is not None and bearing is not None:
            retstr += " (" + "%.2f" % rnge + " @ " + "%.0f" % bearing + ")"
          retstr += " at " + str(altitude) + "ft"

        elif bdsreg == 0x09:
          subtype = msg.data["bds09"].get_type()
          if subtype == 0:
            [velocity, heading, vert_spd, turnrate] = air_modes.parseBDS09_0(msg.data)
            retstr += "Type 17 BDS0,9-%i (track report) from %x with velocity %.0fkt heading %.0f VS %.0f turn rate %.0f" \
                     % (subtype, icao24, velocity, heading, vert_spd, turnrate)
          elif subtype == 1:
            [velocity, heading, vert_spd] = air_modes.parseBDS09_1(msg.data)
            retstr += "Type 17 BDS0,9-%i (track report) from %x with velocity %.0fkt heading %.0f VS %.0f" % (subtype, icao24, velocity, heading, vert_spd)
          elif subtype == 3:
            [mag_hdg, vel_src, vel, vert_spd, geo_diff] = air_modes.parseBDS09_3(msg.data)
            retstr += "Type 17 BDS0,9-%i (air course report) from %x with %s %.0fkt magnetic heading %.0f VS %.0f geo. diff. from baro. alt. %.0fft" \
                     % (subtype, icao24, vel_src, vel, mag_hdg, vert_spd, geo_diff)

          else:
            retstr += "Type 17 BDS0,9-%i from %x not implemented" % (subtype, icao24)

        elif bdsreg == 0x62:
          emerg_str = air_modes.parseBDS62(data)
          retstr += "Type 17 BDS6,2 (emergency) from %x type %s" % (icao24, emerg_str)

        else:
          retstr += "Type 17 with FTC=%i from %x not implemented" % (msg.data["ftc"], icao24)
    except ADSBError:
        return

    self._print(retstr)

  def printTCAS(self, msg):
    msgtype = msg.data["df"]

    if msgtype == 16:
      bds1 = msg.data["vds1"]
      bds2 = msg.data["vds2"]
    else:
      bds1 = msg.data["bds1"]
      bds2 = msg.data["bds2"]

    retstr = output_print.prefix(msg)

    if bds2 != 0:
      retstr += "No handler in type %i for BDS2 == %i from %x" % (msgtype, bds2, msg.ecc)

    elif bds1 == 0:
      retstr += "No handler in type %i for BDS1 == 0 from %x" % (msgtype, msg.ecc)
    elif bds1 == 1:
      retstr += "Type %i link capability report from %x: ACS: 0x%x, BCS: 0x%x, ECS: 0x%x, continues %i" \
                % (msgtype, msg.ecc, msg.data["acs"], msg.data["bcs"], msg.data["ecs"], msg.data["cfs"])
    elif bds1 == 2:
      retstr += "Type %i identification from %x with text %s" % (msgtype, msg.ecc, air_modes.parseMB_id(msg.data))
    elif bds1 == 3:
      retstr += "Type %i TCAS report from %x: " % (msgtype, msg.ecc)
      tti = msg.data["tti"]
      if msgtype == 16:
        (resolutions, complements, rat, mte) = air_modes.parse_TCAS_CRM(msg.data)
        retstr += "advised: %s complement: %s" % (resolutions, complements)
      else:
          if tti == 1:
            (resolutions, complements, rat, mte, threat_id) = air_modes.parseMB_TCAS_threatid(msg.data)
            retstr += "threat ID: %x advised: %s complement: %s" % (threat_id, resolutions, complements)
          elif tti == 2:
            (resolutions, complements, rat, mte, threat_alt, threat_range, threat_bearing) = air_modes.parseMB_TCAS_threatloc(msg.data)
            retstr += "range: %i bearing: %i alt: %i advised: %s complement: %s" % (threat_range, threat_bearing, threat_alt, resolutions, complements)
          else:
            rat = 0
            mte = 0
            retstr += " (no handler for TTI=%i)" % tti
      if mte == 1:
        retstr += " (multiple threats)"
      if rat == 1:
        retstr += " (resolved)"
    else:
      retstr += "No handler for type %i, BDS1 == %i from %x" % (msgtype, bds1, msg.ecc)

    if(msgtype == 20 or msgtype == 16):
      retstr += " at %ift" % air_modes.decode_alt(msg.data["ac"], True)
    else:
      retstr += " ident %x" % air_modes.decode_id(msg.data["id"])

    self._print(retstr)

  handle16 = printTCAS
  handle20 = printTCAS
  handle21 = printTCAS
