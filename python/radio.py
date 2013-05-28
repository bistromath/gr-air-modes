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

# Radio interface for Mode S RX.
# Handles all Gnuradio-related functionality.
# You pass it options, it gives you data.
# It uses the pubsub interface to allow clients to subscribe to its data feeds.

from gnuradio import gr, gru, optfir, eng_notation, blks2
from gnuradio.eng_option import eng_option
from gnuradio.gr.pubsub import pubsub
import air_modes

DOWNLINK_DATA_TYPE = 'dl_data'

class modes_radio (gr.top_block, pubsub):
  def __init__(self, options):
    gr.top_block.__init__(self)
    pubsub.__init__(self)
    self._options = options
    self._queue = gr.msg_queue()
    
    rate = int(options.rate)
    use_resampler = False
    self.time_source = None

    self._setup_source(options)

    self.subscribe('gain', self.set_gain)
    self.subscribe('freq', self.set_freq)

    self['gain'] = options.gain
    self['freq'] = options.freq
    self['rate'] = options.rate
    self['filename'] = options.filename

    #TODO allow setting rate, threshold (drill down into slicer & preamble)

    self.rx_path = air_modes.rx_path(rate, options.threshold, self._queue, options.pmf)

    if use_resampler:
        self.lpfiltcoeffs = gr.firdes.low_pass(1, 5*3.2e6, 1.6e6, 300e3)
        self.resample = blks2.rational_resampler_ccf(interpolation=5, decimation=4, taps=self.lpfiltcoeffs)
        self.connect(self._u, self.resample, self.rx_path)
    else:
        self.connect(self._u, self.rx_path)

    #Publish messages when they come back off the queue
    self._async_rcv = gru.msgq_runner(self._queue, self.async_callback)

  def async_callback(self, msg):
    self[DOWNLINK_DATA_TYPE] = msg.to_string()

  #these are wrapped with try/except because file sources and udp sources
  #don't have set_center_freq/set_gain functions. this should check to see
  #the type of self._u.
  def set_freq(self, freq):
    try:
        result = self._u.set_center_freq(freq, 0)
        return result
    except:
        pass

  def set_gain(self, gain):
    try:
        self._u.set_gain(gain)
    except:
        pass

  def _setup_source(self, options):
    if options.filename is None and options.udp is None and options.rtlsdr is None:
      #UHD source by default
      from gnuradio import uhd
      self._u = uhd.single_usrp_source(options.args, uhd.io_type_t.COMPLEX_FLOAT32, 1)

      if(options.subdev):
        self._u.set_subdev_spec(options.subdev, 0)

      #check for GPSDO
      #if you have a GPSDO, UHD will automatically set the timestamp to UTC time
      #as well as automatically set the clock to lock to GPSDO.
      if self._u.get_time_source(0) == 'gpsdo':
        self._time_source = 'gpsdo'
      else:
        self._time_source = None
        self._u.set_time_now(uhd.time_spec(0.0))

      if options.antenna is not None:
        self._u.set_antenna(options.antenna)

      self._u.set_samp_rate(rate)
      rate = int(self._u.get_samp_rate()) #retrieve actual

      if options.gain is None: #set to halfway
        g = self._u.get_gain_range()
        options.gain = (g.start()+g.stop()) / 2.0

      print "Setting gain to %i" % options.gain
      self._u.set_gain(options.gain)
      print "Gain is %i" % self._u.get_gain()
      
    elif options.rtlsdr: #RTLSDR dongle
        import osmosdr
        self._u = osmosdr.source_c(options.args)
        self._u.set_sample_rate(3.2e6) #fixed for RTL dongles
        if not self._u.set_center_freq(options.freq):
            print "Failed to set initial frequency"

        self._u.set_gain_mode(0) #manual gain mode
        if options.gain is None:
            options.gain = 34
            
        self._u.set_gain(options.gain)
        print "Gain is %i" % self._u.get_gain()

        use_resampler = True
                
    else:
      if options.filename is not None:
        self._u = gr.file_source(gr.sizeof_gr_complex, options.filename)
      elif options.udp is not None:
        self._u = gr.udp_source(gr.sizeof_gr_complex, "localhost", options.udp)
      else:
        raise Exception("No valid source selected")
        

    print "Rate is %i" % (options.rate,)
