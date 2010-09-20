#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <air_modes_preamble.h>
#include <gr_io_signature.h>
#include <modes_energy.h>

air_modes_preamble_sptr air_make_modes_preamble(int channel_rate, float threshold_db)
{
	return air_modes_preamble_sptr (new air_modes_preamble(channel_rate, threshold_db));
}

air_modes_preamble::air_modes_preamble(int channel_rate, float threshold_db) :
    gr_sync_block ("modes_preamble",
                   gr_make_io_signature2 (2, 2, sizeof(float), sizeof(float)), //stream 0 is received data, stream 1 is moving average for reference
                   gr_make_io_signature (1, 1, sizeof(unsigned char)))
{
	//initialize private data here
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = channel_rate / d_chip_rate; //must be integer number of samples per chip to work
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 7.5 * d_samples_per_symbol; //only search to this far from the end of the stream buffer
	d_threshold_db = threshold_db;
	d_threshold = powf(10., threshold_db/10.); //the level that the sample must be above the moving average in order to qualify as a pulse
	set_output_multiple(1+d_check_width*2);
}

int air_modes_preamble::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	//do things!
	const float *inraw = (const float *) input_items[0];
	const float *inavg = (const float *) input_items[1];
	
	//float *outraw = (float *) output_items[0];
	unsigned char *outattrib = (unsigned char *) output_items[0];

	int size = noutput_items - d_check_width;
	int pulse_offsets[4];
	float bit_energies[4];

	for(int i = d_samples_per_chip; i < size; i++) {
		float pulse_threshold = bit_energy(&inavg[i], d_samples_per_chip) * d_threshold;
		bool valid_preamble = false;
		float gate_sum_now = 0, gate_sum_early = 0, gate_sum_late = 0;

		if(bit_energy(&inraw[i], d_samples_per_chip) > pulse_threshold) { //if the sample is greater than the reference level by the specified amount
			//while(inraw[i+1] > inraw[i]) i++;

			//if(inraw[i+1] > inraw[i]) continue; //we're still coming up on the pulse peak, so let's just fall out and look at it next time around
			//if(inraw[i-1] > inraw[i]) continue; //we're past the peak, so it's no longer a valid pulse

			//a note on the above. this simple early/late gate system works for decim = 16, but doesn't work so great for decim = 8. the extra samples, subject to noise,
			//mean the peak is not necessarily the center of the bit, and you get fooled into sampling at strange bit edges. the solution is an area integral, a real early/late gate
			//system, computing the area of a bit and maximizing so you sample at the center of the bit shape for any decimation. for decim = 16 it won't really matter since you only have
			//one possible bit center.

			int gate_sum = early_late(&inraw[i], d_samples_per_chip); //see modes_energy.cc
			if(gate_sum != 0) continue; //if either the early gate or the late gate had greater energy, keep moving.
//			if(gate_sum_late > gate_sum_now) continue;

			//the packets are so short we choose not to do any sort of closed-loop synchronization after this simple gating. if we get a good center sample, the drift should be negligible.

			pulse_offsets[0] = i;
			pulse_offsets[1] = i+int(1.0 * d_samples_per_symbol);
			pulse_offsets[2] = i+int(3.5 * d_samples_per_symbol);
			pulse_offsets[3] = i+int(4.5 * d_samples_per_symbol);

			bit_energies[0] = bit_energy(&inraw[pulse_offsets[0]], d_samples_per_chip);
			bit_energies[1] = bit_energy(&inraw[pulse_offsets[1]], d_samples_per_chip);
			bit_energies[2] = bit_energy(&inraw[pulse_offsets[2]], d_samples_per_chip);
			bit_energies[3] = bit_energy(&inraw[pulse_offsets[3]], d_samples_per_chip);

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

			//make sure all four peaks are within 2dB of each other
			

			float minpeak = avgpeak * 0.631; //-2db
			float maxpeak = avgpeak * 1.585; //2db

			if(bit_energies[0] < minpeak || bit_energies[0] > maxpeak) continue;
			if(bit_energies[1] < minpeak || bit_energies[1] > maxpeak) continue;
			if(bit_energies[2] < minpeak || bit_energies[2] > maxpeak) continue;
			if(bit_energies[3] < minpeak || bit_energies[3] > maxpeak) continue;

		}

			//just for kicks, after validating a preamble, you might want to use all four peaks to form a more accurate "average" center sample time, so that if noise corrupts the first leading edge
			//sample, you don't mis-sample the entire packet.

			//this could also be done in a separate packet, although it probably saves CPU to do it here
			//for the 2 samples per chip case, you can just add up the peaks at the expected peak times, then do the same for +1, and -1.
		if(valid_preamble) {

				gate_sum_now = bit_energies[0] + bit_energies[1] + bit_energies[2] + bit_energies[3];
//				gate_sum_early = bit_energy(&inraw[pulse_offsets[0]-1], d_samples_per_chip)
//											 + bit_energy(&inraw[pulse_offsets[1]-1], d_samples_per_chip)
//											 + bit_energy(&inraw[pulse_offsets[2]-1], d_samples_per_chip)
//											 + bit_energy(&inraw[pulse_offsets[3]-1], d_samples_per_chip);
				gate_sum_late =  bit_energy(&inraw[pulse_offsets[0]+1], d_samples_per_chip)
											 + bit_energy(&inraw[pulse_offsets[1]+1], d_samples_per_chip)
											 + bit_energy(&inraw[pulse_offsets[2]+1], d_samples_per_chip)
											 + bit_energy(&inraw[pulse_offsets[3]+1], d_samples_per_chip);
/*
			if(d_samples_per_chip <= 2) {
				gate_sum_now   = inraw[pulse_offsets[0]+0] + inraw[pulse_offsets[1]+0] + inraw[pulse_offsets[2]+0] + inraw[pulse_offsets[3]+0];
				gate_sum_early = inraw[pulse_offsets[0]-1] + inraw[pulse_offsets[1]-1] + inraw[pulse_offsets[2]-1] + inraw[pulse_offsets[3]-1];
				gate_sum_late  = inraw[pulse_offsets[0]+1] + inraw[pulse_offsets[1]+1] + inraw[pulse_offsets[2]+1] + inraw[pulse_offsets[3]+1];
			} else {
				for(int j = 1-d_samples_per_chip/2; j < d_samples_per_chip/2; j++) {
					gate_sum_now +=   inraw[j+pulse_offsets[0]+0] + inraw[j+pulse_offsets[1]+0] + inraw[j+pulse_offsets[2]+0] + inraw[j+pulse_offsets[3]+0];
					gate_sum_early += inraw[j+pulse_offsets[0]-1] + inraw[j+pulse_offsets[1]-1] + inraw[j+pulse_offsets[2]-1] + inraw[j+pulse_offsets[3]-1];
					gate_sum_late +=  inraw[j+pulse_offsets[0]+1] + inraw[j+pulse_offsets[1]+1] + inraw[j+pulse_offsets[2]+1] + inraw[j+pulse_offsets[3]+1];
				}
			}
*/
//			if(gate_sum_early > gate_sum_now) { //i think this is redundant
//				outattrib[i-1] = 1;
//			}
			/*else*/ if(gate_sum_late > gate_sum_now) {
				outattrib[i+1] = 1;
				i+=1; //so we skip the next one and don't overwrite it
			}
			else outattrib[i] = 1;

		} else outattrib[i] = 0;
	}
	return size;
}
