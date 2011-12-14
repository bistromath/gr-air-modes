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

#include <air_modes_int_and_dump.h>
#include <gr_io_signature.h>
#include <string.h>
#include <iostream>

air_modes_int_and_dump_sptr air_make_modes_int_and_dump(int samples_per_symbol)
{
	return air_modes_int_and_dump_sptr (new air_modes_int_and_dump(samples_per_symbol));
}

air_modes_int_and_dump::air_modes_int_and_dump(int samps_per_chip) :
    gr_block ("modes_int_and_dump",
                   gr_make_io_signature (1, 1, sizeof(float)),
                   gr_make_io_signature (1, 1, sizeof(float)))
{
    d_samples_per_symbol = samples_per_symbol;
	set_output_multiple(d_samples_per_symbol);
    set_history(d_samples_per_symbol);
    
    d_acc = 0;
    d_pos = 0;
}

int air_modes_int_and_dump::general_work(int noutput_items,
                          gr_vector_int &ninput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	const float *in = (const float *) input_items[0];
	float *out = (float *) output_items[0];

    int input_items = std::min(ninput_items[0], ninput_items[1]); //just in case

    //ok first of all we look for "preamble_found" tags in our input range.
    //get a vector of these tags, then every time we hit one
    //reset the integrator position and accumulator
    std::vector<pmt::pmt_t> tags;
	uint64_t abs_sample_cnt = nitems_read(0);
	get_tags_in_range(tags, 0, abs_sample_cnt, abs_sample_cnt + ninput_items, pmt::pmt_string_to_symbol("preamble_found"));

    int out_items = 0;

    int offset = gr_tags::get_nitems(&tags[0]) - abs_sample_cnt;

    for(int i=0; i<120*2; i++) { //for each symbol in a potential long packet
        out[out_items] = 0;
        for(int j=0; j<d_samples_per_symbol; j++) { //for each sample in the symbol
            out[out_items] += in[offset+i+j]; //integrate
        }
        out_items++;
    }

    //insert tag here
    add_item_tag(0, //stream ID
                 nitems_written(0), //sample number
                 pmt::pmt_string_to_symbol("preamble_found");
                 pmt::PMT_T,
                 pmt::pmt_string_to_symbol(unique_id());
                );

    consume_each(wat);
    return out_items;
}
