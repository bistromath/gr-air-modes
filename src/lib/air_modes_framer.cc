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

#include <air_modes_framer.h>
#include <gr_io_signature.h>
#include <air_modes_types.h>
#include <gr_tag_info.h>
#include <iostream>
#include <string.h>

air_modes_framer_sptr air_make_modes_framer(int channel_rate)
{
	return air_modes_framer_sptr (new air_modes_framer(channel_rate));
}

air_modes_framer::air_modes_framer(int channel_rate) :
    gr_sync_block ("modes_framer",
                   gr_make_io_signature (1, 1, sizeof(float)), //stream 0 is received data
                   gr_make_io_signature (1, 1, sizeof(float))) //raw samples passed back out
{
	//initialize private data here
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = channel_rate / d_chip_rate; //must be integer number of samples per chip to work
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 120 * d_samples_per_symbol; //gotta be able to look at two long frame lengths at a time
												//in the event that FRUIT occurs near the end of the first frame
	//set_history(d_check_width*2);
	
	std::stringstream str;
	str << name() << unique_id();
	d_me = pmt::pmt_string_to_symbol(str.str());
	d_key = pmt::pmt_string_to_symbol("frame_info");
}

int air_modes_framer::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	//do things!
	const float *inraw = (const float *) input_items[0];
	float *outraw = (float *) output_items[0];
	//unsigned char *outattrib = (unsigned char *) output_items[0];
	int size = noutput_items - d_check_width*2;
	if(size < 0) return 0;
	float reference_level;
	framer_packet_type packet_attrib;
	std::vector<pmt::pmt_t> tags;
	
	uint64_t abs_sample_cnt = nitems_read(0);
	get_tags_in_range(tags, 0, abs_sample_cnt, abs_sample_cnt + size, pmt::pmt_string_to_symbol("preamble_found"));
	std::vector<pmt::pmt_t>::iterator tag_iter;
	
	memcpy(outraw, inraw, size * sizeof(float));
	
	for(tag_iter = tags.begin(); tag_iter != tags.end(); tag_iter++) {
		uint64_t i = gr_tags::get_nitems(*tag_iter) - abs_sample_cnt;
		//first, assume we have a long packet
		packet_attrib = Long_Packet;

		//let's use the preamble marker to get a reference level for the packet
		reference_level = (inraw[i]
                        + inraw[i+int(1.0*d_samples_per_symbol)]
                        + inraw[i+int(3.5*d_samples_per_symbol)]
                        + inraw[i+int(4.5*d_samples_per_symbol)]) / 4;
		
		//armed with our reference level, let's look for marks within 3dB of the reference level in bits 57-62 (65-70, see above)
		//if bits 57-62 have marks in either chip, we've got a long packet
		//otherwise we have a short packet
		//NOTE: you can change the default here to be short packet, and then check for a long packet. don't know which way is better.
		for(int j = (65 * d_samples_per_symbol); j < (70 * d_samples_per_symbol); j += d_samples_per_symbol) {
			float t_max = std::max(inraw[i+j], 
			                       inraw[i+j+d_samples_per_chip]
			                      );
			if(t_max < (reference_level / 2.0)) packet_attrib = Short_Packet;
		}
		
		//BUT: we must also loop through the entire packet to make sure it is clear of additional preamble markers! 
		//if it has another preamble marker, it's been FRUITed, and we must only
		//mark the new packet (i.e., just continue).

		int lookahead;
		if(packet_attrib == Long_Packet) lookahead = 112 * d_samples_per_symbol;
		else lookahead = 56 * d_samples_per_symbol;

		//ok we have to re-do lookahead for this tagged version.
		//we can do this by looking for tags that fall within that window
		std::vector<pmt::pmt_t> fruit_tags;
		get_tags_in_range(fruit_tags, 0, abs_sample_cnt+i+1, abs_sample_cnt+i+lookahead, pmt::pmt_string_to_symbol("preamble_found"));
		if(fruit_tags.size() > 0) packet_attrib = Fruited_Packet;
		
		//insert tag here
		add_item_tag(0, //stream ID
					 nitems_written(0)+i, //sample
					 d_key,      //preamble_found
			         pmt::pmt_from_long((long)packet_attrib),
			         d_me        //block src id
			        );
	}

	return size;
}
