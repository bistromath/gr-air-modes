#!/usr/bin/python

import os, sys
from PyQt4 import QtCore,QtGui

from test import Ui_MainWindow

import air_modes

class mainwindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setObjectName("gr-air-modes Mode S receiver")

        #set defaults
        #add file, RTL, UHD sources
        self.ui.comboSource.addItems(["UHD device", "RTL-SDR", "File"])
        self.ui.comboSource.setCurrentIndex(0)

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

    #goes and gets valid antenna, sample rate options from the device and grays out appropriate things
    def populate_source_options(self):
        sourceid = self.ui.comboSource.currentText()
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
            except:
                self.rates = []
                self.antennas = []
                self.ui.combo_ant.setEnabled(False)
                self.ui.combo_rate.setEnabled(False)
                
        elif sourceid == "RTL-SDR":
            self.rates = [2.4e6]
            self.antennas = ["RX"]
            self.ui.combo_ant.setEnabled(False)
            self.ui.combo_rate.setEnabled(False)

        elif sourceid == "File":
            self.rates = [2e6, 4e6, 6e6, 8e6, 10e6]
            self.antennas = ["None"]
            self.ui.combo_ant.setEnabled(False)
            self.ui.combo_rate.setEnabled(True)

        self.ui.combo_rate.clear()
        self.ratetext = ["%.3f" % (rate / 1.e6) for rate in self.rates]
        for rate, text in zip(self.rates, self.ratetext):
            self.ui.combo_rate.addItem(text, rate)

        self.ui.combo_ant.clear()
        self.ui.combo_ant.addItems(self.antennas)

        if 4e6 in self.rates:
            self.ui.combo_rate.setCurrentIndex(self.rates.index(4e6))

    def on_comboSource_currentIndexChanged(self, index):
        self.populate_source_options()

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = mainwindow()
    window.show()
    sys.exit(app.exec_())

