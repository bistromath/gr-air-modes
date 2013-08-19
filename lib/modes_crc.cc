/*
 * Copyright 2013 Nick Foster
 *
 * This file is part of gr-air-modes
 *
 * gr-air-modes is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2, or (at your option)
 * any later version.
 *
 * gr-air-modes is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with gr-air-modes; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */


#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <stdio.h>
#include <gr_air_modes/types.h>
#include <gr_air_modes/modes_crc.h>
#include <math.h>
#include <stdlib.h>

unsigned int crc_table[256];
const unsigned int POLY=0xFFF409;

//generate a bytewise lookup CRC table

void generate_crc_table(void)
{
    unsigned int crc = 0;
    for(int n=0; n<256; n++) {
        crc = n<<16;
        for(int k=0; k<8; k++) {
            if(crc & 0x800000) {
                crc = ((crc<<1) ^ POLY) & 0xFFFFFF;
            } else {
                crc = (crc<<1) & 0xFFFFFF;
            }
        }
        crc_table[n] = crc & 0xFFFFFF;
    }
}

//Perform a bytewise CRC check
unsigned int modes_check_crc(unsigned char data[], int length)
{
    if(crc_table[1] != POLY) generate_crc_table();
    unsigned int crc=0;
    for(int i=0; i<length; i++) {
        crc = crc_table[((crc>>16) ^ data[i]) & 0xff] ^ (crc << 8);
    }
    return crc & 0xFFFFFF;
}
