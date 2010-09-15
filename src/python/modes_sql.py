#!/usr/bin/env python
import time, os, sys
from string import split, join
from modes_parse import *

def modes_sql(message):

	#assembles a MySQLdb query tailored to Owen's database
	#this version ignores anything that isn't Type 17 for now, because we just don't care

	[msgtype, shortdata, longdata, parity, ecc, reference] = message.split()

	shortdata = long(shortdata, 16)
	longdata = long(longdata, 16)
	parity = long(parity, 16)
	ecc = long(ecc, 16)
#	reference = float(reference)

	msgtype = int(msgtype)

	query = None

#	if msgtype == 0:
#		query = sql0(shortdata, parity, ecc)
#	elif msgtype == 4:
#		query = sql4(shortdata, parity, ecc)
#	elif msgtype == 5:
#		query = sql5(shortdata, parity, ecc)
#	elif msgtype == 11:
#		query = sql11(shortdata, parity, ecc)
#	elif msgtype == 17:
	if msgtype == 17:
		query = sql17(shortdata, longdata, parity, ecc)
#	elif msgtype == 20:
#		output = parse20(shortdata, longdata, parity, ecc)
#	else:
		#output = "No handler for message type " + str(msgtype) + " from " + str(ecc)

#	output = "(%.0f) " % float(reference) + output

	return query

def sql17(shortdata, longdata, parity, ecc):
	icao24 = shortdata & 0xFFFFFF	
	subtype = (longdata >> 51) & 0x1F

	retstr = None

	if subtype == 4:
		msg = parseBDS08(shortdata, longdata, parity, ecc)
		retstr = "INSERT INTO plane_metadata (icao, ident) VALUES ('" + "%x" % icao24 + "', '" + msg + "') ON DUPLICATE KEY UPDATE seen=now(), ident=values(ident)"

	elif subtype >= 5 and subtype <= 8:
		[altitude, decoded_lat, decoded_lon, rnge, bearing] = parseBDS06(shortdata, longdata, parity, ecc)
		if decoded_lat is None: #no unambiguously valid position available
			retstr = None
		else:
			retstr = "INSERT INTO plane_positions (icao, seen, alt, lat, lon) VALUES ('" + "%x" % icao24 + "', now(), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"

	elif subtype >= 9 and subtype <= 18 and subtype != 15: #i'm eliminating type 15 records because they don't appear to be valid position reports.
		[altitude, decoded_lat, decoded_lon, rnge, bearing] = parseBDS05(shortdata, longdata, parity, ecc)
		if decoded_lat is None: #no unambiguously valid position available
			retstr = None
		else:
			retstr = "INSERT INTO plane_positions (icao, seen, alt, lat, lon) VALUES ('" + "%x" % icao24 + "', now(), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"

	elif subtype == 19:
		subsubtype = (longdata >> 48) & 0x07
		if subsubtype == 0:
			[velocity, heading, vert_spd] = parseBDS09_0(shortdata, longdata, parity, ecc)
			retstr = "INSERT INTO plane_metadata (icao, seen, speed, heading, vertical) VALUES ('" + "%x" % icao24 + "', now(), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ") ON DUPLICATE KEY UPDATE seen=now(), speed=values(speed), heading=values(heading), vertical=values(vertical)"

		elif subsubtype == 1:
			[velocity, heading, vert_spd] = parseBDS09_1(shortdata, longdata, parity, ecc)
			retstr = "INSERT INTO plane_metadata (icao, seen, speed, heading, vertical) VALUES ('" + "%x" % icao24 + "', now(), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ") ON DUPLICATE KEY UPDATE seen=now(), speed=values(speed), heading=values(heading), vertical=values(vertical)"

	else:
		print "debug (modes_sql): unknown subtype %i with data %x %x %x" % (subtype, shortdata, longdata, parity,)


	return retstr




