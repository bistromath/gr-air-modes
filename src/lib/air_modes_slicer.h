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

#ifndef INCLUDED_AIR_MODES_slicer_H
#define INCLUDED_AIR_MODES_slicer_H

#include <gr_sync_block.h>
#include <gr_msg_queue.h>

class air_modes_slicer;
typedef boost::shared_ptr<air_modes_slicer> air_modes_slicer_sptr;

air_modes_slicer_sptr air_make_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);

/*!
 * \brief mode select slicer detection
 * \ingroup block
 */
class air_modes_slicer : public gr_sync_block
{
private:
    friend air_modes_slicer_sptr air_make_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);
    air_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);

	int d_check_width;
	int d_chip_rate;
	int d_samples_per_chip;
	int d_samples_per_symbol;
	double d_secs_per_sample;
	gr_msg_queue_sptr d_queue;
    std::ostringstream d_payload;

public:
    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};

#endif /* INCLUDED_AIR_MODES_slicer_H */
