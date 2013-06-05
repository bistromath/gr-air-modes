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
from optparse import OptionParser
import air_modes
import zmq
import threading
import time

DOWNLINK_DATA_TYPE = "dl_data"

#ZMQ message publisher.
#TODO: limit high water mark
#TODO: limit number of subscribers
class radio_publisher(threading.Thread):
  def __init__(self, port, context, queue):
    threading.Thread.__init__(self)
    self._queue = queue
    self._publisher = context.socket(zmq.PUB)
    if port is None:
      self._publisher.bind("inproc://modes-radio-pub")
    else:
      self._publisher.bind("tcp://*:%i" % port)

    self.setDaemon(True)
    self.shutdown = threading.Event()
    self.finished = threading.Event()
    self.start()

  def run(self):
    done_yet = False
    while not self.shutdown.is_set() and not done_yet:
      if self.shutdown.is_set(): #gives it another round after done is set
        done_yet = True      #so we can clean up the last of the queue
      while not self._queue.empty_p():
        self._publisher.send_multipart([DOWNLINK_DATA_TYPE, self._queue.delete_head().to_string()])
      time.sleep(0.1) #can use time.sleep(0) to yield, but it'll suck a whole CPU
    self._publisher.close()
    self.finished.set()
      

class modes_radio (gr.top_block, pubsub):
  def __init__(self, options, context):
    gr.top_block.__init__(self)
    pubsub.__init__(self)
    self._options = options
    self._queue = gr.msg_queue()
    
    rate = int(options.rate)
    use_resampler = False
    self.time_source = None

    self._setup_source(options)

    self.rx_path = air_modes.rx_path(rate, options.threshold, self._queue, options.pmf)

    #now subscribe to set various options via pubsub
    self.subscribe("FREQ", self.set_freq)
    self.subscribe("GAIN", self.set_gain)
    self.subscribe("RATE", self.set_rate)
    self.subscribe("RATE", self.rx_path.set_rate)
    self.subscribe("THRESHOLD", self.rx_path.set_threshold)
    self.subscribe("PMF", self.rx_path.set_pmf)

    self.publish("FREQ", self.get_freq)
    self.publish("GAIN", self.get_gain)
    self.publish("RATE", self.get_rate)
    self.publish("THRESHOLD", self.rx_path.get_threshold)
    self.publish("PMF", self.rx_path.get_pmf)

    if use_resampler:
        self.lpfiltcoeffs = gr.firdes.low_pass(1, 5*3.2e6, 1.6e6, 300e3)
        self.resample = blks2.rational_resampler_ccf(interpolation=5, decimation=4, taps=self.lpfiltcoeffs)
        self.connect(self._u, self.resample, self.rx_path)
    else:
        self.connect(self._u, self.rx_path)

    #Publish messages when they come back off the queue
    server_addr = ["inproc://modes-radio-pub"]
    if options.tcp is not None:
        server_addr += ["tcp://*:%i"] % options.tcp

    self._sender = air_modes.zmq_pubsub_iface(context, subaddr=None, pubaddr=server_addr)
    self._async_sender = gru.msgq_runner(self._queue, self.send)

  def send(self, msg):
    self._sender["dl_data"] = msg.to_string()

  @staticmethod
  def add_radio_options(parser):
    parser.add_option("-R", "--subdev", type="string",
                      help="select USRP Rx side A or B", metavar="SUBDEV")
    parser.add_option("-A", "--antenna", type="string",
                      help="select which antenna to use on daughterboard")
    parser.add_option("-D", "--args", type="string",
                      help="arguments to pass to radio constructor", default="")
    parser.add_option("-f", "--freq", type="eng_float", default=1090e6,
                      help="set receive frequency in Hz [default=%default]", metavar="FREQ")
    parser.add_option("-g", "--gain", type="int", default=None,
                      help="set RF gain", metavar="dB")
    parser.add_option("-r", "--rate", type="eng_float", default=4000000,
                      help="set ADC sample rate [default=%default]")
    parser.add_option("-T", "--threshold", type="eng_float", default=5.0,
                      help="set pulse detection threshold above noise in dB [default=%default]")
    parser.add_option("-F","--filename", type="string", default=None,
                      help="read data from file instead of radio")
    parser.add_option("-o","--osmocom", action="store_true", default=False,
                      help="Use gr-osmocom source (RTLSDR or HackRF) instead of UHD source")
    parser.add_option("-p","--pmf", action="store_true", default=False,
                      help="Use pulse matched filtering")


  #these are wrapped with try/except because file sources and udp sources
  #don't have set_center_freq/set_gain functions. this should check to see
  #the type of self._u.
  def set_freq(self, freq):
    try:
        result = self._u.set_center_freq(freq, 0)
        return result
    except:
        return 0

  def set_gain(self, gain):
    try:
      self._u.set_gain(gain)
    except:
      pass

  def set_rate(self, rate):
    try:
      self._u.set_rate(rate)
    except:
      pass

  def get_freq(self, freq):
      try:
        return self._u.get_center_freq(freq, 0)
      except:
        pass
    
  def get_gain(self, gain):
    try:
      return self._u.get_gain()
    except:
      pass

  def get_rate(self, rate):
    try:
      return self._u.get_rate()
    except:
      pass

  def _setup_source(self, options):
    if options.filename is None and options.udp is None and options.osmocom is None:
      #UHD source by default
      from gnuradio import uhd
      self._u = uhd.single_usrp_source(options.args, uhd.io_type_t.COMPLEX_FLOAT32, 1)

      if(options.subdev):
        self._u.set_subdev_spec(options.subdev, 0)

      if not self._u.set_center_freq(options.freq):
        print "Failed to set initial frequency"

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

      self._u.set_samp_rate(options.rate)
      options.rate = int(self._u.get_samp_rate()) #retrieve actual

      if options.gain is None: #set to halfway
        g = self._u.get_gain_range()
        options.gain = (g.start()+g.stop()) / 2.0

      print "Setting gain to %i" % options.gain
      self._u.set_gain(options.gain)
      print "Gain is %i" % self._u.get_gain()

    #TODO: detect if you're using an RTLSDR or Jawbreaker
    #and set up accordingly.
    #ALSO TODO: Actually set gain appropriately using gain bins in HackRF driver.
    elif options.osmocom: #RTLSDR dongle or HackRF Jawbreaker
        import osmosdr
        self._u = osmosdr.source_c(options.args)
#        self._u.set_sample_rate(3.2e6) #fixed for RTL dongles
        self._u.set_sample_rate(options.rate)
        if not self._u.set_center_freq(options.freq):
            print "Failed to set initial frequency"

        self._u.set_gain_mode(0) #manual gain mode
        if options.gain is None:
            options.gain = 34
###DO NOT COMMIT
        self._u.set_gain(14, "RF", 0)
        self._u.set_gain(40, "IF", 0)
        self._u.set_gain(14, "RF", 0)
###DO NOT COMMIT
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

  def cleanup(self):
    self._sender.close()
