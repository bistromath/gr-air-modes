#
# Copyright 2012, 2013 Corgan Labs, Nick Foster
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

from gnuradio import gr, blocks, filter
import air_modes_swig

class rx_path(gr.hier_block2):

    def __init__(self, rate, threshold, queue, use_pmf=False, use_dcblock=False):
        gr.hier_block2.__init__(self, "modes_rx_path",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(0,0,0))

        self._rate = int(rate)
        self._threshold = threshold
        self._queue = queue
        self._spc = int(rate/2e6)

        # Convert incoming I/Q baseband to amplitude
        self._demod = blocks.complex_to_mag_squared()
        if use_dcblock:
            self._dcblock = filter.dc_blocker_cc(100*self._spc,False)
            self.connect(self, self._dcblock, self._demod)
        else:
            self.connect(self, self._demod)
            self._dcblock = None

        self._bb = self._demod
        # Pulse matched filter for 0.5us pulses
        if use_pmf:
            self._pmf = blocks.moving_average_ff(self._spc, 1.0/self._spc)#, self._rate)
            self.connect(self._demod, self._pmf)
            self._bb = self._pmf

        # Establish baseline amplitude (noise, interference)
        self._avg = blocks.moving_average_ff(48*self._spc, 1.0/(48*self._spc))#, self._rate) # 3 preambles

        # Synchronize to Mode-S preamble
        self._sync = air_modes_swig.preamble(self._rate, self._threshold)

        # Slice Mode-S bits and send to message queue
        self._slicer = air_modes_swig.slicer(self._queue)

        # Wire up the flowgraph
        self.connect(self._bb, (self._sync, 0))
        self.connect(self._bb, self._avg, (self._sync, 1))
        self.connect(self._sync, self._slicer)

    def set_rate(self, rate):
        self._sync.set_rate(int(rate))
        self._spc = int(rate/2e6)
        self._avg.set_length_and_scale(48*self._spc, 1.0/(48*self._spc))
        if self._bb != self._demod:
            self._pmf.set_length_and_scale(self._spc, 1.0/self._spc)
#        if self._dcblock is not None:
#            self._dcblock.set_length(100*self._spc)

    def set_threshold(self, threshold):
        self._sync.set_threshold(threshold)

    def set_pmf(self, pmf):
        #TODO must be done when top block is stopped
        pass

    def get_pmf(self, pmf):
        return not (self._bb == self._demod)

    def get_threshold(self, threshold):
        return self._sync.get_threshold()

