/*
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
*/

#ifndef AIR_MODES_TYPES_H
#define AIR_MODES_TYPES_H

typedef enum { No_Packet = 0, Short_Packet = 1, Fruited_Packet = 2, Long_Packet = 3 } framer_packet_type;
typedef enum { No_Error = 0, Solution_Found, Too_Many_LCBs, No_Solution, Multiple_Solutions } bruteResultTypeDef;

struct modes_packet {
	unsigned char data[14];
//	unsigned char confidence[14]; //112 bits of boolean high/low confidence data for each bit
	unsigned char lowconfbits[24]; //positions of low confidence bits within the packet

	unsigned long crc;
	unsigned int numlowconf;
	framer_packet_type type; //what length packet are we
	unsigned int message_type;
	float reference_level;
	double timestamp;
};

struct slice_result_t {
	bool decision;
	bool confidence;
};

#endif
