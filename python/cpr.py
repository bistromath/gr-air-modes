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
from air_modes.exceptions import *
#this implements CPR position decoding and encoding.
#the decoder is implemented as a class, cpr_decoder, which keeps state for local decoding.
#the encoder is cpr_encode([lat, lon], type (even=0, odd=1), and surface (0 for surface, 1 for airborne))

#TODO: remove range/bearing calc from CPR decoder class. you can do this outside of the decoder.

latz = 15

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

def nl(declat_in):
    if abs(declat_in) >= 87.0:
        return 1.0
    return math.floor( (2.0*math.pi) * math.acos(1.0- (1.0-math.cos(math.pi/(2.0*latz))) / math.cos( (math.pi/180.0)*abs(declat_in) )**2 )**-1)

def dlon(declat_in, ctype, surface):
    if surface:
        tmp = 90.0
    else:
        tmp = 360.0
    nlcalc = max(nl(declat_in)-ctype, 1)
    return tmp / nlcalc

def decode_lat(enclat, ctype, my_lat, surface):
    tmp1 = dlat(ctype, surface)
    tmp2 = float(enclat) / (2**17)
    j = math.floor(my_lat/tmp1) + math.floor(0.5 + ((my_lat % tmp1) / tmp1) - tmp2)

    return tmp1 * (j + tmp2)

def decode_lon(declat, enclon, ctype, my_lon, surface):
    tmp1 = dlon(declat, ctype, surface)
    tmp2 = float(enclon) / (2**17)
    m = math.floor(my_lon / tmp1) + math.floor(0.5 + ((my_lon % tmp1) / tmp1) - tmp2)

    return tmp1 * (m + tmp2)

def cpr_resolve_local(my_location, encoded_location, ctype, surface):
    [my_lat, my_lon] = my_location
    [enclat, enclon] = encoded_location

    decoded_lat = decode_lat(enclat, ctype, my_lat, surface)
    decoded_lon = decode_lon(decoded_lat, enclon, ctype, my_lon, surface)

    return [decoded_lat, decoded_lon]

def cpr_resolve_global(evenpos, oddpos, mypos, mostrecent, surface):
    #cannot resolve surface positions unambiguously without knowing receiver position
    if surface and mypos is None:
        raise CPRNoPositionError
    
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
        raise CPRBoundaryStraddleError

    if mostrecent == 0:
        rlat = rlateven
    else:
        rlat = rlatodd

    #disambiguate latitude
    if surface:
        if mypos[0] < 0:
            rlat -= 90

    dl = dlon(rlat, mostrecent, surface)
    nl_rlat = nl(rlat)

    m = math.floor(((evenpos[1]*(nl_rlat-1)-oddpos[1]*nl_rlat)/2**17)+0.5) #longitude index
    
    #when surface positions straddle a disambiguation boundary (90 degrees),
    #surface decoding will fail. this might never be a problem in real life, but it'll fail in the
    #test case. the documentation doesn't mention it.

    if mostrecent == 0:
        enclon = evenpos[1]
    else:
        enclon = oddpos[1]

    rlon = dl * ((m % max(nl_rlat-mostrecent,1)) + enclon/2.**17)

    #print "DL: %f nl: %f m: %f rlon: %f" % (dl, nl_rlat, m, rlon)
    #print "evenpos: %x, oddpos: %x, mostrecent: %i" % (evenpos[1], oddpos[1], mostrecent)

    if surface:
        #longitudes need to be resolved to the nearest 90 degree segment to the receiver.
        wat = mypos[1]
        if wat < 0:
            wat += 360
        zone = lambda lon: 90 * (int(lon) / 90)
        rlon += (zone(wat) - zone(rlon))

    #limit to (-180, 180)
    if rlon > 180:
        rlon -= 360.0

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
        self.evenlist = {}
        self.oddlist = {}
        self.evenlist_sfc = {}
        self.oddlist_sfc = {}

    def set_location(self, new_location):
        self.my_location = new_location

    def weed_poslists(self):
        for poslist in [self.evenlist, self.oddlist]:
            for key, item in tuple(poslist.items()):
                if time.time() - item[2] > 10:
                    del poslist[key]
        for poslist in [self.evenlist_sfc, self.oddlist_sfc]:
            for key, item in tuple(poslist.items()):
                if time.time() - item[2] > 25:
                    del poslist[key]

    def decode(self, icao24, encoded_lat, encoded_lon, cpr_format, surface):
        if surface:
            oddlist = self.oddlist_sfc
            evenlist = self.evenlist_sfc
        else:
            oddlist = self.oddlist
            evenlist = self.evenlist

        #add the info to the position reports list for global decoding
        if cpr_format==1:
            oddlist[icao24] = [encoded_lat, encoded_lon, time.time()]
        else:
            evenlist[icao24] = [encoded_lat, encoded_lon, time.time()]

        [decoded_lat, decoded_lon] = [None, None]

        #okay, let's traverse the lists and weed out those entries that are older than 10 seconds
        self.weed_poslists()

        if (icao24 in evenlist) \
          and (icao24 in oddlist):
            newer = (oddlist[icao24][2] - evenlist[icao24][2]) > 0 #figure out which report is newer
            [decoded_lat, decoded_lon] = cpr_resolve_global(evenlist[icao24][0:2], oddlist[icao24][0:2], self.my_location, newer, surface) #do a global decode
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
        scalar = 2.**19
    else:
        scalar = 2.**17

    #encode using 360 constant for segment size.
    dlati = dlat(ctype, False)
    yz = math.floor(scalar * ((lat % dlati)/dlati) + 0.5)
    rlat = dlati * ((yz / scalar) + math.floor(lat / dlati))

    #encode using 360 constant for segment size.
    dloni = dlon(lat, ctype, False)
    xz = math.floor(scalar * ((lon % dloni)/dloni) + 0.5)

    yz = int(yz) & (2**17-1)
    xz = int(xz) & (2**17-1)

    return (yz, xz) #lat, lon

if __name__ == '__main__':
    import sys, random
    
    rounds = 10001
    threshold = 1e-3 #0.001 deg lat/lon
    #this accuracy is highly dependent on latitude, since at high
    #latitudes the corresponding error in longitude is greater

    bs = 0
    surface = False

    lats = [i/(rounds/170.)-85 for i in range(0,rounds)]
    lons = [i/(rounds/360.)-180 for i in range(0,rounds)]

    for i in range(0, rounds):
        even_lat = lats[i]
        #even_lat = random.uniform(-85, 85)
        even_lon = lons[i]
        #even_lon = random.uniform(-180, 180)
        odd_lat = even_lat + 1e-3
        odd_lon = min(even_lon + 1e-3, 180)
        decoder = cpr_decoder([odd_lat, odd_lon])

        #encode that position
        (evenenclat, evenenclon) = cpr_encode(even_lat, even_lon, False, surface)
        (oddenclat, oddenclon)   = cpr_encode(odd_lat, odd_lon, True, surface)

        #try to perform a global decode -- this should fail since the decoder
        #only has heard one position. need two for global decoding.
        icao = random.randint(0, 0xffffff)
        try:
            evenpos = decoder.decode(icao, evenenclat, evenenclon, False, surface)
            raise Exception("CPR test failure: global decode with only one report")
        except CPRNoPositionError:
            pass

        #now try to do a real decode with the last packet's odd complement
        #watch for a boundary straddle -- this isn't fatal, it just indicates
        #that the even and odd reports lie on either side of a longitudinal boundary
        #and so you can't get a position
        try:
            (odddeclat, odddeclon, rng, brg) = decoder.decode(icao, oddenclat, oddenclon, True, surface)
        except CPRBoundaryStraddleError:
            bs += 1
            continue
        except CPRNoPositionError:
            raise Exception("CPR test failure: no decode after even/odd inputs")

        if abs(odddeclat - odd_lat) > threshold or abs(odddeclon - odd_lon) > threshold:
            print("F odddeclat: %f odd_lat: %f" % (odddeclat, odd_lat))
            print( "F odddeclon: %f odd_lon: %f" % (odddeclon, odd_lon))
            raise Exception("CPR test failure: global decode error greater than threshold")
#       else:
#           print("S odddeclat: %f odd_lat: %f" % (odddeclat, odd_lat))
#           print("S odddeclon: %f odd_lon: %f" % (odddeclon, odd_lon))

        nexteven_lat = odd_lat + 1e-3
        nexteven_lon = min(odd_lon + 1e-3, 180)

        (nexteven_enclat, nexteven_enclon) = cpr_encode(nexteven_lat, nexteven_lon, False, surface)

        #try a locally-referenced decode
        try:
            (evendeclat, evendeclon) = cpr_resolve_local([even_lat, even_lon], [nexteven_enclat, nexteven_enclon], False, surface)
        except CPRNoPositionError:
            raise Exception("CPR test failure: local decode failure to resolve")

        #check to see if the positions were valid
        if abs(evendeclat - nexteven_lat) > threshold or abs(evendeclon - nexteven_lon) > threshold:
            print("F evendeclat: %f nexteven_lat: %f evenlat: %f" % (evendeclat, nexteven_lat, even_lat))
            print("F evendeclon: %f nexteven_lon: %f evenlon: %f" % (evendeclon, nexteven_lon, even_lon))
            raise Exception("CPR test failure: local decode error greater than threshold")

    print("CPR test successful. There were %i boundary straddles over %i rounds." % (bs, rounds))
