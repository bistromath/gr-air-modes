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
#include <modes_energy.h>
#include <gr_tag_info.h>

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
                   gr_make_io_signature2 (2, 2, sizeof(float), sizeof(unsigned char)), //stream 0 is received data, stream 1 is binary preamble detector output
                   gr_make_io_signature (0, 0, 0) )
{
	//initialize private data here
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = channel_rate / d_chip_rate; //must be integer number of samples per chip to work
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 120 * d_samples_per_symbol; //how far you will have to look ahead
	d_queue = queue;
	d_secs_per_sample = 1.0 / channel_rate;

	set_output_multiple(1+d_check_width * 2); //how do you specify buffer size for sinks?
}

static bool pmtcompare(pmt::pmt_t x, pmt::pmt_t y)
{
  uint64_t t_x, t_y;
  t_x = pmt::pmt_to_uint64(pmt::pmt_tuple_ref(x, 0));
  t_y = pmt::pmt_to_uint64(pmt::pmt_tuple_ref(y, 0));
  return t_x < t_y;
}

int air_modes_slicer::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	//do things!
	const float *inraw = (const float *) input_items[0];
	const unsigned char *inattrib = (const unsigned char *) input_items[1];
	int size = noutput_items - d_check_width; //since it's a sync block, i assume that it runs with ninput_items = noutput_items

	int i;

	for(i = 0; i < size; i++) {
		if(inattrib[i] == framer_packet_type(Short_Packet) || inattrib[i] == framer_packet_type(Long_Packet)) { //if there's a packet starting here....		
			modes_packet rx_packet;

			int packet_length = 112;
			if(inattrib[i] == framer_packet_type(Short_Packet)) packet_length = 56;

			//printf("Packet received from framer w/length %i\n", packet_length);

			rx_packet.type = framer_packet_type(inattrib[i]);
			memset(&rx_packet.data, 0x00, 14 * sizeof(unsigned char));
			memset(&rx_packet.lowconfbits, 0x00, 24 * sizeof(unsigned char));
			rx_packet.numlowconf = 0;

			//let's use the preamble marker to get a reference level for the packet
			rx_packet.reference_level = (bit_energy(&inraw[i], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(1.0*d_samples_per_symbol)], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(3.5*d_samples_per_symbol)], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(4.5*d_samples_per_symbol)], d_samples_per_chip)) / 4;

			i += 8 * d_samples_per_symbol; //move to the center of the first bit of the data

			//here we calculate the total energy contained in each chip of the symbol
			for(int j = 0; j < packet_length; j++) {
				int firstchip = i+j*d_samples_per_symbol;
				int secondchip = firstchip + d_samples_per_chip;
				bool slice, confidence;
				float firstchip_energy=0, secondchip_energy=0;

				firstchip_energy = bit_energy(&inraw[firstchip], d_samples_per_chip);
				secondchip_energy = bit_energy(&inraw[secondchip], d_samples_per_chip);

				//3dB limits for bit slicing and confidence measurement
				float highlimit=rx_packet.reference_level*2;
				float lowlimit=rx_packet.reference_level*0.5;
				bool firstchip_inref = ((firstchip_energy > lowlimit) && (firstchip_energy < highlimit));
				bool secondchip_inref = ((secondchip_energy > lowlimit) && (secondchip_energy < highlimit));

				//these two lines for a super simple naive slicer.
//				slice = firstchip_energy > secondchip_energy;
//				confidence = bool(int(firstchip_inref) + int(secondchip_inref)); //one and only one chip in the reference zone

				//below is the Lincoln Labs slicer. it may produce greater bit errors. supposedly it is more resistant to mode A/C FRUIT.
        //see http://adsb.tc.faa.gov/WG3_Meetings/Meeting8/Squitter-Lon.pdf
				if(firstchip_inref && !secondchip_inref) {
					slice = 1;
					confidence = 1;
				}
				else if(secondchip_inref && !firstchip_inref) {
					slice = 0;
					confidence = 1;
				} 
				else if(firstchip_inref && secondchip_inref) {
					slice = firstchip_energy > secondchip_energy;
					confidence = 0;
				}
				else if(!firstchip_inref && !secondchip_inref) { //in this case, we determine the bit by whichever is larger, and we determine high confidence if the low chip is 6dB below reference.
					slice = firstchip_energy > secondchip_energy;
					if(slice) {
						if(secondchip_energy < lowlimit * 0.5) confidence = 1;
						else confidence = 0;
					} else {
						if(firstchip_energy < lowlimit * 0.5) confidence = 1;
						else confidence = 0;
					}
				}

				//put the data into the packet
				if(slice) {
					rx_packet.data[j/8] += 1 << (7-(j%8));
				}
				//put the confidence decision into the packet
				if(confidence) {
					//rx_packet.confidence[j/8] += 1 << (7-(j%8));
				} else {
					if(rx_packet.numlowconf < 24) rx_packet.lowconfbits[rx_packet.numlowconf++] = j;
				}
			}
			
			/******************** BEGIN TIMESTAMP BS ******************/
			rx_packet.timestamp_secs = 0;
			rx_packet.timestamp_frac = 0;
			
			uint64_t abs_sample_cnt = nitems_read(0);
			std::vector<pmt::pmt_t> tags;
			uint64_t timestamp_secs, timestamp_sample, timestamp_delta;
			double timestamp_frac;
			
			pmt::pmt_t timestamp = pmt::mp(pmt::mp(0), pmt::mp(0)); //so we don't barf if there isn't one
			
			get_tags_in_range(tags, 0, abs_sample_cnt, abs_sample_cnt + i, pmt::pmt_string_to_symbol("packet_time_stamp"));
			//tags.back() is the most recent timestamp, then.
			if(tags.size() > 0) {
				//if nobody but the USRP is producing timestamps this isn't necessary
				//std::sort(tags.begin(), tags.end(), pmtcompare);
				timestamp = tags.back();
			
				timestamp_secs = pmt_to_uint64(pmt_tuple_ref(gr_tags::get_value(timestamp), 0));
				timestamp_frac = pmt_to_double(pmt_tuple_ref(gr_tags::get_value(timestamp), 1));
				timestamp_sample = gr_tags::get_nitems(timestamp);
				//now we have to offset the timestamp based on the current sample number
				timestamp_delta = (abs_sample_cnt + i) - timestamp_sample;
			
				timestamp_frac += timestamp_delta * d_secs_per_sample;
				if(timestamp_frac > 1.0) {
					timestamp_frac -= 1.0;
					timestamp_secs++;
				}
			
				rx_packet.timestamp_secs = timestamp_secs;
				rx_packet.timestamp_frac = timestamp_frac;
			}

			/******************* END TIMESTAMP BS *********************/
			
			//increment for the next round
			i += packet_length * d_samples_per_symbol;

			//here you might want to traverse the whole packet and if you find all 0's, just toss it. don't know why these packets turn up, but they pass ECC.
			bool zeroes = 1;
			for(int m = 0; m < 14; m++) {
				if(rx_packet.data[m]) zeroes = 0;
			}
			if(zeroes) continue; //toss it

			rx_packet.message_type = (rx_packet.data[0] >> 3) & 0x1F; //get the message type for the parser to conveniently use, and to make decisions on ECC methods

			//we note that short packets other than type 11 CANNOT be reliably decoded, since the a/c address is encoded with the parity bits.
			//mode S in production ATC use relies on the fact that these short packets are reply squitters to transponder requests, 
			//and so the radar should already know the expected a/c reply address. so, error-correction makes no sense on short packets (other than type 11)
			//this means two things: first, we will DROP short packets (other than type 11) with ANY low-confidence bits, since we can't be confident that we're seeing real data
			//second, we will only perform error correction on LONG type S packets.

			//the limitation on short packets means in practice a short packet has to be at least 6dB above the noise floor in order to be output. long packets can theoretically
			//be decoded at the 3dB SNR point. below that and the preamble detector won't fire.
			
			//in practice, this limitation causes you to see a HUGE number of type 11 packets which pass CRC through random luck.
			//these packets necessarily have large numbers of low-confidence bits, so we toss them with an arbitrary limit of 10.
			//that's a pretty dang low threshold so i don't think we'll drop many legit packets

			if(rx_packet.type == Short_Packet && rx_packet.message_type != 11 && rx_packet.numlowconf != 0) continue;
			if(rx_packet.type == Short_Packet && rx_packet.message_type == 11 && rx_packet.numlowconf >= 10) continue;
			
			
			//if(rx_packet.numlowconf >= 24) continue; //don't even try, this is the maximum number of errors ECC could possibly correct
			//the above line should be part of ECC, and only checked if the message has parity errors

			rx_packet.parity = modes_check_parity(rx_packet.data, packet_length);

			if(rx_packet.parity && rx_packet.type == Long_Packet) {
//				long before = rx_packet.parity;
				bruteResultTypeDef bruteResult = modes_ec_brute(rx_packet);

				if(bruteResult == No_Solution) {
					//printf("No solution!\n");
					continue;
				} else if(bruteResult == Multiple_Solutions) {
//					printf("Multiple solutions!\n");
					continue;
				} else if(bruteResult == Too_Many_LCBs) {
					//printf("Too many LCBs (%i)!\n", rx_packet.numlowconf);
					continue;
				} else if(bruteResult == No_Error) {
//					printf("No error!\n");
				} else if(bruteResult == Solution_Found) {
//					printf("Solution found for %i LCBs!\n", rx_packet.numlowconf);
				}
//				rx_packet.parity = modes_check_parity(rx_packet.data, packet_length);
//				if(rx_packet.parity) printf("Error: packet fails parity check after correction, was %x, now %x\n", before, rx_packet.parity);
			}

//			if(rx_packet.parity && rx_packet.type == Long_Packet) printf("Error! Bad packet forwarded to the queue.\n");
			//now we have a complete packet with confidence data, let's print it to the message queue
			//here, rather than send the entire packet, since we've already done parity checking and ECC in C++, we'll
			//send just the data (no confidence bits), separated into fields for easier parsing.

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
			          << " " << rx_packet.timestamp_secs
			          << " " << std::setprecision(10) << std::setw(10) << rx_packet.timestamp_frac;

			gr_message_sptr msg = gr_make_message_from_string(std::string(d_payload.str()));
			d_queue->handle(msg);

		}
	}

	return size;
}
