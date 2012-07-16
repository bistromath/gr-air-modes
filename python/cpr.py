#!/usr/bin/env python
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

import math, time
from modes_exceptions import *
#this implements CPR position decoding and encoding.
#the decoder is implemented as a class, cpr_decoder, which keeps state for local decoding.
#the encoder is cpr_encode([lat, lon], type (even=0, odd=1), and surface (0 for surface, 1 for airborne))

latz = 15

def nbits(surface):
	if surface == 1:
		return 19
	else:
		return 17

def nz(ctype):
	return 4 * latz - ctype

def dlat(ctype, surface):
	if surface == 1:
		tmp = 90.0
	else:
		tmp = 360.0

	nzcalc = nz(ctype)
	if nzcalc == 0:
		return tmp
	else:
		return tmp / nzcalc

def nl_eo(declat_in, ctype):
	return nl(declat_in) - ctype

def nl(declat_in):
	if abs(declat_in) >= 87.0:
		return 1.0
	return math.floor( (2.0*math.pi) * pow(math.acos(1.0- (1.0-math.cos(math.pi/(2.0*latz))) / pow( math.cos( (math.pi/180.0)*abs(declat_in) ) ,2.0) ),-1.0))

def dlon(declat_in, ctype, surface):
	if surface == 1:
		tmp = 90.0
	else:
		tmp = 360.0
	nlcalc = nl_eo(declat_in, ctype)
	if nlcalc == 0:
		return tmp
	else:
		return tmp / max(nlcalc, 1.0)

def decode_lat(enclat, ctype, my_lat, surface):
	tmp1 = dlat(ctype, surface)
	tmp2 = float(enclat) / (2**nbits(surface))
	j = math.floor(my_lat/tmp1) + math.floor(0.5 + ((my_lat % tmp1) / tmp1) - tmp2)
#	print "dlat gives " + "%.6f " % tmp1 + "with j = " + "%.6f " % j + " and tmp2 = " + "%.6f" % tmp2 + " given enclat " + "%x" % enclat

	return tmp1 * (j + tmp2)

def decode_lon(declat, enclon, ctype, my_lon, surface):
	tmp1 = dlon(declat, ctype, surface)
	tmp2 = float(enclon) / (2.0**nbits(surface))
	m = math.floor(my_lon / tmp1) + math.floor(0.5 + ((my_lon % tmp1) / tmp1) - tmp2)
#	print "dlon gives " + "%.6f " % tmp1 + "with m = " + "%.6f " % m + " and tmp2 = " + "%.6f" % tmp2 + " given enclon " + "%x" % enclon

	return tmp1 * (m + tmp2)

def cpr_resolve_local(my_location, encoded_location, ctype, surface):
	[my_lat, my_lon] = my_location
	[enclat, enclon] = encoded_location

	decoded_lat = decode_lat(enclat, ctype, my_lat, surface)
	decoded_lon = decode_lon(decoded_lat, enclon, ctype, my_lon, surface)

	return [decoded_lat, decoded_lon]

def cpr_resolve_global(evenpos, oddpos, mostrecent, surface):
	dlateven = dlat(0, surface)
	dlatodd  = dlat(1, surface)

	evenpos = [float(evenpos[0]), float(evenpos[1])]
	oddpos = [float(oddpos[0]), float(oddpos[1])]
	
	j = math.floor(((nz(1)*evenpos[0] - nz(0)*oddpos[0])/2**17) + 0.5) #latitude index

	rlateven = dlateven * ((j % nz(0))+evenpos[0]/2**17)
	rlatodd  = dlatodd  * ((j % nz(1))+ oddpos[0]/2**17)

	#limit to -90, 90
	if rlateven > 270.0:
		rlateven -= 360.0
	if rlatodd > 270.0:
		rlatodd -= 360.0

	#This checks to see if the latitudes of the reports straddle a transition boundary
	#If so, you can't get a globally-resolvable location.
	if nl(rlateven) != nl(rlatodd):
		#print "Boundary straddle!"
		raise CPRBoundaryStraddleError

	if mostrecent == 0:
		rlat = rlateven
	else:
		rlat = rlatodd

	dl = dlon(rlat, mostrecent, surface)
	nlthing = nl(rlat)
	ni = max(nlthing - mostrecent, 1)

	m =  math.floor(((evenpos[1]*(nlthing-1)-oddpos[1]*(nlthing))/2**17)+0.5) #longitude index

	if mostrecent == 0:
		enclon = evenpos[1]
	else:
		enclon = oddpos[1]

	rlon = dl * (((ni+m) % ni)+enclon/2**17)

	if rlon > 180:
		rlon = rlon - 360.0

	return [rlat, rlon]


#calculate range and bearing between two lat/lon points
#should probably throw this in the mlat py somewhere or make another lib
def range_bearing(loc_a, loc_b):
	[a_lat, a_lon] = loc_a
	[b_lat, b_lon] = loc_b

	esquared = (1/298.257223563)*(2-(1/298.257223563))
	earth_radius_mi = 3963.19059 * (math.pi / 180)

	delta_lat = b_lat - a_lat
	delta_lon = b_lon - a_lon

	avg_lat = ((a_lat + b_lat) / 2.0) * math.pi / 180

	R1 = earth_radius_mi*(1.0-esquared)/pow((1.0-esquared*pow(math.sin(avg_lat),2)),1.5)

	R2 = earth_radius_mi/math.sqrt(1.0-esquared*pow(math.sin(avg_lat),2))

	distance_North = R1*delta_lat
	distance_East = R2*math.cos(avg_lat)*delta_lon

	bearing = math.atan2(distance_East,distance_North) * (180.0 / math.pi)
	if bearing < 0.0:
		bearing += 360.0

	rnge = math.hypot(distance_East,distance_North)
	return [rnge, bearing]

class cpr_decoder:
	def __init__(self, my_location):
		self.my_location = my_location
		self.lkplist = {}
		self.evenlist = {}
		self.oddlist = {}

	def set_location(new_location):
		self.my_location = new_location

	def weed_poslists(self):
		for poslist in [self.lkplist, self.evenlist, self.oddlist]:
			for key, item in poslist.items():
				if time.time() - item[2] > 900:
					del poslist[key]

	def decode(self, icao24, encoded_lat, encoded_lon, cpr_format, surface):
		#add the info to the position reports list for global decoding
		if cpr_format==1:
			self.oddlist[icao24] = [encoded_lat, encoded_lon, time.time()]
		else:
			self.evenlist[icao24] = [encoded_lat, encoded_lon, time.time()]

		[decoded_lat, decoded_lon] = [None, None]

		#okay, let's traverse the lists and weed out those entries that are older than 15 minutes, as they're unlikely to be useful.
		self.weed_poslists()

		if icao24 in self.lkplist:
			#do emitter-centered local decoding
			[decoded_lat, decoded_lon] = cpr_resolve_local(self.lkplist[icao24][0:2], [encoded_lat, encoded_lon], cpr_format, surface)
			self.lkplist[icao24] = [decoded_lat, decoded_lon, time.time()] #update the local position for next time

		elif (icao24 in self.evenlist) \
		  and (icao24 in self.oddlist) \
		  and (abs(self.evenlist[icao24][2] - self.oddlist[icao24][2]) < 10) \
		  and (surface == 0):
			newer = (self.oddlist[icao24][2] - self.evenlist[icao24][2]) > 0 #figure out which report is newer
   			[decoded_lat, decoded_lon] = cpr_resolve_global(self.evenlist[icao24][0:2], self.oddlist[icao24][0:2], newer, surface) #do a global decode
			self.lkplist[icao24] = [decoded_lat, decoded_lon, time.time()]

		#so we really can't guarantee that local decoding will work unless you are POSITIVE that you can't hear more than 180nm out.
		#this will USUALLY work, but you can't guarantee it!
		#elif surface == 1 and self.my_location is not None:
		#	[local_lat, local_lon] = cpr_resolve_local(self.my_location, [encoded_lat, encoded_lon], cpr_format, surface) #try local decoding
		#	[rnge, bearing] = range_bearing(self.my_location, [local_lat, local_lon])
		#	if rnge < validrange: #if the local decoding can be guaranteed valid
		#		self.lkplist[icao24] = [local_lat, local_lon, time.time()] #update the local position for next time
		#		[decoded_lat, decoded_lon] = [local_lat, local_lon]
		else:
			raise CPRNoPositionError

		if self.my_location is not None:
			[rnge, bearing] = range_bearing(self.my_location, [decoded_lat, decoded_lon])
		else:
			rnge = None
			bearing = None

		return [decoded_lat, decoded_lon, rnge, bearing]

#encode CPR position
def cpr_encode(lat, lon, ctype, surface):
	if surface is True:
		scalar = float(2**19)
	else:
		scalar = float(2**17)

	dlati = float(dlat(ctype, False))
	yz = math.floor(scalar * ((lat % dlati)/dlati) + 0.5)
	rlat = dlati * ((yz / scalar) + math.floor(lat / dlati))

	nleo = nl_eo(rlat, ctype)
	if nleo == 0:
		dloni = 360.0
	else:
		dloni = 360.0 / nl_eo(rlat, ctype)

	xz = math.floor(scalar * ((lon % dloni)/dloni) + 0.5)

	yz = int(yz % scalar)
	xz = int(xz % scalar)

	return (yz, xz) #lat, lon

if __name__ == '__main__':
	import sys, random

	rounds = 10000
	threshold = 1e-3 #0.001 deg lat/lon
	#this accuracy is highly dependent on latitude, since at high
	#latitudes the corresponding error in longitude is greater

	bs = 0

	for i in range(0, rounds):
		decoder = cpr_decoder(None)
		even_lat = random.uniform(-85, 85)
		even_lon = random.uniform(-180,180)
		odd_lat = even_lat + 1e-2
		odd_lon = min(even_lon + 1e-2, 180)

		#encode that position
		(evenenclat, evenenclon) = cpr_encode(even_lat, even_lon, False, False)
		(oddenclat, oddenclon)   = cpr_encode(odd_lat, odd_lon, True, False)

		#perform a global decode
		icao = random.randint(0, 0xffffff)
		try:
			evenpos = decoder.decode(icao, evenenclat, evenenclon, False, False)
			#print "CPR global decode with only one report: %f %f" % (evenpos[0], evenpos[1])
			raise Exception("CPR test failure: global decode with only one report")
		except CPRNoPositionError:
			pass

		try:
			(odddeclat, odddeclon, rng, brg) = decoder.decode(icao, oddenclat, oddenclon, True, False)
		except CPRBoundaryStraddleError:
			bs += 1
			continue
		except CPRNoPositionError:
			raise Exception("CPR test failure: no decode after even/odd inputs")

		#print "Lat: %f Lon: %f" % (ac_lat, ac_lon)

		if abs(odddeclat - odd_lat) > threshold or abs(odddeclon - odd_lon) > threshold:
			print "odddeclat: %f odd_lat: %f" % (odddeclat, odd_lat)
			print "odddeclon: %f odd_lon: %f" % (odddeclon, odd_lon)
			raise Exception("CPR test failure: global decode error greater than threshold")

		nexteven_lat = odd_lat + 1e-2
		nexteven_lon = min(odd_lon + 1e-2, 180)

		(nexteven_enclat, nexteven_enclon) = cpr_encode(nexteven_lat, nexteven_lon, False, False)

		try:
			(evendeclat, evendeclon) = cpr_resolve_local([even_lat, even_lon], [nexteven_enclat, nexteven_enclon], False, False)
		except CPRNoPositionError:
			raise Exception("CPR test failure: local decode failure to resolve")
		
		if abs(evendeclat - nexteven_lat) > threshold or abs(evendeclon - nexteven_lon) > threshold:
			raise Exception("CPR test failure: local decode error greater than threshold")

	print "CPR test successful. There were %i boundary straddles over %i rounds." % (bs, rounds)
