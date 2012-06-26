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
from altitude import decode_alt
import cpr
import math
from modes_exceptions import *

#this implements a packet class which can retrieve its own fields.
class data_field:
  def __init__(self, data):
    self.data = data

  types = { }
  offset = 1   #field offset applied to all fields. used for offsetting
               #subtypes to reconcile with the spec. Really just for readability.

  #get a particular field from the data
  def __getitem__(self, fieldname):
    mytype = self.get_type()
    if mytype in self.types:
      if fieldname in self.types[mytype]: #verify it exists in this packet type
        return self.get_bits(*self.types[mytype][fieldname])
      else:
        raise FieldNotInPacket(fieldname)
    else:
      raise NoHandlerError(mytype)

  #grab all the fields in the packet as a dict
  def get_fields(self):
    return {field: self[field] for field in self.types[self.get_type()]}

  def get_type(self):
    raise NotImplementedError

  def get_numbits(self):
    raise NotImplementedError

  #retrieve bits from data given the offset and number of bits.
  #the offset is both left-justified (LSB) and starts at 1, to
  #correspond to the Mode S spec. Blame them.
  def get_bits(self, *args):
    startbit = args[0]
    num = args[1]
    bits = (self.data \
        >> (self.get_numbits() - startbit - num + self.offset)) \
         & ((1 << num) - 1)
    if len(args) == 3:
      #construct a subtype from the bit field
      return args[2](bits)
    else:
      #return the bits as a number
      return bits

#type MB (extended squitter types 20,21) subfields
class mb_reply(data_field):
  fields = { "acs": (45,20), "ais": (41,48),  "ara": (41,14), "bcs": (65,16),
             "bds": (33,8),  "bds1": (33,4),  "bds2": (37,4), "cfs": (41,4),
             "ecs": (81,8),  "mte": (60,1),   "rac": (55,4),  "rat": (59,1),
             "tid": (33,26), "tida": (63,13), "tidb": (83,6), "tidr": (76,7),
             "tti": (61,2)
           }
  offset = 33 #fields offset by 33 to match documentation

  #types are based on bds1 subfield
  types = { 0: ["bds", "bds1", "bds2"], #TODO
            1: ["bds", "bds1", "bds2", "cfs", "acs", "bcs"],
            2: ["bds", "bds1", "bds2", "ais"],
            3: ["bds", "bds1", "bds2", "ara",  "rac", "rat",
                "mte", "tti",  "tida", "tidr", "tidb"]
          }

  def get_type(self):
    bds1 = self.get_bits(self.fields["bds1"])
    bds2 = self.get_bits(self.fields["bds2"])
    if bds1 not in (0,1,2,3) or bds2 not in (0,):
      raise NoHandlerError
    return int(bds1)

  def get_numbits(self):
    return 56

class bds09_reply(data_field):
  offset = 6
  types = {
             #BDS0,9 subtype 0
             0: {"sub": (6,3), "dew": (10,1), "vew": (11,11), "dns": (22,1),
                 "vns": (23,11), "str": (34,1), "tr": (35,6), "dvr": (41,1),
                 "vr": (42,9)},
             #BDS0,9 subtypes 1-2 (differ only in velocity encoding)
             1: {"sub": (6,3), "icf": (9,1), "ifr": (10,1), "nuc": (11,3),
                 "dew": (14,1), "vew": (15,10), "dns": (25,1), "vns": (26,10),
                 "vrsrc": (36,1), "dvr": (37,1), "vr": (38,9), "dhd": (49,1), "hd": (50,6)},
             #BDS0,9 subtype 3-4 (airspeed and heading)
             3: {"sub": (6,3), "icf": (9,1), "ifr": (10,1), "nuc": (11,3), "mhs": (14,1),
                 "hdg": (15,10), "ast": (25,1), "spd": (26,10), "vrsrc": (36,1),
                 "dvr": (37,1), "vr": (38,9), "dhd": (49,1), "hd": (50,6)}
          }

  def get_type(self):
    sub = self.get_bits(6,3)
    if sub == 0:
      return 0
    if 1 <= sub <= 2:
      return 1
    if 3 <= sub <= 4:
      return 3

  def get_numbits(self):
    return 51
      
#type 17 extended squitter data
class me_reply(data_field):
  #types in this format are listed by BDS register
  #TODO: add comments explaining these fields
  types = { 0x05: {"ftc": (1,5), "ss": (6,2), "saf": (8,1), "alt": (9,12), "time": (21,1), "cpr": (22,1), "lat": (23,17), "lon": (40,17)}, #airborne position
            0x06: {"ftc": (1,5), "mvt": (6,7), "gts": (13,1), "gtk": (14,7), "time": (21,1), "cpr": (22,1), "lat": (23,17), "lon": (40,17)}, #surface position
            0x07: {"ftc": (1,5),}, #TODO extended squitter status
            0x08: {"ftc": (1,5), "cat": (6,3), "ident": (9,48)}, #extended squitter identification and type
            0x09: {"ftc": (1,5), "bds09": (6,51, bds09_reply)},
            #0x0A: data link capability report
            #0x17: common usage capability report
            #0x18-0x1F: Mode S specific services capability report
            #0x20: aircraft identification
            0x61: {"ftc": (1,5), "eps": (9,3)}
          }

  #maps ftc to BDS register
  def get_type(self):
    ftc = self.get_bits(1,5)
    if 1 <= ftc <= 4:
      return 0x08
    elif 5 <= ftc <= 8:
      return 0x06
    elif 9 <= ftc <= 18:
      return 0x05
    elif ftc == 19:
      return 0x09
    else:
      return NoHandlerError
    
  def get_numbits(self):
    return 56

class modes_reply(data_field):
  #bitfield definitions according to Mode S spec for each packet type
  types = { 0: {"df": (1,5), "vs": (6,1), "cc": (7,1), "sl": (9,3), "ri": (14,4), "ac": (20,13), "ap": (33,24)},
            4: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "ac": (20,13), "ap": (33,24)},
            5: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "id": (20,13), "ap": (33,24)},
           11: {"df": (1,5), "ca": (6,3), "aa": (9,24), "pi": (33,24)},
           16: {"df": (1,5), "vs": (6,1), "sl": (9,3), "ri": (14,4), "ac": (20,13), "mv": (33,56), "ap": (88,24)},
           17: {"df": (1,5), "ca": (6,3), "aa": (9,24), "me": (33,56, me_reply), "pi": (88,24)},
           20: {"df": (1,5), "fs": (6,3), "dr": (9,24), "um": (14,6), "ac": (20,13), "mb": (33,56, mb_reply), "ap": (88,24)},
           21: {"df": (1,5), "fs": (6,3), "dr": (9,24), "um": (14,6), "id": (20,13), "mb": (33,56, mb_reply), "ap": (88,24)},
           24: {"df": (1,5), "ke": (6,1), "nd": (7,4), "md": (11,80), "ap": (88,24)}
          }

  def is_long(self):
    return self.data > (1 << 56)

  def get_numbits(self):
    return 112 if self.is_long() else 56

  def get_type(self):
    return self.get_bits(1,5)

#  #type MV (extended squitter type 16) subfields
#  mv_fields = { "ara": (41,14), "mte": (60,1),  "rac": (55,4), "rat": (59,1),
#                "vds": (33,8),  "vds1": (33,4), "vds2": (37,4)
#              }

class modes_parse:
  def __init__(self, mypos):
      self.my_location = mypos
      self.cpr = cpr.cpr_decoder(self.my_location)
    
  def parse0(self, data):
    fields = data.get_fields()
    altitude = decode_alt(data["ac"], True)
    return [fields["vs"], fields["cc"], fields["sl"], fields["ri"], altitude]

  def parse4(self, data):
    fields = data.get_fields()
    altitude = decode_alt(data["ac"], True)
    return [data["fs"], data["dr"], data["um"], altitude]

  def parse5(self, data):
    return [data["fs"], data["dr"], data["um"], data["id"]]

  def parse11(self, data, ecc):
    interrogator = ecc & 0x0F
    return [data["aa"], interrogator, data["ca"]]

  categories = [["NO INFO", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED"],\
                ["NO INFO", "SURFACE EMERGENCY VEHICLE", "SURFACE SERVICE VEHICLE", "FIXED OBSTRUCTION", "RESERVED", "RESERVED", "RESERVED"],\
                ["NO INFO", "GLIDER", "BALLOON/BLIMP", "PARACHUTE", "ULTRALIGHT", "RESERVED", "UAV", "SPACECRAFT"],\
                ["NO INFO", "LIGHT", "SMALL", "LARGE", "LARGE HIGH VORTEX", "HEAVY", "HIGH PERFORMANCE", "ROTORCRAFT"]]

  def parseBDS08(self, data):
    catstring = self.categories[data["me"]["ftc"]-1][data["me"]["cat"]]

    msg = ""
    for i in range(0, 8):
      msg += self.charmap( data["me"]["ident"] >> (42-6*i) & 0x3F)
    return (msg, catstring)

  def charmap(self, d):
    if d > 0 and d < 27:
      retval = chr(ord("A")+d-1)
    elif d == 32:
      retval = " "
    elif d > 47 and d < 58:
      retval = chr(ord("0")+d-48)
    else:
      retval = " "

    return retval

  def parseBDS05(self, data):
    icao24 = data["aa"]

    encoded_lon = data["me"]["lon"]
    encoded_lat = data["me"]["lat"]
    cpr_format = data["me"]["cpr"]
    altitude = decode_alt(data["me"]["alt"], False)

    [decoded_lat, decoded_lon, rnge, bearing] = self.cpr.decode(icao24, encoded_lat, encoded_lon, cpr_format, 0)

    return [altitude, decoded_lat, decoded_lon, rnge, bearing]


  #welp turns out it looks like there's only 17 bits in the BDS0,6 ground packet after all.
  def parseBDS06(self, data):
    icao24 = data["aa"]
 
    encoded_lon = data["me"]["lon"]
    encoded_lat = data["me"]["lat"]
    cpr_format = data["me"]["cpr"]
    altitude = decode_alt(data["me"]["alt"], False)
    [decoded_lat, decoded_lon, rnge, bearing] = self.cpr.decode(icao24, encoded_lat, encoded_lon, cpr_format, 1)
    return [altitude, decoded_lat, decoded_lon, rnge, bearing]

  def parseBDS09_0(self, data):
    #0: ["sub", "dew", "vew", "dns", "vns", "str", "tr", "svr", "vr"],
    bdsobj = data["me"]["bds09"]
    vert_spd = bdsobj["vr"] * 32
    ud = bool(bdsobj["dvr"])
    if ud:
      vert_spd = 0 - vert_spd
    turn_rate = bdsobj["tr"] * 15/62
    rl = bdsobj["str"]
    if rl:
      turn_rate = 0 - turn_rate
    ns_vel = bdsobj["vns"] - 1
    ns = bool(bdsobj["dns"])
    ew_vel = bdsobj["vew"] - 1
    ew = bool(bdsobj["dew"])
    
    velocity = math.hypot(ns_vel, ew_vel)
    if ew:
      ew_vel = 0 - ew_vel
    if ns:
      ns_vel = 0 - ns_vel
    heading = math.atan2(ew_vel, ns_vel) * (180.0 / math.pi)
    if heading < 0:
      heading += 360

    return [velocity, heading, vert_spd, turn_rate]

  def parseBDS09_1(self, data):
    #1: ["sub", "icf", "ifr", "nuc", "dew", "vew", "dns", "vns", "vrsrc", "dvr", "vr", "dhd", "hd"],
    bdsobj = data["me"]["bds09"]
    alt_geo_diff = bdsobj["hd"] * 25
    above_below = bool(bdsobj["dhd"])
    if above_below:
      alt_geo_diff = 0 - alt_geo_diff;
    vert_spd = float(bdsobj["vr"] - 1) * 64
    ud = bool(bdsobj["dvr"])
    if ud:
      vert_spd = 0 - vert_spd
    vert_src = bool(bdsobj["vrsrc"])
    ns_vel = float(bdsobj["vns"])
    ns = bool(bdsobj["dns"])
    ew_vel = float(bdsobj["vew"])
    ew = bool(bdsobj["dew"])
    subtype = bdsobj["sub"]
    if subtype == 0x02:
      ns_vel <<= 2
      ew_vel <<= 2

    velocity = math.hypot(ns_vel, ew_vel)
    if ew:
      ew_vel = 0 - ew_vel
	
    if ns_vel == 0:
      heading = 0
    else:
      heading = math.atan(float(ew_vel) / float(ns_vel)) * (180.0 / math.pi)
    if ns:
      heading = 180 - heading
    if heading < 0:
      heading += 360

    return [velocity, heading, vert_spd]

  def parse20(self, shortdata, longdata):
    [fs, dr, um, alt] = self.parse4(shortdata)
    #BDS defines TCAS reply type and is the first 8 bits
    #BDS1 is first four, BDS2 is bits 5-8
    bds1 = longdata_bits(longdata, 33, 4)
    bds2 = longdata_bits(longdata, 37, 4)
    #bds2 != 0 defines extended TCAS capabilities, not in spec
    return [fs, dr, um, alt, bds1, bds2]

  def parseMB_commB(self, longdata): #bds1, bds2 == 0
    raise NoHandlerError

  def parseMB_caps(self, longdata): #bds1 == 1, bds2 == 0
    #cfs, acs, bcs
    raise NoHandlerError

  def parseMB_id(self, longdata): #bds1 == 2, bds2 == 0
    msg = ""
    for i in range(0, 8):
      msg += self.charmap( longdata >> (42-6*i) & 0x3F)
    return (msg)

  def parseMB_TCASRA(self, longdata): #bds1 == 3, bds2 == 0
    #ara[41-54],rac[55-58],rat[59],mte[60],tti[61-62],tida[63-75],tidr[76-82],tidb[83-88]
    raise NoHandlerError
