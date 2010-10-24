#!/usr/bin/env python
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

from modes_parse import *
from cpr import *
import sys

my_location = [37.76225, -122.44254]

shortdata = long(sys.argv[1], 16)
longdata = long(sys.argv[2], 16)
parity = long(sys.argv[3], 16)
ecc = long(sys.argv[4], 16)

parser = modes_parse(my_location)

[altitude, decoded_lat, decoded_lon, rnge, bearing] = parser.parseBDS06(shortdata, longdata, parity, ecc)

if decoded_lat is not None:
	print "Altitude: %i\nLatitude: %.6f\nLongitude: %.6f\nRange: %.2f\nBearing: %i\n" % (altitude, decoded_lat, decoded_lon, rnge, bearing,)

print "Decomposing...\n"

subtype = (longdata >> 51) & 0x1F;

encoded_lon = longdata & 0x1FFFF
encoded_lat = (longdata >> 17) & 0x1FFFF
cpr_format = (longdata >> 34) & 1

enc_alt = (longdata >> 36) & 0x0FFF

print "Subtype: %i\nEncoded longitude: %x\nEncoded latitude: %x\nCPR format: %i\nEncoded altitude: %x\n" % (subtype, encoded_lon, encoded_lat, cpr_format, enc_alt,)

#print "First argument is order %i, second %i" % ((evendata >> 34) & 1, (odddata >> 34) & 1,)

#evenencpos = [(evendata >> 17) & 0x1FFFF, evendata & 0x1FFFF]
#oddencpos = [(odddata >> 17) & 0x1FFFF, odddata & 0x1FFFF]

#[declat, declon] = cpr_decode_global(evenencpos, oddencpos, newer)

#print "Global latitude: %.6f\nGlobal longitude: %.6f" % (declat, declon,)
