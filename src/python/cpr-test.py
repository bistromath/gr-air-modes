#!/usr/bin/env python

from modes_parse import *
from cpr import *
import sys

my_location = [37.76225, -122.44254]

shortdata = long(sys.argv[1], 16)
longdata = long(sys.argv[2], 16)
parity = long(sys.argv[3], 16)
ecc = long(sys.argv[4], 16)

[altitude, decoded_lat, decoded_lon, rnge, bearing] = parseBDS05(shortdata, longdata, parity, ecc)

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
