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

#include <air_modes_slicer.h>
#include <gr_io_signature.h>
#include <air_modes_types.h>
#include <sstream>
#include <iomanip>
#include <modes_parity.h>
#include <gr_tag_info.h>
#include <iostream>

extern "C"
{
#include <stdio.h>
#include <string.h>
}

air_modes_slicer_sptr air_make_modes_slicer(int channel_rate, gr_msg_queue_sptr queue)
{
	return air_modes_slicer_sptr (new air_modes_slicer(channel_rate, queue));
}

air_modes_slicer::air_modes_slicer(int channel_rate, gr_msg_queue_sptr queue) :
    gr_sync_block ("modes_slicer",
                   gr_make_io_signature (1, 1, sizeof(float)), //stream 0 is received data, stream 1 is binary preamble detector output
                   gr_make_io_signature (0, 0, 0) )
{
	//initialize private data here
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = 2;//FIXME this is constant now channel_rate / d_chip_rate;
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 120 * d_samples_per_symbol; //how far you will have to look ahead
	d_queue = queue;
	d_secs_per_sample = 1.0 / d_chip_rate;

	set_output_multiple(1+d_check_width * 2); //how do you specify buffer size for sinks?
}

//FIXME i'm sure this exists in gr
static bool pmtcompare(pmt::pmt_t x, pmt::pmt_t y)
{
  uint64_t t_x, t_y;
  t_x = pmt::pmt_to_uint64(pmt::pmt_tuple_ref(x, 0));
  t_y = pmt::pmt_to_uint64(pmt::pmt_tuple_ref(y, 0));
  return t_x < t_y;
}

//this slicer is courtesy of Lincoln Labs. supposedly it is more resistant to mode A/C FRUIT.
//see http://adsb.tc.faa.gov/WG3_Meetings/Meeting8/Squitter-Lon.pdf
static slice_result_t slicer(const float bit0, const float bit1, const float ref) {
	slice_result_t result;

	//3dB limits for bit slicing and confidence measurement
	float highlimit=ref*2;
	float lowlimit=ref*0.5;
	
	bool firstchip_inref  = ((bit0 > lowlimit) && (bit0 < highlimit));
	bool secondchip_inref = ((bit1 > lowlimit) && (bit1 < highlimit));

	if(firstchip_inref && !secondchip_inref) {
		result.decision = 1;
		result.confidence = 1;
	}
	else if(secondchip_inref && !firstchip_inref) {
		result.decision = 0;
		result.confidence = 1;
	} 
	else if(firstchip_inref && secondchip_inref) {
		result.decision = bit0 > bit1;
		result.confidence = 0;
	}
	else {//if(!firstchip_inref && !secondchip_inref) {
		result.decision = bit0 > bit1;
		if(result.decision) {
			if(bit1 < lowlimit * 0.5) result.confidence = 1;
			else result.confidence = 0;
		} else {
			if(bit0 < lowlimit * 0.5) result.confidence = 1;
			else result.confidence = 0;
		}
	}
	return result;
}

/*
static double pmt_to_timestamp(pmt::pmt_t tstamp, uint64_t sample_cnt, double secs_per_sample) {
	double frac;
	uint64_t secs, sample, sample_age;

	if(gr_tags::get_name(tstamp) != "time") return 0;
	
	secs = pmt_to_uint64(pmt_tuple_ref(gr_tags::get_value(tstamp), 0));
	frac = pmt_to_double(pmt_tuple_ref(gr_tags::get_value(tstamp), 1));
	sample = gr_tags::get_nitems(d_timestamp);
	//now we have to offset the timestamp based on the current sample number
	sample_age = (sample_cnt + i) - sample;
	return sample_age * secs_per_sample + frac + secs;
}
*/
int air_modes_slicer::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	const float *in = (const float *) input_items[0];
	int size = noutput_items - d_check_width; //since it's a sync block, i assume that it runs with ninput_items = noutput_items

	int i;
	static int n_ok=0, n_badcrc=0, n_loconf=0, n_zeroes=0;
	
	std::vector<pmt::pmt_t> tags;
	uint64_t abs_sample_cnt = nitems_read(0);
	get_tags_in_range(tags, 0, abs_sample_cnt, abs_sample_cnt + size, pmt::pmt_string_to_symbol("preamble_found"));
	std::vector<pmt::pmt_t>::iterator tag_iter;
	
	for(tag_iter = tags.begin(); tag_iter != tags.end(); tag_iter++) {
		uint64_t i = gr_tags::get_nitems(*tag_iter) - abs_sample_cnt;
		modes_packet rx_packet;

		memset(&rx_packet.data, 0x00, 14 * sizeof(unsigned char));
		memset(&rx_packet.lowconfbits, 0x00, 24 * sizeof(unsigned char));
		rx_packet.numlowconf = 0;

		//let's use the preamble to get a reference level for the packet
		//fixme: a better thing to do is create a bi-level avg 1 and avg 0
		//through simple statistics, then take the median for your slice level
		//this won't improve decoding but will improve confidence
		rx_packet.reference_level = (in[i]
								   + in[i+2]
								   + in[i+7]
								   + in[i+9]) / 4.0;

		i += 16; //move on up to the first bit of the packet data
		//now let's slice the header so we can determine if it's a short pkt or a long pkt
		unsigned char pkt_hdr = 0;
		for(int j=0; j < 5; j++) {
			slice_result_t slice_result = slicer(in[i+j*2], in[i+j*2+1], rx_packet.reference_level);
			if(slice_result.decision) pkt_hdr += 1 << (4-j);
		}
		if(pkt_hdr == 17) rx_packet.type = Long_Packet;
		else rx_packet.type = Short_Packet;
		int packet_length = (rx_packet.type == framer_packet_type(Short_Packet)) ? 56 : 112;

		//it's slice time!
		//TODO: don't repeat your work here, you already have the first 5 bits
		for(int j = 0; j < packet_length; j++) {
			slice_result_t slice_result = slicer(in[i+j*2], in[i+j*2+1], rx_packet.reference_level);

			//put the data into the packet
			if(slice_result.decision) {
				rx_packet.data[j/8] += 1 << (7-(j%8));
			}
			//put the confidence decision into the packet
			if(slice_result.confidence) {
				//rx_packet.confidence[j/8] += 1 << (7-(j%8));
			} else {
				if(rx_packet.numlowconf < 24) rx_packet.lowconfbits[rx_packet.numlowconf++] = j;
			}
		}
			
		/******************** BEGIN TIMESTAMP BS ******************/
		rx_packet.timestamp = 0;
		/*
		uint64_t abs_sample_cnt = nitems_read(0);
		std::vector<pmt::pmt_t> tags;
		uint64_t timestamp_secs, timestamp_sample, timestamp_delta;
		double timestamp_frac;
		
		get_tags_in_range(tags, 0, abs_sample_cnt, abs_sample_cnt + i, pmt::pmt_string_to_symbol("time"));
		//tags.back() is the most recent timestamp, then.
		if(tags.size() > 0) {
			d_timestamp = tags.back();
		}

		if(d_timestamp) {
			rx_packet.timestamp = pmt_to_timestamp(d_timestamp, abs_sample_cnt + i, d_secs_per_sample);
		}
		*/
		/******************* END TIMESTAMP BS *********************/
			
		//increment for the next round

		//here you might want to traverse the whole packet and if you find all 0's, just toss it. don't know why these packets turn up, but they pass ECC.
		bool zeroes = 1;
		for(int m = 0; m < 14; m++) {
			if(rx_packet.data[m]) zeroes = 0;
		}
		if(zeroes) {n_zeroes++; continue;} //toss it

		rx_packet.message_type = (rx_packet.data[0] >> 3) & 0x1F; //get the message type for the parser to conveniently use, and to make decisions on ECC methods

		if(rx_packet.type == Short_Packet && rx_packet.message_type != 11 && rx_packet.numlowconf > 2) {n_loconf++; continue;}
		if(rx_packet.message_type == 11 && rx_packet.numlowconf >= 10) {n_loconf++; continue;}
			
		rx_packet.parity = modes_check_parity(rx_packet.data, packet_length);

		//parity for packets that aren't type 11 or type 17 is encoded with the transponder ID, which we don't know
		//therefore we toss 'em if there's syndrome
		//parity for the other short packets is usually nonzero, so they can't really be trusted that far
		if(rx_packet.parity && (rx_packet.message_type == 11 || rx_packet.message_type == 17)) {n_badcrc++; continue;}

		//we no longer attempt to brute force error correct via syndrome. it really only gets you 1% additional returns,
		//at the expense of a lot of CPU time and complexity

		//we'll replicate some data by sending the message type as the first field, followed by the first 8+24=32 bits of the packet, followed by
		//56 long packet data bits if applicable (zero-padded if not), followed by parity

		d_payload.str("");
		d_payload << std::dec << std::setw(2) << std::setfill('0') << rx_packet.message_type << std::hex << " ";
		for(int m = 0; m < 4; m++) {
			d_payload << std::setw(2) << std::setfill('0') << unsigned(rx_packet.data[m]);
		}
		d_payload << " ";
		if(packet_length == 112) {
			for(int m = 4; m < 11; m++) {
				d_payload << std::setw(2) << std::setfill('0') << unsigned(rx_packet.data[m]);
			}
			d_payload << " ";
			for(int m = 11; m < 14; m++) {
				d_payload << std::setw(2) << std::setfill('0') << unsigned(rx_packet.data[m]);
			}
		} else {
			for(int m = 4; m < 11; m++) {
				d_payload << std::setw(2) << std::setfill('0') << unsigned(0);
			}
			d_payload << " ";
			for(int m = 4; m < 7; m++) {
				d_payload << std::setw(2) << std::setfill('0') << unsigned(rx_packet.data[m]);
			}
		}
			
		d_payload << " " << std::setw(6) << rx_packet.parity << " " << std::dec << rx_packet.reference_level
		          << " " << std::setprecision(10) << std::setw(10) << rx_packet.timestamp;
			gr_message_sptr msg = gr_make_message_from_string(std::string(d_payload.str()));
		d_queue->handle(msg);
		n_ok++;
		std::cout << "n_ok: " << n_ok << " n_loconf: " << n_loconf << " n_badcrc: " << n_badcrc << " n_zeroes: " << n_zeroes << std::endl;

	}

	return size;
}
