/*
# Copyright 2013 Nick Foster
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

#include <gnuradio/io_signature.h>
#include <string.h>
#include <iostream>
#include <iomanip>
#include <gnuradio/tags.h>
#include "uplink_impl.h"

namespace gr {

air_modes::uplink::sptr air_modes::uplink::make(int channel_rate, float threshold_db, gr::msg_queue::sptr queue) {
    return gnuradio::get_initial_sptr(new air_modes::uplink_impl(channel_rate, threshold_db, queue));
}

air_modes::uplink_impl::uplink_impl(int channel_rate, float threshold_db, gr::msg_queue::sptr queue) :
    gr::block ("uplink",
                   gr::io_signature::make2 (2, 2, sizeof(float), sizeof(float)), //stream 0 is received data, stream 1 is moving average for reference
                   gr::io_signature::make (1, 1, sizeof(float))) //the output packets
{
    d_chip_rate = 4000000;
    set_rate(channel_rate);
    set_threshold(threshold_db);

    std::stringstream str;
    str << name() << unique_id();
    d_me = pmt::string_to_symbol(str.str());
    d_key = pmt::string_to_symbol("uplink_found");
    d_queue = queue;
}

void air_modes::uplink_impl::set_rate(int channel_rate) {
    d_samples_per_chip = channel_rate / d_chip_rate;
    d_samples_per_symbol = d_samples_per_chip * 2;
    d_check_width = 120 * d_samples_per_symbol;
    d_secs_per_sample = 1.0/channel_rate;
    set_output_multiple(1+d_check_width*2);
    set_history(d_samples_per_symbol);
}

void air_modes::uplink_impl::set_threshold(float threshold_db) {
    d_threshold_db = threshold_db;
    d_threshold = powf(10., threshold_db/20.);
}

float air_modes::uplink_impl::get_threshold(void) {
    return d_threshold_db;
}

int air_modes::uplink_impl::get_rate(void) {
    return d_samples_per_chip * d_chip_rate;
}

//todo: make it return a pair of some kind, otherwise you can lose precision
static double tag_to_timestamp(gr::tag_t tstamp, uint64_t abs_sample_cnt, double secs_per_sample) {
	uint64_t ts_sample, last_whole_stamp;
	double last_frac_stamp;

	if(tstamp.key == NULL || pmt::symbol_to_string(tstamp.key) != "rx_time") return 0;

	last_whole_stamp = pmt::to_uint64(pmt::tuple_ref(tstamp.value, 0));
	last_frac_stamp = pmt::to_double(pmt::tuple_ref(tstamp.value, 1));
	ts_sample = tstamp.offset;
	
	double tstime = double(abs_sample_cnt * secs_per_sample) + last_whole_stamp + last_frac_stamp;
	if(0) std::cout << "HEY WE GOT A STAMP AT " << tstime << " TICKS AT SAMPLE " << ts_sample << " ABS SAMPLE CNT IS " << abs_sample_cnt << std::endl;
	return tstime;
}

//the preamble pattern in bits
//fixme goes in .h
//these are in 0.25us increments
static const int preamble_bits[] = {1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, -1};
static double correlate_preamble(const float *in, int samples_per_chip) {
	double corr = 0.0;
	for(int i=0; i<20; i++) {
		for(int j=0; j<samples_per_chip;j++)
			corr += preamble_bits[i]*in[i*samples_per_chip+j];
	}
	return corr/(20*samples_per_chip);
}

int air_modes::uplink_impl::general_work(int noutput_items,
						  gr_vector_int &ninput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	const float *in = (const float *) input_items[0];
	const float *inavg = (const float *) input_items[1];

	int mininputs = std::min(ninput_items[0], ninput_items[1]); //they should be matched but let's be safe
	//round number of input samples down to nearest d_samples_per_chip
	//we also subtract off d_samples_per_chip to allow the bit center finder some leeway
	const int ninputs = std::max(mininputs - (mininputs % d_samples_per_symbol) - d_samples_per_symbol, 0);
	if (ninputs <= 0) { consume_each(0); return 0; }
	
	float *out = (float *) output_items[0];

	if(0) std::cout << "Uplink called with " << ninputs << " samples" << std::endl;

	uint64_t abs_sample_cnt = nitems_read(0);
	std::vector<gr::tag_t> tstamp_tags;
	get_tags_in_range(tstamp_tags, 0, abs_sample_cnt, abs_sample_cnt + ninputs, pmt::string_to_symbol("rx_time"));
	//tags.back() is the most recent timestamp, then.
	if(tstamp_tags.size() > 0) {
		d_timestamp = tstamp_tags.back();
	}
	
	for(int i=0; i < ninputs; i++) {
		float pulse_threshold = inavg[i] * d_threshold;
		//we're looking for negative pulses, since the sync
		//phase reversal bit will always be negative.
		if(in[i] < (0-fabs(pulse_threshold))) { //hey we got a candidate
			if(0) std::cout << "Pulse threshold " << (0-fabs(pulse_threshold)) << " exceeded by sample at " << in[i] << std::endl;

			while(in[i+1] < in[i] and (ninputs-112*d_samples_per_symbol) > i) i++;
			bool ugly = false;
			for(int j=0; j<8*d_samples_per_symbol; j++) {
				if(in[i+j+d_samples_per_symbol] < fabs(pulse_threshold)) ugly=true;
			}
			if(ugly) continue;
			if(0) std::cout << "Phase reversal sync found at " << i << " with value " << in[i] << std::endl;
			//now we're at the phase reversal sync bit, and we can start pulling bits out
			//next bit starts 0.5us later (2 bit periods)
			float ref_level = 0;
			for(int j=0; j<d_samples_per_symbol*2; j++) {
				ref_level += in[i+j];
			}
			ref_level /= (d_samples_per_symbol*2);
			
			i+=d_samples_per_symbol*2;


			//be sure we've got enough room in the input buffer to copy out a whole packet
			if(ninputs-i < 112*d_samples_per_symbol) {
				consume_each(std::max(i-1,0));
				if(0) std::cout << "Uplink consumed " << std::max(i-1,0) << ", returned 0 (no room)" << std::endl;
				return 0;
			}

			for(int j=0; j<ninputs; j++) {
				out[j] = in[j];
			}
			out[i] = 1;

			unsigned char bits[14];
			memset((void *) bits, 0x00, 14);
			for(int j=0; j<56; j++) {
				if(in[i+j*d_samples_per_symbol] < 0) bits[j/8] += 1 << (7-(j%8));
			}
			if(0) {
				std::cout << "Data: ";
				for(int j=0; j<7; j++) {
					std::cout << std::setw(2) << std::setfill('0') << std::hex << int(bits[j]);
				}
				std::cout << std::dec << std::endl;
			}

			//get the timestamp of the uplink tag
			double tstamp = tag_to_timestamp(d_timestamp, abs_sample_cnt + i, d_secs_per_sample);

			d_payload.str("");
			for(int m=0; m<7; m++) {
				d_payload << std::hex << std::setw(2) << std::setfill('0') << unsigned(bits[m]);
			}

			d_payload << " " << std::setw(6) << 0 << " " << std::dec << ref_level
					  << " " << std::setprecision(10) << std::setw(10) << tstamp;
            gr::message::sptr msg = gr::message::make_from_string(std::string(d_payload.str()));
			d_queue->handle(msg);
			
			//produce only one output per work call -- TODO this should probably change
			if(0) std::cout << "Uplink consumed " << i+112*d_samples_per_symbol << " with i=" << i << ", returned 112" << std::endl;

			consume_each(ninputs);
			return ninputs;
		}
	}
	
	//didn't get anything this time
	//if(1) std::cout << "Uplink consumed " << ninputs << ", returned 0" << std::endl;
	consume_each(ninputs);
	return 0;
}

} //namespace gr
