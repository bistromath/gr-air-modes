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

#ifndef INCLUDED_AIR_MODES_PREAMBLE_H
#define INCLUDED_AIR_MODES_PREAMBLE_H

#include <gnuradio/block.h>
#include <gr_air_modes/api.h>

namespace gr {
namespace air_modes {

/*!
 * \brief mode select preamble detection
 * \ingroup block
 */
class AIR_MODES_API preamble : virtual public gr::block
{
public:
    typedef boost::shared_ptr<preamble> sptr;
    static sptr make(float channel_rate, float threshold_db);

    virtual void set_rate(float channel_rate) = 0;
    virtual void set_threshold(float threshold_db) = 0;
    virtual float get_rate(void) = 0;
    virtual float get_threshold(void) = 0;
};

} // namespace air_modes
} // namespace gr

#endif /* INCLUDED_AIR_MODES_PREAMBLE_H */
