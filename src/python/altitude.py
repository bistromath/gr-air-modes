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


#!/usr/bin/env python
#from string import split, join

#betcha this would be faster if you used a table for mode C
#you could strip out D1 since it's never used, that leaves 11 bits (table is 2048 entries)
#on the other hand doing it this way is educational for others
def decode_alt(alt, bit13):
	if alt & 0x40 and bit13 is True:
		return "METRIC ERROR"

	if alt & 0x10: #a mode S-style reply
		if bit13 is True:
			tmp1 = (alt & 0x1F80) >> 2 #first 6 bits get shifted 2 down
			tmp2 = (alt & 0x20) >> 1 #that bit gets shifted 1 down
		else:
			tmp1 = (alt & 0x0FE0) >> 1 #first 7 bits get shifted 1 down but there are only 12 bits in the representation
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

		bigpart =  ((alt & B4) >> 1) + ((alt & B2) >> 2) + ((alt & B1) >> 3) + ((alt & A4) >> 4) + ((alt & A2) >> 5) + ((alt & A1) >> 6) + ((alt & D4) << 6) + ((alt & D2) << 5)

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
