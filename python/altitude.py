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

# For reference into the methodology used to decode altitude,
# see RTCA DO-181D p.42

from air_modes.exceptions import *

def decode_alt(alt, bit13):
	mbit = alt & 0x0040
	qbit = alt & 0x0010
	
	if mbit and bit13:
		#nobody uses metric altitude: AFAIK, it's an orphaned part of
		#the spec. haven't seen it in three years. as a result, replies
		#with mbit set can be considered spurious, and so we discard them here.
		
		#bits 20-25, 27-31 encode alt in meters
		#remember that bits are LSB (bit 20 is MSB)
		#meters_alt = 0
		#for (shift, bit) in enumerate(range(31,26,-1)+range(25,19,-1)):
		#	meters_alt += ((alt & (1<<bit)) != 0) << shift
		#decoded_alt = meters_alt / 0.3048
		raise MetricAltError

	if qbit: #a mode S-style reply
		#bit13 is false for BDS0,5 ADS-B squitters, and is true otherwise
		if bit13:
			#in this representation, the altitude bits are as follows:
			# 12 11 10 9 8 7 (6) 5 (4) 3 2 1 0
			# so bits 6 and 4 are the M and Q bits, respectively.
			tmp1 = (alt & 0x3F80) >> 2
			tmp2 = (alt & 0x0020) >> 1
		else:
			tmp1 = (alt & 0x1FE0) >> 1
			tmp2 = 0

		decoded_alt = ((alt & 0x0F) | tmp1 | tmp2) * 25 - 1000

	else: #a mode C-style reply
		  #okay, the order they come in is:
		  #C1 A1 C2 A2 C4 A4 X B1 D1 B2 D2 B4 D4
    	  #the order we want them in is:
    	  #D2 D4 A1 A2 A4 B1 B2 B4
    	  #so we'll reassemble into a Gray-coded representation

		if bit13 is False:
			alt = (alt & 0x003F) | (alt & 0x0FC0 << 1)

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

		bigpart =  ((alt & B4) >> 1) \
				 + ((alt & B2) >> 2) \
				 + ((alt & B1) >> 3) \
				 + ((alt & A4) >> 4) \
				 + ((alt & A2) >> 5) \
				 + ((alt & A1) >> 6) \
				 + ((alt & D4) << 6) \
				 + ((alt & D2) << 5)

		#bigpart is now the 500-foot-resolution Gray-coded binary part
		decoded_alt = gray2bin(bigpart)
		#real_alt is now the 500-foot-per-tick altitude

		cbits =   ((alt & C4) >> 8) + ((alt & C2) >> 9) + ((alt & C1) >> 10)
		cval = gray2bin(cbits) #turn them into a real number

		if cval == 7:
			cval = 5 #not a real gray code after all

		if decoded_alt % 2:
			cval = 6 - cval #since the code is symmetric this unwraps it to see whether to subtract the C bits or add them

		decoded_alt *= 500 #take care of the A,B,D data
		decoded_alt += cval * 100 #factor in the C data
		decoded_alt -= 1300 #subtract the offset

	return decoded_alt

def gray2bin(gray):
	i = gray >> 1

	while i != 0:
		gray ^= i
		i >>= 1

	return gray

def encode_alt_modes(alt, bit13):
	mbit = False
	qbit = True
	encalt = (int(alt) + 1000) / 25

	if bit13 is True:
		tmp1 = (encalt & 0xfe0) << 2
		tmp2 = (encalt & 0x010) << 1
		
	else:
		tmp1 = (encalt & 0xff8) << 1
		tmp2 = 0

	return (encalt & 0x0F) | tmp1 | tmp2 | (mbit << 6) | (qbit << 4)

if __name__ == "__main__":
	try:
		for alt in range(-1000, 101400, 25):
			dec = decode_alt(encode_alt_modes(alt, False), False)
			if dec != alt:
				print "Failure at %i with bit13 clear (got %s)" % (alt, dec)
		for alt in range(-1000, 101400, 25):
			dec = decode_alt(encode_alt_modes(alt, True), True)
			if dec != alt:
				print "Failure at %i with bit13 set (got %s)" % (alt, dec)
	except MetricAltError:
		print "Failure at %i due to metric alt bit" % alt
