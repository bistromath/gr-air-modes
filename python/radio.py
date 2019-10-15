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
# Handles all hardware- and source-related functionality
# You pass it options, it gives you data.
# It uses the pubsub interface to allow clients to subscribe to its data feeds.

from gnuradio import gr, gru, eng_notation, filter, blocks
from gnuradio.filter import optfir
from gnuradio.eng_option import eng_option
from gnuradio.gr.pubsub import pubsub
from gnuradio.filter import pfb
from optparse import OptionParser, OptionGroup
import air_modes
import zmq
import threading
import time
import re

class modes_radio (gr.top_block, pubsub):
  def __init__(self, options, context):
    gr.top_block.__init__(self)
    pubsub.__init__(self)
    self._options = options
    self._queue = gr.msg_queue()
    self._rate = int(options.rate)

    self._resample = None
    self._setup_source(options)

    if self._rate < 4e6:
        self._resample = pfb.arb_resampler_ccf(4.e6/self._rate)
        self._rx_rate = 4e6
    else:
        self._rx_rate = self._rate

    self._rx_path = air_modes.rx_path(self._rx_rate, options.threshold,
                                      self._queue, options.pmf, options.dcblock)


    #now subscribe to set various options via pubsub
    self.subscribe("freq", self.set_freq)
    self.subscribe("gain", self.set_gain)
    self.subscribe("rate", self.set_rate)
    self.subscribe("rate", self._rx_path.set_rate)
    self.subscribe("threshold", self._rx_path.set_threshold)
    self.subscribe("pmf", self._rx_path.set_pmf)

    self.publish("freq", self.get_freq)
    self.publish("gain", self.get_gain)
    self.publish("rate", self.get_rate)
    self.publish("threshold", self._rx_path.get_threshold)
    self.publish("pmf", self._rx_path.get_pmf)

    if self._resample is not None:
        self.connect(self._u, self._resample, self._rx_path)
    else:
        self.connect(self._u, self._rx_path)

    #Publish messages when they come back off the queue
    server_addr = ["inproc://modes-radio-pub"]
    if options.tcp is not None:
        server_addr += ["tcp://*:%i" % options.tcp]

    self._sender = air_modes.zmq_pubsub_iface(context, subaddr=None, pubaddr=server_addr)
    self._async_sender = gru.msgq_runner(self._queue, self.send)

  def send(self, msg):
    self._sender["dl_data"] = msg.to_string()

  @staticmethod
  def add_radio_options(parser):
    group = OptionGroup(parser, "Receiver setup options")

    #Choose source
    group.add_option("-s","--source", type="string", default="uhd",
                      help="Choose source: uhd, osmocom, <filename>, or <ip:port> [default=%default]")
    group.add_option("-t","--tcp", type="int", default=None, metavar="PORT",
                      help="Open a TCP server on this port to publish reports")

    #UHD/Osmocom args
    group.add_option("-R", "--subdev", type="string",
                      help="select USRP Rx side A or B", metavar="SUBDEV")
    group.add_option("-A", "--antenna", type="string",
                      help="select which antenna to use on daughterboard")
    group.add_option("-D", "--args", type="string",
                      help="arguments to pass to radio constructor", default="")
    group.add_option("-f", "--freq", type="eng_float", default=1090e6,
                      help="set receive frequency in Hz [default=%default]", metavar="FREQ")
    group.add_option("-g", "--gain", type="int", default=None,
                      help="set RF gain", metavar="dB")

    #RX path args
    group.add_option("-r", "--rate", type="eng_float", default=4e6,
                      help="set sample rate [default=%default]")
    group.add_option("-T", "--threshold", type="eng_float", default=7.0,
                      help="set pulse detection threshold above noise in dB [default=%default]")
    group.add_option("-p","--pmf", action="store_true", default=True,
                      help="Use pulse matched filtering [default=%default]")
    group.add_option("-d","--dcblock", action="store_true", default=False,
                      help="Use a DC blocking filter (best for HackRF Jawbreaker) [default=%default]")

    parser.add_option_group(group)

  def live_source(self):
    return self._options.source=="uhd" or self._options.source=="osmocom"

  def set_freq(self, freq):
    return self._u.set_center_freq(freq, 0) if self.live_source() else 0

  def set_gain(self, gain):
    if self.live_source():
        self._u.set_gain(gain)
        print("Gain is %f" % self.get_gain())
    return self.get_gain()

  def set_rate(self, rate):
    if(rate < 4e6 and self._rate > 4e6):
        raise NotImplementedError("Lowering rate <4e6Msps not currently supported.")
    if(rate < 4e6):
        self._resample.set_rate(4e6/rate)
        self._rx_rate = 4e6
    else:
        self._rx_rate = rate
    self._rx_path.set_rate(self._rx_rate)
    if self._options.source in ("osmocom"):
        return self._u.set_sample_rate(rate)
    if self._options.source in ("uhd"):
        return self._u.set_rate(rate)
    else:
        return 0

  def set_threshold(self, threshold):
    self._rx_path.set_threshold(threshold)

  def get_freq(self, freq):
    return self._u.get_center_freq(freq, 0) if self.live_source() else 1090e6

  def get_gain(self):
    return self._u.get_gain() if self.live_source() else 0

  def get_rate(self):
    return self._u.get_rate() if self.live_source() else self._rate

  def _setup_source(self, options):
    if options.source == "uhd":
      #UHD source by default
      from gnuradio import uhd
      self._u = uhd.usrp_source(
          options.args,
          uhd.stream_args(
              cpu_format="fc32",
              channels=range(1),
          ),
      )

      if(options.subdev):
        self._u.set_subdev_spec(options.subdev, 0)

      if not self._u.set_center_freq(options.freq):
        print("Failed to set initial frequency")

      #check for GPSDO
      #if you have a GPSDO, UHD will automatically set the timestamp to UTC time
      #as well as automatically set the clock to lock to GPSDO.
      if self._u.get_time_source(0) != 'gpsdo':
        self._u.set_time_now(uhd.time_spec(0.0))

      if options.antenna is not None:
        self._u.set_antenna(options.antenna)

      self._u.set_samp_rate(options.rate)
      options.rate = int(self._u.get_samp_rate()) #retrieve actual

      if options.gain is None: #set to halfway
        g = self._u.get_gain_range()
        options.gain = (g.start()+g.stop()) / 2.0

      print("Setting gain to %i" % options.gain)
      self._u.set_gain(options.gain)
      print("Gain is %i" % self._u.get_gain())

    #TODO: detect if you're using an RTLSDR or Jawbreaker
    #and set up accordingly.
    elif options.source == "osmocom": #RTLSDR dongle or HackRF Jawbreaker
        import osmosdr
        self._u = osmosdr.source(options.args)
#        self._u.set_sample_rate(3.2e6) #fixed for RTL dongles
        self._u.set_sample_rate(options.rate)
        if not self._u.set_center_freq(options.freq):
            print("Failed to set initial frequency")

#        self._u.set_gain_mode(0) #manual gain mode
        if options.gain is None:
            options.gain = 34
        self._u.set_gain(options.gain)
        print("Gain is %i" % self._u.get_gain())

        #Note: this should only come into play if using an RTLSDR.
#        lpfiltcoeffs = gr.firdes.low_pass(1, 5*3.2e6, 1.6e6, 300e3)
#        self._resample = filter.rational_resampler_ccf(interpolation=5, decimation=4, taps=lpfiltcoeffs)

    else:
      #semantically detect whether it's ip.ip.ip.ip:port or filename
      if ':' in options.source:
        try:
          ip, port = re.search("(.*)\:(\d{1,5})", options.source).groups()
        except:
          raise Exception("Please input UDP source e.g. 192.168.10.1:12345")
        self._u = blocks.udp_source(gr.sizeof_gr_complex, ip, int(port))
        print("Using UDP source %s:%s" % (ip, port))
      else:
        self._u = blocks.file_source(gr.sizeof_gr_complex, options.source)
        print("Using file source %s" % options.source)

    print("Rate is %i" % (options.rate,))

  def close(self):
    self.stop()
    self.wait()
    self._sender.close()
    self._u = None
