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

  fields = { }
  types = { }
  subfields = { } #fields to return objects instead of just returning bits
  startbit = 0 #field offset applied to all fields. used for offsetting subtypes to reconcile with spec.

  #get a particular field from the data
  def __getitem__(self, fieldname):
    if fieldname in self.types[self.get_type()]: #verify it exists in this packet type
      if fieldname in self.subfields:
        #create a new subfield object and return it
        return self.subfields[fieldname](self.get_bits(self.fields[fieldname]))
      return self.get_bits(self.fields[fieldname])
    else:
      raise FieldNotInPacket(fieldname)

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
  def get_bits(self, arg):
    (offset, num) = arg
    return (self.data \
        >> (self.get_numbits() - offset - num + self.startbit + 1)) \
         & ((1 << num) - 1)

#type MB (extended squitter types 20,21) subfields
class mb_reply(data_field):
  fields = { "acs": (45,20), "ais": (41,48),  "ara": (41,14), "bcs": (65,16),
             "bds": (33,8),  "bds1": (33,4),  "bds2": (37,4), "cfs": (41,4),
             "ecs": (81,8),  "mte": (60,1),   "rac": (55,4),  "rat": (59,1),
             "tid": (33,26), "tida": (63,13), "tidb": (83,6), "tidr": (76,7),
             "tti": (61,2)
           }
  startbit = 32 #fields offset by 32 to match documentation

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
    return bds1

  def get_numbits(self):
    return 56

#type 17 extended squitter data
class me_reply(data_field):
  #TODO: add comments explaining these fields
  fields = { "ftc":  (1,5),   "ss":   (6,2),   "saf":   (8,1),    "alt":  (9, 12),
             "time": (21,1),  "cpr":  (22,1),  "lat":   (23, 17), "lon":  (40, 17),
             "mvt":  (6,7),   "gts":  (13,1),  "gtk":   (14,7),   "trs":  (1,2),
             "ats":  (3,1),   "cat":  (6,3),   "ident": (9,48),   "sub":  (6,3),
             "dew":  (10,1),  "vew":  (11,11), "dns":   (22,1),   "vns":  (23,11),
             "str":  (34,1),  "tr":   (35,6),  "svr":   (41,1),   "vr":   (42,9),
             "icf":  (9,1),   "ifr":  (10,1),  "nuc":   (11,3),   "gdew": (14,1),
             "gvew": (15,10), "gdns": (25,1),  "gvns":  (26,10),  "vrs":  (36,1),
             "gsvr": (37,1),  "gvr":  (38,9),  "ghds":  (49,1),   "ghd":  (50,6),
             "mhs":  (14,1),  "hdg":  (15,10), "ast":   (25,1),   "spd":  (26,10),
             "eps":  (9,3)
             #TODO: TCP, TCP+1/BDS 6,2
             }
  startbit = 0
  types = { }

  def get_type(self):
    pass
    
  def get_numbits(self):
    return 56


class modes_reply(data_field):
  def __init__(self, data):
    data_field.__init__(self, data)
#TODO FIX PARITY FIELDS
    self.parity_fields = {
        "ap": (33+(self.get_numbits()-56),24),
        "pi": (33+(self.get_numbits()-56),24)
        }

  #bitfield definitions according to Mode S spec
  #(start bit, num bits)
  fields = { "df": (1,5),   "vs": (6,1),   "fs": (6,3),   "cc": (7,1),
             "sl": (9,3),   "ri": (14,4),  "ac": (20,13), "dr": (9,5),
             "um": (14,6),  "id": (20,13), "ca": (6,3),   "aa": (9,24),
             "mv": (33,56), "me": (33,56), "mb": (33,56), "ke": (6,1),
             "nd": (7,4),   "md": (11,80)
           }

  #fields in each packet type (DF value)
  types = { 0: ["df", "vs", "cc", "sl", "ri", "ac", "ap"],
            4: ["df", "fs", "dr", "um", "ac", "ap"],
            5: ["df", "fs", "dr", "um", "id", "ap"],
            11: ["df", "ca", "aa", "pi"],
            16: ["df", "vs", "sl", "ri", "ac", "mv", "ap"],
            17: ["df", "ca", "aa", "me", "pi"],
            20: ["df", "fs", "dr", "um", "ac", "mb", "ap"],
            21: ["df", "fs", "dr", "um", "id", "mb", "ap"],
            24: ["df", "ke", "nd", "md", "ap"]
          }

  subfields = { "mb": mb_reply, "me": me_reply } #TODO MV, ME

  def is_long(self):
    return self.data > (1 << 56)

  def get_numbits(self):
    return 112 if self.is_long() else 56

  def get_type(self):
    return self.get_bits(self.fields["df"])

#TODO overload getitem to handle special parity fields

#  #type MV (extended squitter type 16) subfields
#  mv_fields = { "ara": (41,14), "mte": (60,1),  "rac": (55,4), "rat": (59,1),
#                "vds": (33,8),  "vds1": (33,4), "vds2": (37,4)
#              }

class modes_parse:
  def __init__(self, mypos):
      self.my_location = mypos
      self.cpr = cpr.cpr_decoder(self.my_location)
    
  def parse0(self, shortdata):
    vs = bool(shortdata >> 26 & 0x1)    #ground sensor -- airborne when 0
    cc = bool(shortdata >> 25 & 0x1)    #crosslink capability, binary
    sl = shortdata >> 21 & 0x07  #operating sensitivity of onboard TCAS system. 0 means no TCAS sensitivity reported, 1-7 give TCAS sensitivity
    ri = shortdata >> 15 & 0x0F #speed coding: 0 = no onboard TCAS, 1 = NA, 2 = TCAS w/inhib res, 3 = TCAS w/vert only, 4 = TCAS w/vert+horiz, 5-7 = NA, 8 = no max A/S avail,
								  #9 = A/S <= 75kt, 10 = A/S (75-150]kt, 11 = (150-300]kt, 12 = (300-600]kt, 13 = (600-1200]kt, 14 = >1200kt, 15 = NA

    altitude = decode_alt(shortdata & 0x1FFF, True) #bit 13 is set for type 0

    return [vs, cc, sl, ri, altitude]

  def parse4(self, shortdata):
    fs = shortdata >> 24 & 0x07 #flight status: 0 is airborne normal, 1 is ground normal, 2 is airborne alert, 3 is ground alert, 4 is alert SPI, 5 is normal SPI
    dr = shortdata >> 19 & 0x1F #downlink request: 0 means no req, bit 0 is Comm-B msg rdy bit, bit 1 is TCAS info msg rdy, bit 2 is Comm-B bcast #1 msg rdy, bit2+bit0 is Comm-B bcast #2 msg rdy,
								#bit2+bit1 is TCAS info and Comm-B bcast #1 msg rdy, bit2+bit1+bit0 is TCAS info and Comm-B bcast #2 msg rdy, 8-15 N/A, 16-31 req to send N-15 segments
    um = shortdata >> 13 & 0x3F #transponder status readouts, no decoding information available

    altitude = decode_alt(shortdata & 0x1FFF, True)

    return [fs, dr, um, altitude]


  def parse5(self, shortdata):
    fs = shortdata >> 24 & 0x07 #flight status: 0 is airborne normal, 1 is ground normal, 2 is airborne alert, 3 is ground alert, 4 is alert SPI, 5 is normal SPI
    dr = shortdata >> 19 & 0x1F #downlink request: 0 means no req, bit 0 is Comm-B msg rdy bit, bit 1 is TCAS info msg rdy, bit 2 is Comm-B bcast #1 msg rdy, bit2+bit0 is Comm-B bcast #2 msg rdy,
								#bit2+bit1 is TCAS info and Comm-B bcast #1 msg rdy, bit2+bit1+bit0 is TCAS info and Comm-B bcast #2 msg rdy, 8-15 N/A, 16-31 req to send N-15 segments
    um = shortdata >> 13 & 0x3F #transponder status readouts, no decoding information available
    ident = shortdata & 0x1FFF

    return [fs, dr, um, ident]

  def parse11(self, shortdata, ecc):
    interrogator = ecc & 0x0F
	
    ca = shortdata >> 13 & 0x3F #capability
    icao24 = shortdata & 0xFFFFFF
    
    return [icao24, interrogator, ca]

	#the Type 17 subtypes are:
	#0: No position information
	#1: Identification (Category set D)
	#2: Identification (Category set C)
	#3: "" (B)
	#4: "" (A)
	#5: Surface position accurate to 7.5m
	#6: "" to 25m
	#7: "" to 185.2m (0.1nm)
	#8: "" above 185.2m
	#9: Airborne position to 7.5m
	#10-18: Same with less accuracy
	#19: Airborne velocity
	#20: Airborne position w/GNSS height above earth
	#21: same to 25m
	#22: same above 25m
	#23: Reserved
	#24: Reserved for surface system status
	#25-27: Reserved
	#28: Extended squitter aircraft status
	#29: Current/next trajectory change point
	#30: Aircraft operational coordination
	#31: Aircraft operational status

  categories = [["NO INFO", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED", "RESERVED"],\
                ["NO INFO", "SURFACE EMERGENCY VEHICLE", "SURFACE SERVICE VEHICLE", "FIXED OBSTRUCTION", "RESERVED", "RESERVED", "RESERVED"],\
                ["NO INFO", "GLIDER", "BALLOON/BLIMP", "PARACHUTE", "ULTRALIGHT", "RESERVED", "UAV", "SPACECRAFT"],\
                ["NO INFO", "LIGHT", "SMALL", "LARGE", "LARGE HIGH VORTEX", "HEAVY", "HIGH PERFORMANCE", "ROTORCRAFT"]]

  def parseBDS08(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF
    subtype = (longdata >> 51) & 0x1F
    category = (longdata >> 48) & 0x07
    catstring = self.categories[subtype-1][category]

    msg = ""
    for i in range(0, 8):
      msg += self.charmap( longdata >> (42-6*i) & 0x3F)
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

  def parseBDS05(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF

    encoded_lon = longdata & 0x1FFFF
    encoded_lat = (longdata >> 17) & 0x1FFFF
    cpr_format = (longdata >> 34) & 1

    enc_alt = (longdata >> 36) & 0x0FFF

    altitude = decode_alt(enc_alt, False)

    [decoded_lat, decoded_lon, rnge, bearing] = self.cpr.decode(icao24, encoded_lat, encoded_lon, cpr_format, 0)

    return [altitude, decoded_lat, decoded_lon, rnge, bearing]


  #welp turns out it looks like there's only 17 bits in the BDS0,6 ground packet after all.
  def parseBDS06(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF

    encoded_lon = longdata & 0x1FFFF
    encoded_lat = (longdata >> 17) & 0x1FFFF
    cpr_format = (longdata >> 34) & 1

    altitude = 0

    [decoded_lat, decoded_lon, rnge, bearing] = self.cpr.decode(icao24, encoded_lat, encoded_lon, cpr_format, 1)

    return [altitude, decoded_lat, decoded_lon, rnge, bearing]

  def parseBDS09_0(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF
    vert_spd = ((longdata >> 6) & 0x1FF) * 32
    ud = bool((longdata >> 15) & 1)
    if ud:
      vert_spd = 0 - vert_spd
    turn_rate = (longdata >> 16) & 0x3F
    turn_rate = turn_rate * 15/62
    rl = bool((longdata >> 22) & 1)
    if rl:
      turn_rate = 0 - turn_rate
    ns_vel = (longdata >> 23) & 0x7FF - 1
    ns = bool((longdata >> 34) & 1)
    ew_vel = (longdata >> 35) & 0x7FF - 1
    ew = bool((longdata >> 46) & 1)
    subtype = (longdata >> 48) & 0x07

    velocity = math.hypot(ns_vel, ew_vel)
    if ew:
      ew_vel = 0 - ew_vel
    if ns:
      ns_vel = 0 - ns_vel
    heading = math.atan2(ew_vel, ns_vel) * (180.0 / math.pi)
    if heading < 0:
      heading += 360

    return [velocity, heading, vert_spd, turn_rate]

  def parseBDS09_1(self, shortdata, longdata):
    icao24 = shortdata & 0xFFFFFF
    alt_geo_diff = longdata & 0x7F - 1
    above_below = bool((longdata >> 7) & 1)
    if above_below:
      alt_geo_diff = 0 - alt_geo_diff;
    vert_spd = float((longdata >> 10) & 0x1FF - 1)
    ud = bool((longdata >> 19) & 1)
    if ud:
      vert_spd = 0 - vert_spd
    vert_src = bool((longdata >> 20) & 1)
    ns_vel = float((longdata >> 21) & 0x3FF - 1)
    ns = bool((longdata >> 31) & 1)
    ew_vel = float((longdata >> 32) & 0x3FF - 1)
    ew = bool((longdata >> 42) & 1)
    subtype = (longdata >> 48) & 0x07


    if subtype == 0x02:
      ns_vel *= 4
      ew_vel *= 4


    vert_spd *= 64
    alt_geo_diff *= 25
	
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
