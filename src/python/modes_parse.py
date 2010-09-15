#!/usr/bin/env python

import time, os, sys
from string import split, join
from altitude import decode_alt
from cpr import cpr_decode
import math

def parse0(shortdata, parity, ecc):
#	shortdata = long(shortdata, 16)
	#parity = long(parity)

	vs = bool(shortdata >> 26 & 0x1)    #ground sensor -- airborne when 0
	cc = bool(shortdata >> 25 & 0x1)    #crosslink capability, binary
	sl = shortdata >> 21 & 0x07  #operating sensitivity of onboard TCAS system. 0 means no TCAS sensitivity reported, 1-7 give TCAS sensitivity
	ri = shortdata >> 15 & 0x0F #speed coding: 0 = no onboard TCAS, 1 = NA, 2 = TCAS w/inhib res, 3 = TCAS w/vert only, 4 = TCAS w/vert+horiz, 5-7 = NA, 8 = no max A/S avail,
								  #9 = A/S <= 75kt, 10 = A/S (75-150]kt, 11 = (150-300]kt, 12 = (300-600]kt, 13 = (600-1200]kt, 14 = >1200kt, 15 = NA

	altitude = decode_alt(shortdata & 0x1FFF, True) #bit 13 is set for type 0

	return [vs, cc, sl, ri, altitude]

def parse4(shortdata, parity, ecc):
#	shortdata = long(shortdata, 16)
	fs = shortdata >> 24 & 0x07 #flight status: 0 is airborne normal, 1 is ground normal, 2 is airborne alert, 3 is ground alert, 4 is alert SPI, 5 is normal SPI
	dr = shortdata >> 19 & 0x1F #downlink request: 0 means no req, bit 0 is Comm-B msg rdy bit, bit 1 is TCAS info msg rdy, bit 2 is Comm-B bcast #1 msg rdy, bit2+bit0 is Comm-B bcast #2 msg rdy,
								#bit2+bit1 is TCAS info and Comm-B bcast #1 msg rdy, bit2+bit1+bit0 is TCAS info and Comm-B bcast #2 msg rdy, 8-15 N/A, 16-31 req to send N-15 segments
	um = shortdata >> 13 & 0x3F #transponder status readouts, no decoding information available

	altitude = decode_alt(shortdata & 0x1FFF, True)

	return [fs, dr, um, altitude]



def parse5(shortdata, parity, ecc):
#	shortdata = long(shortdata, 16)
	fs = shortdata >> 24 & 0x07 #flight status: 0 is airborne normal, 1 is ground normal, 2 is airborne alert, 3 is ground alert, 4 is alert SPI, 5 is normal SPI
	dr = shortdata >> 19 & 0x1F #downlink request: 0 means no req, bit 0 is Comm-B msg rdy bit, bit 1 is TCAS info msg rdy, bit 2 is Comm-B bcast #1 msg rdy, bit2+bit0 is Comm-B bcast #2 msg rdy,
								#bit2+bit1 is TCAS info and Comm-B bcast #1 msg rdy, bit2+bit1+bit0 is TCAS info and Comm-B bcast #2 msg rdy, 8-15 N/A, 16-31 req to send N-15 segments
	um = shortdata >> 13 & 0x3F #transponder status readouts, no decoding information available

	return [fs, dr, um]

def parse11(shortdata, parity, ecc):
#	shortdata = long(shortdata, 16)
	interrogator = ecc & 0x0F
	
	ca = shortdata >> 13 & 0x3F #capability
	icao24 = shortdata & 0xFFFFFF

	return [icao24, interrogator, ca]

#def parse17(shortdata, longdata, parity, ecc):
#	shortdata = long(shortdata, 16)
#	longdata = long(longdata, 16)
#	parity = long(parity, 16)
#	ecc = long(ecc, 16)

#	subtype = (longdata >> 51) & 0x1F;

	#the subtypes are:
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


#	if subtype == 4:
#		retstr = parseBDS08(shortdata, longdata, parity, ecc)
#	elif subtype >= 9 and subtype <= 18:
#		retstr = parseBDS05(shortdata, longdata, parity, ecc)
#	elif subtype == 19:
#		subsubtype = (longdata >> 48) & 0x07
#		if subsubtype == 0:
#			retstr = parseBDS09_0(shortdata, longdata, parity, ecc)
#		elif subsubtype == 1:
#			retstr = parseBDS09_1(shortdata, longdata, parity, ecc)
#		else:
#			retstr = "BDS09 subtype " + str(subsubtype) + " not implemented"
#	else:
#		retstr = "Type 17, subtype " + str(subtype) + " not implemented"

#	return retstr

def parseBDS08(shortdata, longdata, parity, ecc):
	icao24 = shortdata & 0xFFFFFF

	msg = ""
	for i in range(0, 8):
		msg += charmap( longdata >> (42-6*i) & 0x3F)

	#retstr = "Type 17 subtype 04 (ident) from " + "%x" % icao24 + " with data " + msg

	return msg

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


#lkplist is the last known position, for emitter-centered decoding. evenlist and oddlist are the last 
#received encoded position data for each reporting type. all dictionaries indexed by ICAO number.
lkplist = {}
evenlist = {}
oddlist = {}
evenlist_ground = {}
oddlist_ground = {}

#the above dictionaries are all in the format [lat, lon, time].

def parseBDS05(shortdata, longdata, parity, ecc):
	icao24 = shortdata & 0xFFFFFF

	encoded_lon = longdata & 0x1FFFF
	encoded_lat = (longdata >> 17) & 0x1FFFF
	cpr_format = (longdata >> 34) & 1

	enc_alt = (longdata >> 36) & 0x0FFF

	altitude = decode_alt(enc_alt, False)

	[decoded_lat, decoded_lon, rnge, bearing] = cpr_decode(icao24, encoded_lat, encoded_lon, cpr_format, evenlist, oddlist, lkplist, 0, longdata)

	return [altitude, decoded_lat, decoded_lon, rnge, bearing]


#welp turns out it looks like there's only 17 bits in the BDS0,6 ground packet after all. fuck.
def parseBDS06(shortdata, longdata, parity, ecc):
	icao24 = shortdata & 0xFFFFFF

	encoded_lon = longdata & 0x1FFFF
	encoded_lat = (longdata >> 17) & 0x1FFFF
	cpr_format = (longdata >> 34) & 1

#	enc_alt = (longdata >> 36) & 0x0FFF

	altitude = 0

	[decoded_lat, decoded_lon, rnge, bearing] = cpr_decode(icao24, encoded_lat, encoded_lon, cpr_format, evenlist_ground, oddlist_ground, lkplist, 1, longdata)

	return [altitude, decoded_lat, decoded_lon, rnge, bearing]


def parseBDS09_0(shortdata, longdata, parity, ecc):
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

	#retstr = "Type 17 subtype 09-0 (track report) from " + "%x" % icao24 + " with velocity " + "%.0f" % velocity + "kt heading " + "%.0f" % heading + " VS " + "%.0f" % vert_spd

	return [velocity, heading, vert_spd]

def parseBDS09_1(shortdata, longdata, parity, ecc):
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

	#retstr = "Type 17 subtype 09-1 (track report) from " + "%x" % icao24 + " with velocity " + "%.0f" % velocity + "kt heading " + "%.0f" % heading + " VS " + "%.0f" % vert_spd

	return [velocity, heading, vert_spd]

def parse20(shortdata, longdata, parity, ecc):
	return "Message 20 not yet implemented"


