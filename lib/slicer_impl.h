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

#ifndef INCLUDED_AIR_MODES_SLICER_IMPL_H
#define INCLUDED_AIR_MODES_SLICER_IMPL_H

#include <gnuradio/sync_block.h>
#include <gnuradio/msg_queue.h>
#include <gr_air_modes/api.h>
#include <gr_air_modes/slicer.h>

namespace gr {
namespace air_modes {

class AIR_MODES_API slicer_impl : public slicer
{
private:
    int d_check_width;
    int d_chip_rate;
    int d_samples_per_chip;
    int d_samples_per_symbol;
    gr::tag_t d_timestamp;
    gr::msg_queue::sptr d_queue;
    std::ostringstream d_payload;

public:
    slicer_impl(gr::msg_queue::sptr queue);

    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};

} //namespace air_modes
} //namespace gr

#endif /* INCLUDED_AIR_MODES_SLICER_IMPL_H */
