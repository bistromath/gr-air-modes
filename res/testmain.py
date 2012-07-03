#!/usr/bin/python

import os, sys, time, threading
from PyQt4 import QtCore,QtGui
from gnuradio import gr, gru, optfir, eng_notation, blks2
import gnuradio.gr.gr_threading as _threading
import air_modes
from test import Ui_MainWindow
import csv

class mainwindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setObjectName("gr-air-modes Mode S receiver")

        #set defaults
        #add file, RTL, UHD sources
        self.ui.combo_source.addItems(["UHD device", "RTL-SDR", "File"])
        self.ui.combo_source.setCurrentIndex(0)

        #populate antenna, rate combo boxes based on source
        self.populate_source_options()

        #should round to actual achieved gain
        self.ui.line_gain.insert("30")

        #default to 3dB
        self.ui.line_threshold.insert("3")

        self.ui.combo_ant.setCurrentIndex(self.ui.combo_ant.findText("RX2"))

        #check KML by default, leave the rest unchecked.
        self.ui.check_sbs1.setCheckState(QtCore.Qt.Unchecked)
        self.ui.check_raw.setCheckState(QtCore.Qt.Unchecked)
        self.ui.check_fgfs.setCheckState(QtCore.Qt.Unchecked)
        self.ui.check_kml.setCheckState(QtCore.Qt.Checked)

        self.ui.line_sbs1port.insert("30003")
        self.ui.line_rawport.insert("9988")
        self.ui.line_fgfsport.insert("5500")
        self.ui.line_kmlfilename.insert("modes.kml")

        #disable by default
        self.ui.check_adsbonly.setCheckState(QtCore.Qt.Unchecked)

        self.queue = gr.msg_queue(10)
        self.runner = None
        self.fg = None
        self.outputs = []
        self.updates = []
        self.output_handler = None
        self.kmlgen = None #necessary bc we stop its thread in shutdown

    #goes and gets valid antenna, sample rate options from the device and grays out appropriate things
    def populate_source_options(self):
        sourceid = self.ui.combo_source.currentText()
        self.rates = []
        self.ratetext = []
        self.antennas = []
        
        if sourceid == "UHD device":
            try:
                from gnuradio import uhd
                self.src = uhd.single_usrp_source("", uhd.io_type_t.COMPLEX_FLOAT32, 1)
                self.rates = [rate.start() for rate in self.src.get_samp_rates()]
                self.antennas = self.src.get_antennas()
                self.src = None #deconstruct UHD source for now
                self.ui.combo_ant.setEnabled(True)
                self.ui.combo_rate.setEnabled(True)
                self.ui.stack_source.setCurrentIndex(0)
            except:
                self.rates = []
                self.antennas = []
                self.ui.combo_ant.setEnabled(False)
                self.ui.combo_rate.setEnabled(False)
                self.ui.stack_source.setCurrentIndex(0)
                
        elif sourceid == "RTL-SDR":
            self.rates = [2.4e6]
            self.antennas = ["RX"]
            self.ui.combo_ant.setEnabled(False)
            self.ui.combo_rate.setEnabled(False)
            self.ui.stack_source.setCurrentIndex(0)

        elif sourceid == "File":
            self.rates = [2e6, 4e6, 6e6, 8e6, 10e6]
            self.antennas = ["None"]
            self.ui.combo_ant.setEnabled(False)
            self.ui.combo_rate.setEnabled(True)
            self.ui.stack_source.setCurrentIndex(1)

        self.ui.combo_rate.clear()
        self.ratetext = ["%.3f" % (rate / 1.e6) for rate in self.rates]
        for rate, text in zip(self.rates, self.ratetext):
            self.ui.combo_rate.addItem(text, rate)

        self.ui.combo_ant.clear()
        self.ui.combo_ant.addItems(self.antennas)

        if 4e6 in self.rates:
            self.ui.combo_rate.setCurrentIndex(self.rates.index(4e6))

    def on_combo_source_currentIndexChanged(self, index):
        self.populate_source_options()

    def on_button_start_released(self):
        #if we're already running, kill it!
        if self.runner is not None:
            self.output_handler.done = True
            self.output_handler = None
            self.fg.stop()
            self.runner = None
            if self.kmlgen is not None:
                self.kmlgen.done = True
                #TODO FIXME KMLGEN NEEDS SELFDESTRUCT
                #self.kmlgen = None

            self.ui.button_start.setText("Start")

        else: #we aren't already running, let's get this party started
            options = {}
            options["source"] = self.ui.combo_source.currentText()
            options["rate"] = int(self.ui.combo_rate.currentIndex())
            options["antenna"] = self.ui.combo_ant.currentText()
            options["gain"] = float(self.ui.line_gain.text())
            options["threshold"] = float(self.ui.line_threshold.text())
            options["filename"] = str(self.ui.line_inputfile.text())

            self.fg = adsb_rx_block(options, self.queue) #create top RX block
            self.runner = top_block_runner(self.fg) #spawn new thread to do RX

            try:
                my_position = [float(self.ui.line_my_lat.text()), float(self.ui.line_my_lon.text())]
            except:
                my_position = None

            self.outputs = []
            self.updates = []

            #output options to populate outputs, updates
            if self.ui.check_kml.checkState():
                #we spawn a thread to run every 30 seconds (or whatever) to generate KML
                self.kmlgen = air_modes.modes_kml(self.ui.line_kmlfilename.text(), my_position) #create a KML generating thread
                self.outputs.append(self.kmlgen.output)

            if self.ui.check_sbs1.checkState():
                sbs1port = int(self.ui.line_sbs1port.text())
                sbs1out = air_modes.modes_output_sbs1(my_position, sbs1port)
                self.outputs.append(sbs1out.output)
                self.updates.append(sbs1out.add_pending_conns)

            if self.ui.check_fgfs.checkState():
                fghost = "127.0.0.1" #TODO FIXME
                fgport = self.ui.line_fgfsport.currentText()
                fgout = air_modes.modes_flightgear(my_position, fghost, int(fgport))
                self.outputs.append(fgout.output)

            if self.ui.check_raw.checkState():
                rawport = air_modes.modes_raw_server(int(self.ui.line_raw.text()))
                self.outputs.append(rawport.output)
                self.updates.append(rawport.add_pending_conns)

            #add output for live data box
            self.outputs.append(self.output_live_data)

            #create output handler
            self.output_handler = output_handler(self.outputs, self.updates, self.queue)
            self.ui.button_start.setText("Stop") #modify button text

    def output_live_data(self, msg):
        self.ui.text_livedata.append(msg)


class output_handler(threading.Thread):
    def __init__(self, outputs, updates, queue):
        threading.Thread.__init__(self)
        self.setDaemon(1)
        self.outputs = outputs
        self.updates = updates
        self.queue = queue
        self.done = False
        self.start()

    def run(self):
        while self.done is False:
            for update in self.updates:
                update()
            if not self.queue.empty_p():
                msg = self.queue.delete_head()
                for output in self.outputs:
                    try:
                        output(msg.to_string())
                    except ADSBError:
                        pass

            time.sleep(0.3)

        self.done = True
        

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

#Top block for ADSB receiver. If you define a standard interface you
#can make this common code between the GUI app and the cmdline app
class adsb_rx_block (gr.top_block):
    def __init__(self, options, queue):
        gr.top_block.__init__(self)

        self.options = options
        rate = int(options["rate"])
        use_resampler = False

        if options["source"] == "UHD device":
            from gnuradio import uhd
            self.u = uhd.single_usrp_source("", uhd.io_type_t.COMPLEX_FLOAT32, 1)
            time_spec = uhd.time_spec(0.0)
            self.u.set_time_now(time_spec)
            self.u.set_antenna(options["antenna"])
            self.u.set_samp_rate(rate)
            self.u.set_gain(options["gain"])
        
        elif options["source"] == "RTL-SDR":
            import osmosdr
            self.u = osmosdr.source_c()
            self.u.set_sample_rate(2.4e6) #fixed for RTL dongles
            self.u.set_gain_mode(0) #manual gain mode
            self.u.set_gain(options["gain"])
            use_resampler = True

        elif options["source"] == "File":
            self.u = gr.file_source(gr.sizeof_gr_complex, options["filename"])

        self.demod = gr.complex_to_mag()
        self.avg = gr.moving_average_ff(100, 1.0/100, 400)
        
        self.preamble = air_modes.modes_preamble(rate, options["threshold"])
        self.slicer = air_modes.modes_slicer(rate, queue)

        if use_resampler:
            self.lpfiltcoeffs = gr.firdes.low_pass(1, 5*2.4e6, 1.2e6, 300e3)
            self.resample = blks2.rational_resampler_ccf(interpolation=5, decimation=3, taps=self.lpfiltcoeffs)
            self.connect(self.u, self.resample, self.demod)
        else:
            self.connect(self.u, self.demod)

        self.connect(self.demod, self.avg)
        self.connect(self.demod, (self.preamble, 0))
        self.connect(self.avg, (self.preamble, 1))
        self.connect((self.preamble, 0), (self.slicer, 0))

    def tune(self, freq):
        result = self.u.set_center_freq(freq, 0)
        return result

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = mainwindow()
    window.show()
    sys.exit(app.exec_())

