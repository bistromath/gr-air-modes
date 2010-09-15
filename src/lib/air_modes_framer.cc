#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <air_modes_framer.h>
#include <gr_io_signature.h>
#include <air_modes_types.h>
#include <modes_energy.h>

air_modes_framer_sptr air_make_modes_framer(int channel_rate)
{
	return air_modes_framer_sptr (new air_modes_framer(channel_rate));
}

air_modes_framer::air_modes_framer(int channel_rate) :
    gr_sync_block ("modes_framer",
                   gr_make_io_signature2 (2, 2, sizeof(float), sizeof(unsigned char)), //stream 0 is received data, stream 1 is binary preamble detector output
                   gr_make_io_signature (1, 1, sizeof(unsigned char))) //output is [0, 1, 2]: [no frame, short frame, long frame]
{
	//initialize private data here
	d_chip_rate = 2000000; //2Mchips per second
	d_samples_per_chip = channel_rate / d_chip_rate; //must be integer number of samples per chip to work
	d_samples_per_symbol = d_samples_per_chip * 2;
	d_check_width = 120 * d_samples_per_symbol; //gotta be able to look at two long frame lengths at a time in the event that FRUIT occurs near the end of the first frame

	set_output_multiple(1+d_check_width*2);
}

int air_modes_framer::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
		                  gr_vector_void_star &output_items)
{
	//do things!
	const float *inraw = (const float *) input_items[0];
	const unsigned char *inattrib = (const unsigned char *) input_items[1];
	
	//float *outraw = (float *) output_items[0];
	unsigned char *outattrib = (unsigned char *) output_items[0];

	int size = noutput_items - d_check_width; //need to be able to look ahead a full frame

	int reference_level = 0;
	framer_packet_type packet_attrib;

	for(int i = 0; i < size; i++) {

		packet_attrib = No_Packet;

		if(!inattrib[i]) {
			outattrib[i] = packet_attrib;
			continue; //if there's no preamble marker, forget it, move on
		}

		//first, assume we have a long packet
		packet_attrib = Long_Packet;

		//let's use the preamble marker to get a reference level for the packet
		reference_level = (bit_energy(&inraw[i], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(1.0*d_samples_per_symbol)], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(3.5*d_samples_per_symbol)], d_samples_per_chip) 
										 + bit_energy(&inraw[i+int(4.5*d_samples_per_symbol)], d_samples_per_chip)) / 4;

		//armed with our reference level, let's look for marks within 3dB of the reference level in bits 57-62 (65-70, see above)
		//if bits 57-62 have marks in either chip, we've got a long packet
		//otherwise we have a short packet

		//NOTE: you can change the default here to be short packet, and then check for a long packet. don't know which way is better.

		for(int j = (65 * d_samples_per_symbol); j < (70 * d_samples_per_symbol); j += d_samples_per_symbol) {
			int t_max = (bit_energy(&inraw[i+j], d_samples_per_chip) > bit_energy(&inraw[i+j+d_samples_per_chip], d_samples_per_chip)) ? bit_energy(&inraw[i+j], d_samples_per_chip) : bit_energy(&inraw[i+j+d_samples_per_chip], d_samples_per_chip);
			if(t_max < (reference_level / 2)) packet_attrib = Short_Packet;
		}

		//BUT: we must also loop through the entire packet to make sure it is clear of additional preamble markers! if it has another preamble marker, it's been FRUITed, and we must only
		//mark the new packet (i.e., just continue).

		int lookahead;
		if(packet_attrib == Long_Packet) lookahead = 112;
		else lookahead = 56;

		for(int j = i+1; j < i+(lookahead * d_samples_per_symbol); j++) {
			if(inattrib[j]) packet_attrib = Fruited_Packet; //FRUITed by mode S! in this case, we drop this first packet
			//if(inraw[j] > (reference_level * 2)) packet_attrib = Fruited_Packet; //catches strong Mode A/C fruit inside the packet
			//but good error correction should cope with that
		}

		outattrib[i] = packet_attrib;

	}

	return size;
}
