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

#ifndef INCLUDED_AIR_MODES_UPLINK_H
#define INCLUDED_AIR_MODES_UPLINK_H

#include <gr_block.h>
#include <gr_msg_queue.h>
#include <air_modes_api.h>

class air_modes_uplink;
typedef boost::shared_ptr<air_modes_uplink> air_modes_uplink_sptr;

AIR_MODES_API air_modes_uplink_sptr air_make_modes_uplink(int channel_rate, float threshold_db, gr_msg_queue_sptr queue);

/*!
 * \brief mode select uplink detection
 * \ingroup block
 */
class AIR_MODES_API air_modes_uplink : public gr_block
{
private:
    friend air_modes_uplink_sptr air_make_modes_uplink(int channel_rate, float threshold_db, gr_msg_queue_sptr queue);
    air_modes_uplink(int channel_rate, float threshold_db, gr_msg_queue_sptr queue);

    int d_check_width;
    float d_symbol_rate;
    float d_uplink_length_us;
    int d_samples_per_symbol;
    float d_threshold_db;
    float d_threshold;
    pmt::pmt_t d_me, d_key;
    gr_tag_t d_timestamp;
    double d_secs_per_sample;
    gr_msg_queue_sptr d_queue;
    std::ostringstream d_payload;

public:
    int general_work (int noutput_items,
              gr_vector_int &ninput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};

#endif /* INCLUDED_AIR_MODES_UPLINK_H */
