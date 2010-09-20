#!/usr/bin/env python
#from string import split, join
#from math import pi, floor, cos, acos
import math, time
#this implements CPR position decoding.

latz = 15
nbits = 17
#my_lat = 37.76225 #update these later!
#my_lon = -122.44254
#ER
my_lat = 37.40889176297184
my_lon = -122.07765340805054


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
		return tmp / nlcalc

def decode_lat(enclat, ctype, my_lat, surface):
	tmp1 = dlat(ctype, surface)
	tmp2 = float(enclat) / (2**nbits)
	j = math.floor(my_lat/tmp1) + math.floor(0.5 + (mod(my_lat, tmp1) / tmp1) - tmp2)
#	print "dlat gives " + "%.6f " % tmp1 + "with j = " + "%.6f " % j + " and tmp2 = " + "%.6f" % tmp2 + " given enclat " + "%x" % enclat

	return tmp1 * (j + tmp2)

def decode_lon(declat, enclon, ctype, my_lon, surface):
	tmp1 = dlon(declat, ctype, surface)
	tmp2 = float(enclon) / (2.0**nbits)
	m = math.floor(my_lon / tmp1) + math.floor(0.5 + (mod(my_lon, tmp1) / tmp1) - tmp2)
#	print "dlon gives " + "%.6f " % tmp1 + "with m = " + "%.6f " % m + " and tmp2 = " + "%.6f" % tmp2 + " given enclon " + "%x" % enclon

	return tmp1 * (m + tmp2)


def mod(a, b):
	if a < 0:
		a += 360.0

	return a - b * math.floor(a / b)

def cpr_resolve_local(my_location, encoded_location, ctype, surface):
	[my_lat, my_lon] = my_location
	[enclat, enclon] = encoded_location



	decoded_lat = decode_lat(enclat, ctype, my_lat, surface)
	decoded_lon = decode_lon(decoded_lat, enclon, ctype, my_lon, surface)

	return [decoded_lat, decoded_lon]

def cpr_resolve_global(evenpos, oddpos, mostrecent, surface): #ok this is considered working, tentatively
	dlateven = dlat(0, surface);
	dlatodd  = dlat(1, surface);

#	print dlateven;
#	print dlatodd;

	evenpos = [float(evenpos[0]), float(evenpos[1])]
	oddpos = [float(oddpos[0]), float(oddpos[1])]

	#print "Even position: %x, %x\nOdd position: %x, %x" % (evenpos[0], evenpos[1], oddpos[0], oddpos[1],)

	j = math.floor(((59*evenpos[0] - 60*oddpos[0])/2**nbits) + 0.5) #latitude index

	#print "Latitude index: %i" % j #should be 6, getting 5?

	rlateven = dlateven * (mod(j, 60)+evenpos[0]/2**nbits)
	rlatodd  = dlatodd  * (mod(j, 59)+ oddpos[0]/2**nbits)

	#print "Rlateven: %f\nRlatodd: %f" % (rlateven, rlatodd,)

	if nl(rlateven) != nl(rlatodd):
		#print "Boundary straddle!"
		return (None, None,)

	if mostrecent == 0:
		rlat = rlateven
	else:
		rlat = rlatodd

	if rlat > 90:
		rlat = rlat - 180.0

	dl = dlon(rlat, mostrecent, surface)
	nlthing = nl(rlat)
	ni = nlthing - mostrecent

	#print "ni is %i" % ni

	m =  math.floor(((evenpos[1]*(nlthing-1)-oddpos[1]*(nlthing))/2**nbits)+0.5) #longitude index, THIS LINE IS CORRECT
	#print "m is %f" % m #should be -16


	if mostrecent == 0:
		enclon = evenpos[1]
	else:
		enclon = oddpos[1]

	rlon = dl * (mod(ni+m, ni)+enclon/2**nbits)

	if rlon > 180:
		rlon = rlon - 360.0

	return [rlat, rlon]


def cpr_decode(icao24, encoded_lat, encoded_lon, cpr_format, evenlist, oddlist, lkplist, surface, longdata):
	#this is a stopgap measure to catch those packets which aren't really position packets. what gives?
#	if encoded_lat == 0 or encoded_lon == 0:
		#print "debug: lat or lon zero for longdata %x" % (longdata,)
#		return [None, None, None, None]

	if cpr_format==1:
		oddlist[icao24] = [encoded_lat, encoded_lon, time.time()]
	else:
		evenlist[icao24] = [encoded_lat, encoded_lon, time.time()]

	[decoded_lat, decoded_lon] = [None, None]

	#okay, let's traverse the lists and weed out those entries that are older than 15 minutes, as they're unlikely to be useful.
	for key, item in lkplist.items():
		if time.time() - item[2] > 900:
			del lkplist[key]

	for key, item in evenlist.items():
		if time.time() - item[2] > 900:
			del evenlist[key]

	for key, item in oddlist.items():
		if time.time() - item[2] > 900:
			del oddlist[key]

	#here we perform global/emitter-centered CPR decoding as follows:
	#first, check for the ICAO number in the planelist. if there is a decoded position in there, use that for emitter-centered decoding and be done with it.

	if surface==1:
		validrange = 45
	else:
		validrange = 180

	if icao24 in lkplist:
		#print "debug: icao found in LKP table. EC decoding with local position list %s" % str(lkplist[icao24][0:2])
		[decoded_lat, decoded_lon] = cpr_resolve_local(lkplist[icao24][0:2], [encoded_lat, encoded_lon], cpr_format, surface) #do emitter-centered local decoding
		lkplist[icao24] = [decoded_lat, decoded_lon, time.time()] #update the local position for next time

############debug info for plotting strange position reports###############
#		[lkprange, lkpbearing] = range_bearing(lkplist[icao24][0:2], [decoded_lat, decoded_lon])
#		lkpdeltat = time.time() - lkplist[icao24][2]
#		#the units are now mi/sec
#		#an SR-71 can move at 0.6 miles per second, so let's say if it's over 1.0mi/s it's probably a bug
#		if lkprange / lkpdeltat > 1.0:
#			print "debug: buggy position packet detected from icao %x, encoded lat %x, encoded lon %x, CPR format %i, longdata %x." % (icao24, encoded_lat, encoded_lon, cpr_format, longdata)
#		
############debug info for plotting strange position reports###############

	else: #no LKP available
		#print "debug: icao %x not found. attempting local decode." % icao24
		[local_lat, local_lon] = cpr_resolve_local([my_lat, my_lon], [encoded_lat, encoded_lon], cpr_format, surface) #try local decoding
#		print "debug: local resolve gives %.6f, %.6f" % (local_lat, local_lon)
		[rnge, bearing] = range_bearing([my_lat, my_lon], [local_lat, local_lon])
		if rnge < validrange: #if the local decoding can be guaranteed valid
			#print "debug: range < 180nm, position valid."
			lkplist[icao24] = [local_lat, local_lon, time.time()] #update the local position for next time
			[decoded_lat, decoded_lon] = [local_lat, local_lon]
		else: #if the local decoding can't be guaranteed valid AND you couldn't find an LKP
#			print "debug: range > %inm, attempting global decode." % validrange
			#attempt global decode
			if (icao24 in evenlist) and (icao24 in oddlist):
#				print "debug: ICAOs found in both lists."
				if abs(evenlist[icao24][2] - oddlist[icao24][2]) < 10: #if there's less than 10 seconds of time difference between the reports
#					print "debug: valid even/odd positions, performing global decode."
					newer = (oddlist[icao24][2] - evenlist[icao24][2]) > 0 #figure out which report is newer
					[decoded_lat, decoded_lon] = cpr_resolve_global(evenlist[icao24][0:2], oddlist[icao24][0:2], newer, surface) #do a global decode
					if decoded_lat is not None:
						lkplist[icao24] = [decoded_lat, decoded_lon, time.time()]
#				else:
#					print "debug: timestamps not close enough to be valid."
#			else:
#					print "debug: even/odd information not found."

	#print "settled on position: %.6f, %.6f" % (decoded_lat, decoded_lon,)
	if decoded_lat is not None:
		[rnge, bearing] = range_bearing([my_lat, my_lon], [decoded_lat, decoded_lon])
	else:
		rnge = None
		bearing = None

	return [decoded_lat, decoded_lon, rnge, bearing]



def range_bearing(loc_a, loc_b):
	[a_lat, a_lon] = loc_a
	[b_lat, b_lon] = loc_b

	esquared = (1/298.257223563)*(2-(1/298.257223563))
	earth_radius_mi = 3963.19059 * (math.pi / 180)

	delta_lat = b_lat - a_lat
	delta_lon = b_lon - a_lon

	avg_lat = (a_lat + b_lat) / 2.0

	R1 = earth_radius_mi*(1.0-esquared)/pow((1.0-esquared*pow(math.sin(avg_lat),2)),1.5)
             
	R2 = earth_radius_mi/math.sqrt(1.0-esquared*pow(math.sin(avg_lat),2))

	distance_North = R1*delta_lat
	distance_East = R2*math.cos(avg_lat)*delta_lon

	bearing = math.atan2(distance_East,distance_North) * (180.0 / math.pi)
	if bearing < 0.0:
		bearing += 360.0

	rnge = math.hypot(distance_East,distance_North)


	return [rnge, bearing]
