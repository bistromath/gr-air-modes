#
# Copyright 2012 Corgan Labs
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

from gnuradio import gr
import air_modes_swig

class rx_path(gr.hier_block2):

    def __init__(self, rate, threshold, queue):
        gr.hier_block2.__init__(self, "modes_rx_path",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(0,0,0))

        self._rate = int(rate)
        self._threshold = threshold
        self._queue = queue

        # Convert incoming I/Q baseband to amplitude
        self._demod = gr.complex_to_mag()

        # Establish baseline amplitude (noise, interference)
        self._avg = gr.moving_average_ff(100, 1.0/100, 400) # FIXME

        # Synchronize to Mode-S preamble
        self._sync = air_modes_swig.modes_preamble(self._rate, self._threshold)

        # Slice Mode-S bits and send to message queue
        self._slicer = air_modes_swig.modes_slicer(self._rate, self._queue)

        self.connect(self, self._demod, (self._sync, 0))
        self.connect(self._demod, self._avg, (self._sync, 1))
        self.connect(self._sync, self._slicer)
