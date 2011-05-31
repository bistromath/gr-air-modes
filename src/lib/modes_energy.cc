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

#include <air_modes_types.h>
#include <modes_energy.h>

//helper functions to calculate bit energy and Eb/No

//this is a really cheesy early/late gate synchronizer. compares bit energy 
int early_late(const float *data, int samples_per_chip) {
	float gate_sum_early=0, gate_sum_now=0, gate_sum_late=0;

	gate_sum_early = bit_energy(&data[-1], samples_per_chip);
	gate_sum_now = bit_energy(&data[0], samples_per_chip);
	gate_sum_late = bit_energy(&data[1], samples_per_chip);

	if(gate_sum_early > gate_sum_now) return -1;
	else if(gate_sum_late > gate_sum_now) return 1;
	else return 0;
}

//return total bit energy of a chip centered at the current point (we bias right for even samples per chip)
float bit_energy(const float *data, int samples_per_chip) {
	return *data;
/*	float energy = 0;
	if(samples_per_chip <= 2) {
		energy = data[0];
	} else {
		for(int j = 1-samples_per_chip/2; j < samples_per_chip/2; j++) {
			energy += data[j];
		}
	}
	return energy;
*/
}
