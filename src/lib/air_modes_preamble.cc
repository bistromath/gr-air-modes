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

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <air_modes_preamble.h>
#include <gr_io_signature.h>
#include <modes_energy.h>
#include <string.h>
#include <iostream>

air_modes_preamble_sptr air_make_modes_preamble(int channel_rate, float threshold_db)
{
	return air_modes_preamble_sptr (new air_modes_preamble(channel_rate, threshold_db));
}

air_modes_preamble::air_modes_preamble(int channel_rate, float threshold_db) :
    gr_sync_block ("modes_preamble",
                   gr_make_io_signature2 (2, 2, sizeof(float), sizeof(float)), //stream 0 is received data, stream 1 is moving average for reference
                   gr_make_io_signature (1, 1, sizeof(float))) //the original data. we pass it out in order to use tags.
{
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = channel_rate / d_chip_rate; //must be integer number of samples per chip to work
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 7.5 * d_samples_per_symbol; //only search to this far from the end of the stream buffer
	d_threshold_db = threshold_db;
	d_threshold = powf(10., threshold_db/10.); //the level that the sample must be above the moving average in order to qualify as a pulse
	set_output_multiple(1+d_check_width*2);
	std::stringstream str;
	str << name() << unique_id();
	d_me = pmt::pmt_string_to_symbol(str.str());
	d_key = pmt::pmt_string_to_symbol("preamble_found");
	//set_history(d_check_width);
}

int air_modes_preamble::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	//do things!
	const float *inraw = (const float *) input_items[0];
	const float *inavg = (const float *) input_items[1];
	
	float *outraw = (float *) output_items[0];

	int size = noutput_items - d_check_width;
	int pulse_offsets[4];
	float bit_energies[4];
	
	memcpy(outraw, inraw, size * sizeof(float));
	
	uint64_t abs_out_sample_cnt = nitems_written(0);

	for(int i = d_samples_per_chip; i < size; i++) {
		float pulse_threshold = bit_energy(&inavg[i], d_samples_per_chip) * d_threshold;
		bool valid_preamble = false;
		float gate_sum_now = 0, gate_sum_early = 0, gate_sum_late = 0;

		if(bit_energy(&inraw[i], d_samples_per_chip) > pulse_threshold) { //if the sample is greater than the reference level by the specified amount
			int gate_sum = early_late(&inraw[i], d_samples_per_chip); //see modes_energy.cc
			if(gate_sum != 0) continue; //if either the early gate or the late gate had greater energy, keep moving.
			//the packets are so short we choose not to do any sort of closed-loop synchronization after this simple gating. 
			//if we get a good center sample, the drift should be negligible.
			pulse_offsets[0] = 0;
			pulse_offsets[1] = int(1.0 * d_samples_per_symbol);
			pulse_offsets[2] = int(3.5 * d_samples_per_symbol);
			pulse_offsets[3] = int(4.5 * d_samples_per_symbol);

			bit_energies[0] = bit_energy(&inraw[i+pulse_offsets[0]], d_samples_per_chip);
			bit_energies[1] = bit_energy(&inraw[i+pulse_offsets[1]], d_samples_per_chip);
			bit_energies[2] = bit_energy(&inraw[i+pulse_offsets[2]], d_samples_per_chip);
			bit_energies[3] = bit_energy(&inraw[i+pulse_offsets[3]], d_samples_per_chip);

			//search for the rest of the pulses at their expected positions
			if( bit_energies[1] < pulse_threshold) continue;
			if( bit_energies[2] < pulse_threshold) continue;
			if( bit_energies[3] < pulse_threshold) continue;

			valid_preamble = true; //this gets falsified by the following statements to disqualify a preamble

			float avgpeak = (bit_energies[0] + bit_energies[1] + bit_energies[2] + bit_energies[3]) / 4;

			float space_threshold = bit_energies[0] / d_threshold; //set the threshold requirement for spaces (0 chips) to threshold dB below the current peak
			//search between pulses and all the way out to 8.0us to make sure there are no pulses inside the "0" chips. make sure all the samples are <= (inraw[peak] * d_threshold).
			//so 0.5us has to be < space_threshold, as does (1.5-3), 4, (5-7.5) in order to qualify.
			for(int j = 1.5 * d_samples_per_symbol; j <= 3 * d_samples_per_symbol; j+=d_samples_per_chip) 
				if(bit_energy(&inraw[i+j], d_samples_per_chip) > space_threshold) valid_preamble = false;
			for(int j = 5 * d_samples_per_symbol; j <= 7.5 * d_samples_per_symbol; j+=d_samples_per_chip)
				if(bit_energy(&inraw[i+j], d_samples_per_chip) > space_threshold) valid_preamble = false;

			//make sure all four peaks are within 3dB of each other
			float minpeak = avgpeak * 0.5;//-3db, was 0.631; //-2db
			float maxpeak = avgpeak * 2.0;//3db, was 1.585; //2db

			if(bit_energies[0] < minpeak || bit_energies[0] > maxpeak) continue;
			if(bit_energies[1] < minpeak || bit_energies[1] > maxpeak) continue;
			if(bit_energies[2] < minpeak || bit_energies[2] > maxpeak) continue;
			if(bit_energies[3] < minpeak || bit_energies[3] > maxpeak) continue;
		}

		if(valid_preamble) {
			//get a more accurate chip center by finding the energy peak across all four preamble peaks
			//there's some weirdness in the early part, so i ripped it out.
			bool early, late;
			do {
				early = late = false;
				gate_sum_early= bit_energy(&inraw[i+pulse_offsets[0]-1], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[1]-1], d_samples_per_chip)
						      + bit_energy(&inraw[i+pulse_offsets[2]-1], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[3]-1], d_samples_per_chip);
							  
				gate_sum_now =  bit_energy(&inraw[i+pulse_offsets[0]], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[1]], d_samples_per_chip)
						      + bit_energy(&inraw[i+pulse_offsets[2]], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[3]], d_samples_per_chip);
				
				gate_sum_late = bit_energy(&inraw[i+pulse_offsets[0]+1], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[1]+1], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[2]+1], d_samples_per_chip)
							  + bit_energy(&inraw[i+pulse_offsets[3]+1], d_samples_per_chip);

				early = (gate_sum_early > gate_sum_now);
				late = (gate_sum_late > gate_sum_now);
				if(late) i++;
				//else if(early) i--;
				//if(early && late) early = late = false;
			} while(late);
	
			//finally after all this, let's post the preamble!
			add_item_tag(0, //stream ID
			             nitems_written(0)+i, //sample
			             d_key,      //preamble_found
			             pmt::PMT_T, //meaningless for us
			             d_me        //block src id
			            );
		}
	}
	return size;
}
