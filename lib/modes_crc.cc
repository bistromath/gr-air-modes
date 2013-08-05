/*
 * Copyright 2007 Free Software Foundation, Inc.
 *
 * This file is part of GNU Radio
 *
 * GNU Radio is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2, or (at your option)
 * any later version.
 *
 * GNU Radio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Radio; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

//this is copied almost verbatim from Eric Cottrell's gr-air platform.

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <stdio.h>
#include <gr_air_modes/types.h>
#include <gr_air_modes/modes_crc.h>
#include <math.h>
#include <stdlib.h>

/*  Mode S Parity Table
 *   Index is bit position with bit 0 being the first bit after preamble
 *   On short frames an offset of 56 is used.
*/
const unsigned int modes_crc_table[112] =
{
    0x3935ea,  // Start of Long Frame CRC
    0x1c9af5,
    0xf1b77e,
    0x78dbbf,
    0xc397db,
    0x9e31e9,
    0xb0e2f0,
    0x587178,
    0x2c38bc,
    0x161c5e,
    0x0b0e2f,
    0xfa7d13,
    0x82c48d,
    0xbe9842,
    0x5f4c21,
    0xd05c14,
    0x682e0a,
    0x341705,
    0xe5f186,
    0x72f8c3,
    0xc68665,
    0x9cb936,
    0x4e5c9b,
    0xd8d449,
    0x939020,
    0x49c810,
    0x24e408,
    0x127204,
    0x093902,
    0x049c81,
    0xfdb444,
    0x7eda22,
    0x3f6d11, // Extended 56 bit field
    0xe04c8c,
    0x702646,
    0x381323,
    0xe3f395,
    0x8e03ce,
    0x4701e7,
    0xdc7af7,
    0x91c77f,
    0xb719bb,
    0xa476d9,
    0xadc168,
    0x56e0b4,
    0x2b705a,
    0x15b82d,
    0xf52612,
    0x7a9309,
    0xc2b380,
    0x6159c0,
    0x30ace0,
    0x185670,
    0x0c2b38,
    0x06159c,
    0x030ace,
    0x018567,
    0xff38b7,  // Start of Short Frame CRC
    0x80665f,
    0xbfc92b,
    0xa01e91,
    0xaff54c,
    0x57faa6,
    0x2bfd53,
    0xea04ad,
    0x8af852,
    0x457c29,
    0xdd4410,
    0x6ea208,
    0x375104,
    0x1ba882,
    0x0dd441,
    0xf91024,
    0x7c8812,
    0x3e4409,
    0xe0d800,
    0x706c00,
    0x383600,
    0x1c1b00,
    0x0e0d80,
    0x0706c0,
    0x038360,
    0x01c1b0,
    0x00e0d8,
    0x00706c,
    0x003836,
    0x001c1b,
    0xfff409,
    0x800000,   // 24 PI or PA bits
    0x400000,
    0x200000,
    0x100000,
    0x080000,
    0x040000,
    0x020000,
    0x010000,
    0x008000,
    0x004000,
    0x002000,
    0x001000,
    0x000800,
    0x000400,
    0x000200,
    0x000100,
    0x000080,
    0x000040,
    0x000020,
    0x000010,
    0x000008,
    0x000004,
    0x000002,
    0x000001,
};

int modes_check_crc(unsigned char data[], int length)
{
	int crc=0, i;
	for(i = 0; i < length; i++)
	{
		if(data[i/8] & (1 << (7-(i%8))))
		{
			crc ^= modes_crc_table[i+(112-length)];
		}
	}
    return crc;
}
