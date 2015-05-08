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
import math
import air_modes
from air_modes.exceptions import *

#this implements a packet class which can retrieve its own fields.
class data_field:
  def __init__(self, data):
    self.data = data
    self.fields = self.parse()

  types = { }
  offset = 1   #field offset applied to all fields. used for offsetting
               #subtypes to reconcile with the spec. Really just for readability.

  #get a particular field from the data
  def __getitem__(self, fieldname):
    mytype = self.get_type()
    if mytype in self.types:
      if fieldname in self.fields: #verify it exists in this packet type
        return self.fields[fieldname]
      else:
        raise FieldNotInPacket(fieldname)
    else:
      raise NoHandlerError(mytype)

  #grab all the fields in the packet as a dict
  #done once on init so you don't have to iterate down every time you grab a field
  def parse(self):
    fields = {}
    mytype = self.get_type()
    if mytype in self.types:
      for field in self.types[mytype]:
        bits = self.types[self.get_type()][field]
        if len(bits) == 3:
          obj = bits[2](self.get_bits(bits[0], bits[1]))
          fields.update(obj.parse())
          fields.update({field: obj})
        else:
          fields.update({field: self.get_bits(bits[0], bits[1])})
    else:
      raise NoHandlerError(mytype)
    return fields

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
    bits = 0
    try:
      bits = (self.data \
        >> (self.get_numbits() - startbit - num + self.offset)) \
         & ((1 << num) - 1)
    #the exception handler catches instances when you try to shift more than
    #the number of bits. this can happen when a garbage packet gets through
    #which reports itself as a short packet but of type long.
    #TODO: should find more productive way to throw this out
    except ValueError:
      pass
      #print "Short packet received for long packet type: %x" % self.data
    return bits

class bds09_reply(data_field):
  offset = 6
  types = {  #BDS0,9 subtype 0
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
    elif 9 <= ftc <= 18 and ftc != 15: #FTC 15 does not appear to be valid
      return 0x05
    elif ftc == 19:
      return 0x09
    elif ftc == 28:
      return 0x61
    else:
      return NoHandlerError(ftc)
    
  def get_numbits(self):
    return 56

#resolves the TCAS reply types from TTI info
class tcas_reply(data_field):
  offset = 61
  types = { 0: {"tti": (61,2)}, #UNKNOWN
            1: {"tti": (61,2), "tid": (63,26)},
            2: {"tti": (61,2), "tida": (63,13), "tidr": (76,7), "tidb": (83,6)}
          }
  def get_type(self):
    return self.get_bits(61,2)

  def get_numbits(self):
    return 28

#extended squitter types 20,21 MB subfield
class mb_reply(data_field):
  offset = 33 #fields offset by 33 to match documentation
  #types are based on bds1 subfield
  types = { 0: {"bds1": (33,4), "bds2": (37,4)}, #TODO
            1: {"bds1": (33,4), "bds2": (37,4), "cfs": (41,4), "acs": (45,20), "bcs": (65,16), "ecs": (81,8)},
            2: {"bds1": (33,4), "bds2": (37,4), "ais": (41,48)},
            3: {"bds1": (33,4), "bds2": (37,4), "ara": (41,14), "rac": (55,4), "rat": (59,1),
                "mte": (60,1), "tcas": (61, 28, tcas_reply)}
          }

  def get_type(self):
    bds1 = self.get_bits(33,4)
    bds2 = self.get_bits(37,4)
    if bds1 not in (0,1,2,3) or bds2 not in (0,):
      raise NoHandlerError(bds1)
    return int(bds1)

  def get_numbits(self):
    return 56

#  #type MV (extended squitter type 16) subfields
#  mv_fields = { "ara": (41,14), "mte": (60,1),  "rac": (55,4), "rat": (59,1),
#                "vds": (33,8),  "vds1": (33,4), "vds2": (37,4)
#              }

class mv_reply(data_field):
  offset = 33
  types = { "ara": (41,14), "mte": (60,1),  "rac": (55,4), "rat": (59,1),
            "vds": (33,8),  "vds1": (33,4), "vds2": (37,4)
          }

  def get_type(self):
    vds1 = self.get_bits(33,4)
    vds2 = self.get_bits(37,4)
    if vds1 not in (3,) or vds2 not in (0,):
      raise NoHandlerError(bds1)
    return int(vds1)

  def get_numbits(self):
    return 56

#the whole Mode S packet type
class modes_reply(data_field):
  types = { 0: {"df": (1,5), "vs": (6,1), "cc": (7,1), "sl": (9,3), "ri": (14,4), "ac": (20,13), "ap": (33,24)},
            4: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "ac": (20,13), "ap": (33,24)},
            5: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "id": (20,13), "ap": (33,24)},
           11: {"df": (1,5), "ca": (6,3), "aa": (9,24), "pi": (33,24)},
           16: {"df": (1,5), "vs": (6,1), "sl": (9,3), "ri": (14,4), "ac": (20,13), "mv": (33,56), "ap": (88,24)},
           17: {"df": (1,5), "ca": (6,3), "aa": (9,24), "me": (33,56, me_reply), "pi": (88,24)},
           20: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "ac": (20,13), "mb": (33,56, mb_reply), "ap": (88,24)},
           21: {"df": (1,5), "fs": (6,3), "dr": (9,5), "um": (14,6), "id": (20,13), "mb": (33,56, mb_reply), "ap": (88,24)},
           24: {"df": (1,5), "ke": (6,1), "nd": (7,4), "md": (11,80), "ap": (88,24)}
          }

  def is_long(self):
    return self.data > (1 << 56)

  def get_numbits(self):
    return 112 if self.is_long() else 56

  def get_type(self):
    return self.get_bits(1,5)

#unscramble mode A/C-style squawk codes for type 5 replies below
def decode_id(id):
  
  C1 = 0x1000
  A1 = 0x0800
  C2 = 0x0400
  A2 = 0x0200	#this represents the order in which the bits come
  C4 = 0x0100
  A4 = 0x0080
  B1 = 0x0020
  D1 = 0x0010
  B2 = 0x0008
  D2 = 0x0004
  B4 = 0x0002
  D4 = 0x0001
  
  a = ((id & A1) >> 11) + ((id & A2) >> 8) + ((id & A4) >> 5)
  b = ((id & B1) >> 5)  + ((id & B2) >> 2) + ((id & B4) << 1)
  c = ((id & C1) >> 12) + ((id & C2) >> 9) + ((id & C4) >> 6)
  d = ((id & D1) >> 2)  + ((id & D2) >> 1) + ((id & D4) << 2)
   
  return (a * 1000) + (b * 100) + (c * 10) + d

#decode ident squawks
def charmap(d):
  if d > 0 and d < 27:
    retval = chr(ord("A")+d-1)
  elif d == 32:
    retval = " "
  elif d > 47 and d < 58:
    retval = chr(ord("0")+d-48)
  else:
    retval = " "

  return retval

def parseBDS08(data):
  categories = [["NO INFO", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED"],\
                ["NO INFO", "SURFACE EMERGENCY VEHICLE", "SURFACE SERVICE VEHICLE", "FIXED OBSTRUCTION", "CLUSTER OBSTRUCTION", "LINE OBSTRUCTION", "RESERVED"],\
                ["NO INFO", "GLIDER", "BALLOON/BLIMP", "PARACHUTE", "ULTRALIGHT", "RESERVED", "UAV", "SPACECRAFT"],\
                ["NO INFO", "LIGHT", "SMALL", "LARGE", "LARGE HIGH VORTEX", "HEAVY", "HIGH PERFORMANCE", "ROTORCRAFT"]]

  catstring = categories[data["ftc"]-1][data["cat"]]

  msg = ""
  for i in range(0, 8):
    msg += charmap(data["ident"] >> (42-6*i) & 0x3F)
  return (msg, catstring)

#NOTE: this is stateful -- requires CPR decoder
def parseBDS05(data, cprdec):
  altitude = decode_alt(data["alt"], False)
  [decoded_lat, decoded_lon, rnge, bearing] = cprdec.decode(data["aa"], data["lat"], data["lon"], data["cpr"], 0)
  return [altitude, decoded_lat, decoded_lon, rnge, bearing]

#NOTE: this is stateful -- requires CPR decoder
def parseBDS06(data, cprdec):
  ground_track = data["gtk"] * 360. / 128
  [decoded_lat, decoded_lon, rnge, bearing] = cprdec.decode(data["aa"], data["lat"], data["lon"], data["cpr"], 1)
  return [ground_track, decoded_lat, decoded_lon, rnge, bearing]

def parseBDS09_0(data):
  #0: ["sub", "dew", "vew", "dns", "vns", "str", "tr", "svr", "vr"],
  vert_spd = data["vr"] * 32
  ud = bool(data["dvr"])
  if ud:
    vert_spd = 0 - vert_spd
  turn_rate = data["tr"] * 15/62
  rl = data["str"]
  if rl:
    turn_rate = 0 - turn_rate
  ns_vel = data["vns"] - 1
  ns = bool(data["dns"])
  ew_vel = data["vew"] - 1
  ew = bool(data["dew"])
    
  velocity = math.hypot(ns_vel, ew_vel)
  if ew:
    ew_vel = 0 - ew_vel
  if ns:
    ns_vel = 0 - ns_vel
  heading = math.atan2(ew_vel, ns_vel) * (180.0 / math.pi)
  if heading < 0:
    heading += 360

  return [velocity, heading, vert_spd, turn_rate]

def parseBDS09_1(data):
  #1: ["sub", "icf", "ifr", "nuc", "dew", "vew", "dns", "vns", "vrsrc", "dvr", "vr", "dhd", "hd"],
  alt_geo_diff = data["hd"] * 25
  above_below = bool(data["dhd"])
  if above_below:
    alt_geo_diff = 0 - alt_geo_diff;
  vert_spd = float(data["vr"] - 1) * 64
  ud = bool(data["dvr"])
  if ud:
    vert_spd = 0 - vert_spd
  vert_src = bool(data["vrsrc"])
  ns_vel = float(data["vns"])
  ns = bool(data["dns"])
  ew_vel = float(data["vew"])
  ew = bool(data["dew"])
  subtype = data["sub"]
  if subtype == 0x02:
    ns_vel *= 4
    ew_vel *= 4

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

def parseBDS09_3(data):
    #3: {"sub", "icf", "ifr", "nuc", "mhs", "hdg", "ast", "spd", "vrsrc",
    #    "dvr", "vr", "dhd", "hd"}
  mag_hdg = data["mhs"] * 360. / 1024
  vel_src = "TAS" if data["ast"] == 1 else "IAS"
  vel = data["spd"]
  if data["sub"] == 4:
      vel *= 4
  vert_spd = float(data["vr"] - 1) * 64
  if data["dvr"] == 1:
      vert_spd = 0 - vert_spd
  geo_diff = float(data["hd"] - 1) * 25
  return [mag_hdg, vel_src, vel, vert_spd, geo_diff]
      

def parseBDS62(data):
  eps_strings = ["NO EMERGENCY", "GENERAL EMERGENCY", "LIFEGUARD/MEDICAL", "FUEL EMERGENCY",
                 "NO COMMUNICATIONS", "UNLAWFUL INTERFERENCE", "RESERVED", "RESERVED"]
  return eps_strings[data["eps"]]

def parseMB_id(data): #bds1 == 2, bds2 == 0
  msg = ""
  for i in range(0, 8):
    msg += charmap( data["ais"] >> (42-6*i) & 0x3F)
  return (msg)

def parseMB_TCAS_resolutions(data):
  #these are LSB because the ICAO are asshats
  ara_bits    = {41: "CLIMB", 42: "DON'T DESCEND", 43: "DON'T DESCEND >500FPM", 44: "DON'T DESCEND >1000FPM",
                 45: "DON'T DESCEND >2000FPM", 46: "DESCEND", 47: "DON'T CLIMB", 48: "DON'T CLIMB >500FPM",
                 49: "DON'T CLIMB >1000FPM", 50: "DON'T CLIMB >2000FPM", 51: "TURN LEFT", 52: "TURN RIGHT",
                 53: "DON'T TURN LEFT", 54: "DON'T TURN RIGHT"}
  rac_bits    = {55: "DON'T DESCEND", 56: "DON'T CLIMB", 57: "DON'T TURN LEFT", 58: "DON'T TURN RIGHT"}
  ara = data["ara"]
  rac = data["rac"]
  #check to see which bits are set
  resolutions = ""
  for bit in ara_bits:
    if ara & (1 << (54-bit)):
      resolutions += " " + ara_bits[bit]
  complements = ""
  for bit in rac_bits:
    if rac & (1 << (58-bit)):
      complements += " " + rac_bits[bit]
  return (resolutions, complements)

#rat is 1 if resolution advisory terminated <18s ago
#mte is 1 if multiple threats indicated
#tti is threat type: 1 if ID, 2 if range/brg/alt
#tida is threat altitude in Mode C format
def parseMB_TCAS_threatid(data): #bds1==3, bds2==0, TTI==1
  #3: {"bds1": (33,4), "bds2": (37,4), "ara": (41,14), "rac": (55,4), "rat": (59,1),
  #    "mte": (60,1), "tti": (61,2),  "tida": (63,13), "tidr": (76,7), "tidb": (83,6)}
  (resolutions, complements) = parseMB_TCAS_resolutions(data)
  return (resolutions, complements, data["rat"], data["mte"], data["tid"])

def parseMB_TCAS_threatloc(data): #bds1==3, bds2==0, TTI==2
  (resolutions, complements) = parseMB_TCAS_resolutions(data)
  threat_alt = decode_alt(data["tida"], True)
  return (resolutions, complements, data["rat"], data["mte"], threat_alt, data["tidr"], data["tidb"])

#type 16 Coordination Reply Message
def parse_TCAS_CRM(data):
  (resolutions, complements) = parseMB_TCAS_resolutions(data)
  return (resolutions, complements, data["rat"], data["mte"])

#this decorator takes a pubsub and returns a function which parses and publishes messages
def make_parser(pub):
  publisher = pub
  def publish(message):
    [data, ecc, reference, int_timestamp, frac_timestamp] = message.split()
    try:
      ret = air_modes.modes_report(modes_reply(int(data, 16)),
                                   int(ecc, 16),
                                   10.0*math.log10(max(1e-8,float(reference))),
                                   air_modes.stamp(int(int_timestamp), float(frac_timestamp)))
      pub["modes_dl"] = ret
      pub["type%i_dl" % ret.data.get_type()] = ret
    except ADSBError:
      pass

  return publish
