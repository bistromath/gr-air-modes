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

#ifndef INCLUDED_AIR_MODES_SLICER_H
#define INCLUDED_AIR_MODES_SLICER_H

#include <gnuradio/block.h>
#include <gr_air_modes/api.h>
#include <gnuradio/msg_queue.h>

namespace gr {
namespace air_modes {

/*!
 * \brief mode select slicer
 * \ingroup block
 */
class AIR_MODES_API slicer : virtual public gr::sync_block
{
public:
    typedef boost::shared_ptr<slicer> sptr;
    static sptr make(gr::msg_queue::sptr queue);
};

} //namespace air_modes
} //namespace gr

#endif /* INCLUDED_AIR_MODES_SLICER_H */
