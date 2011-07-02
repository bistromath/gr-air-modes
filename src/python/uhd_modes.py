#!/usr/bin/env python
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

my_position = [37.76225, -122.44254]
#my_position = [37.409066,-122.077836]
#my_position = None

from gnuradio import gr, gru, optfir, eng_notation, blks2, air
from gnuradio import uhd
from gnuradio.eng_option import eng_option
from optparse import OptionParser
import time, os, sys, threading
from string import split, join
from usrpm import usrp_dbid
from modes_print import modes_output_print
from modes_sql import modes_output_sql
from modes_sbs1 import modes_output_sbs1
from modes_kml import modes_kml
import gnuradio.gr.gr_threading as _threading
import csv

class top_block_runner(_threading.Thread):
    def __init__(self, tb):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.tb = tb
        self.done = False
        self.start()

    def run(self):
        self.tb.run()
        self.done = True

class adsb_rx_block (gr.top_block):
  def __init__(self, options, args, queue):
    gr.top_block.__init__(self)

    self.options = options
    self.args = args
    rate = int(options.rate)

    if options.filename is None:
      self.u = uhd.single_usrp_source("", uhd.io_type_t.COMPLEX_FLOAT32, 1)

      if(options.rx_subdev_spec is None):
        options.rx_subdev_spec = ""
      self.u.set_subdev_spec(options.rx_subdev_spec)
      if not options.antenna is None:
        self.u.set_antenna(options.antenna)

      self.u.set_samp_rate(rate)
      rate = int(self.u.get_samp_rate()) #retrieve actual

      if options.gain is None: #set to halfway
        g = self.u.get_gain_range()
        options.gain = (g.start()+g.stop()) / 2.0

      if not(self.tune(options.freq)):
        print "Failed to set initial frequency"

      print "Setting gain to %i" % (options.gain,)
      self.u.set_gain(options.gain)
      print "Gain is %i" % (self.u.get_gain(),)

    else:
      self.u = gr.file_source(gr.sizeof_gr_complex, options.filename)

    print "Rate is %i" % (rate,)

    pass_all = 0
    if options.output_all :
      pass_all = 1

    self.demod = gr.complex_to_mag()
    self.avg = gr.moving_average_ff(100, 1.0/100, 400)
    
    #the DBSRX especially tends to be spur-prone; the LPF keeps out the
    #spur multiple that shows up at 2MHz
    self.lpfiltcoeffs = gr.firdes.low_pass(1, rate, 1.8e6, 200e3)
    self.lpfilter = gr.fir_filter_ccc(1, self.lpfiltcoeffs)
    
    self.preamble = air.modes_preamble(rate, options.threshold)
    #self.framer = air.modes_framer(rate)
    self.slicer = air.modes_slicer(rate, queue)
    
    self.connect(self.u, self.lpfilter, self.demod)
    self.connect(self.demod, self.avg)
    self.connect(self.demod, (self.preamble, 0))
    self.connect(self.avg, (self.preamble, 1))
    self.connect((self.preamble, 0), (self.slicer, 0))

  def tune(self, freq):
    result = self.u.set_center_freq(freq, 0)
    return result

if __name__ == '__main__':
  usage = "%prog: [options] output filename"
  parser = OptionParser(option_class=eng_option, usage=usage)
  parser.add_option("-R", "--rx-subdev-spec", type="string",
          help="select USRP Rx side A or B", metavar="SUBDEV")
  parser.add_option("-A", "--antenna", type="string",
          help="select which antenna to use on daughterboard")
  parser.add_option("-f", "--freq", type="eng_float", default=1090e6,
                      help="set receive frequency in Hz [default=%default]", metavar="FREQ")
  parser.add_option("-g", "--gain", type="int", default=None,
                      help="set RF gain", metavar="dB")
  parser.add_option("-r", "--rate", type="eng_float", default=4000000,
                      help="set ADC sample rate [default=%default]")
  parser.add_option("-T", "--threshold", type="eng_float", default=3.0,
                      help="set pulse detection threshold above noise in dB [default=%default]")
  parser.add_option("-a","--output-all", action="store_true", default=False,
                      help="output all frames")
  parser.add_option("-F","--filename", type="string", default=None,
            help="read data from file instead of USRP")
  parser.add_option("-K","--kml", type="string", default=None,
                      help="filename for Google Earth KML output")
  parser.add_option("-P","--sbs1", action="store_true", default=False,
                      help="open an SBS-1-compatible server on port 30003")
  parser.add_option("-n","--no-print", action="store_true", default=False,
                      help="disable printing decoded packets to stdout")
  parser.add_option("-l","--location", type="string", default=None,
                      help="GPS coordinates of receiving station in format xx.xxxxx,xx.xxxxx")
  (options, args) = parser.parse_args()

  if options.location is not None:
    reader = csv.reader([options.location])
    my_position = reader.next()

  queue = gr.msg_queue()
  
  outputs = [] #registry of plugin output functions
  updates = [] #registry of plugin update functions

  if options.kml is not None:
    sqlport = modes_output_sql(my_position, 'adsb.db') #create a SQL parser to push stuff into SQLite
    outputs.append(sqlport.insert)
    #also we spawn a thread to run every 30 seconds (or whatever) to generate KML
    kmlgen = modes_kml('adsb.db', options.kml, my_position) #create a KML generating thread which reads the database

  if options.sbs1 is True:
    sbs1port = modes_output_sbs1(my_position)
    outputs.append(sbs1port.output)
    updates.append(sbs1port.add_pending_conns)
    
  if options.no_print is not True:
    outputs.append(modes_output_print(my_position).parse)

  fg = adsb_rx_block(options, args, queue)
  runner = top_block_runner(fg)

  while 1:
    try:
      #the update registry is really for the SBS1 plugin -- we're looking for new TCP connections.
      #i think we have to do this here rather than in the output handler because otherwise connections will stack up
      #until the next output arrives
      for update in updates:
        update()
      
      #main message handler
      if queue.empty_p() == 0 :
        while queue.empty_p() == 0 :
          msg = queue.delete_head() #blocking read

          for out in outputs:
            out(msg.to_string())

      elif runner.done:
        raise KeyboardInterrupt
      else:
        time.sleep(0.1)

    except KeyboardInterrupt:
      fg.stop()
      runner = None
      if options.kml is not None:
          kmlgen.done = True
      break
