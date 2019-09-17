#!/usr/bin/env python
#
# Copyright 2012 Nick Foster
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

# azimuthal projection widget to plot reception range vs. azimuth

from PyQt4 import QtCore, QtGui
import threading
import math
from air_modes.exceptions import *
import numpy as np

# model has max range vs. azimuth in n-degree increments
# contains separate max range for a variety of altitudes so
# you can determine your altitude dropouts by bearing
# assumes that if you can hear ac at 1000', you can hear at 5000'+.
class az_map_model(QtCore.QObject):
    dataChanged = QtCore.pyqtSignal(name='dataChanged')
    npoints = 360/5
    def __init__(self, parent=None):
        super(az_map_model, self).__init__(parent)
        self._data = []
        self.lock = threading.Lock()
        self._altitudes = [0, 1000, 2000, 5000, 10000, 15000, 20000, 25000, 30000]
        #initialize everything to 0
        for i in range(0,az_map_model.npoints):
            self._data.append([0] * len(self._altitudes))

    def rowCount(self):
        return len(self._data)

    def columnCount(self):
        return len(self._altitudes)

    def data(self, row, col):
        return self._data[row][col]

    def addRecord(self, bearing, altitude, distance):
        with self.lock:
            #round up to nearest altitude in altitudes list
            #there's probably another way to do it
            if altitude >= max(self._altitudes):
                col = self.columnCount()-1
            else:
                col = self._altitudes.index(min([alt for alt in self._altitudes if alt >= altitude]))

            #find which bearing row we sit in
            row = int(int(bearing+(180./az_map_model.npoints)) / (360./az_map_model.npoints)) % az_map_model.npoints
            #set max range for all alts >= the ac alt
            #this expresses the assumption that higher ac can be heard further
            update = False
            for i in range(col, len(self._altitudes)):
                if distance > self._data[row][i]:
                    self._data[row][i] = distance
                    update = True
        if update:
            self.dataChanged.emit()

    def reset(self):
        with self.lock:
            self._data = []
            for i in range(0,az_map_model.npoints):
                self._data.append([0] * len(self._altitudes))
        self.dataChanged.emit()


# the azimuth map widget
class az_map(QtGui.QWidget):
    maxrange = 200
    bgcolor = QtCore.Qt.black
    ringpen =  QtGui.QPen(QtGui.QColor(0,   96,  127, 255), 1.3)

    def __init__(self, parent=None):
        super(az_map, self).__init__(parent)
        self._model = None
        self._paths = []
        self.maxrange = az_map.maxrange

    def minimumSizeHint(self):
        return QtCore.QSize(50, 50)

    def sizeHint(self):
        return QtCore.QSize(300, 300)

    def setModel(self, model):
        self._model = model
        self._model.dataChanged.connect(self.repaint)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        #TODO: make it not have to redraw paths EVERY repaint
        #drawing paths is VERY SLOW
        #maybe use a QTimer to limit repaints
        self.drawPaths()

        #set background
        painter.fillRect(event.rect(), QtGui.QBrush(az_map.bgcolor))

        #draw the range rings
        self.drawRangeRings(painter)
        for i in range(len(self._paths)):
            alpha = 230 * (i+1) / (len(self._paths)) + 25
            painter.setPen(QtGui.QPen(QtGui.QColor(alpha,alpha,0,255), 1.0))
            painter.drawPath(self._paths[i])

    def drawPaths(self):
        self._paths = []
        if(self._model):
            for alt in range(0, self._model.columnCount()):
                path = QtGui.QPainterPath()
                for i in range(az_map_model.npoints-1,-1,-1):
                    #bearing is to start point of arc (clockwise) 
                    bearing = (i+0.5) * 360./az_map_model.npoints
                    distance = self._model._data[i][alt]
                    radius = min(self.width(), self.height()) / 2.0
                    scale = radius * distance / self.get_range()
                    #convert bearing,distance to x,y
                    xpts = scale * math.sin(bearing * math.pi / 180)
                    ypts = scale * math.cos(bearing * math.pi / 180)
                    #get the bounding rectangle of the arc

                    arcrect = QtCore.QRectF(QtCore.QPointF(0-scale, 0-scale),
                                            QtCore.QPointF(scale, scale))

                    if path.isEmpty():
                        path.moveTo(xpts, 0-ypts) #so we don't get a line from 0,0 to the first point
                    else:
                        path.lineTo(xpts, 0-ypts)
                    path.arcTo(arcrect, 90-bearing, 360./az_map_model.npoints)

                self._paths.append(path)

    #this is just to add a little buffer space for showing the ring & range
    def get_range(self):
        return int(self.maxrange * 1.1)

    def drawRangeRings(self, painter):
        painter.translate(self.width()/2, self.height()/2)
        #choose intelligent range step -- keep it between 3-5 rings
        rangestep = 100
        while self.get_range() / rangestep < 3:
            rangestep /= 2.0
        for i in np.arange(rangestep, self.get_range(), rangestep): 
            diameter = (float(i) / self.get_range()) * min(self.width(), self.height())
            painter.setPen(az_map.ringpen)
            painter.drawEllipse(QtCore.QRectF(-diameter / 2.0,
                                -diameter / 2.0, diameter, diameter))
            painter.setPen(QtGui.QColor(255,127,0,255))

            painter.drawText(0-70/2.0, diameter/2.0, 70, 30, QtCore.Qt.AlignHCenter,
                             "%.1fnm" % i)

    def setMaxRange(self, maxrange):
        maxrange = max(3.25, maxrange)
        maxrange = min(500., maxrange)
        self.maxrange = maxrange
        self.repaint()

    def wheelEvent(self, event):
        self.setMaxRange(self.maxrange + (event.delta()/120.)*self.maxrange/4.)

class az_map_output:
    def __init__(self, cprdec, model, pub):
        self._cpr = cprdec
        self.model = model
        pub.subscribe("type17_dl", self.output)

    def output(self, msg):
        try:
            now = time.time()

            icao = msg.data["aa"]
            subtype = msg.data["ftc"]
            distance, altitude, bearing = [0,0,0]
            if 5 <= subtype <= 8:
                (ground_track, decoded_lat, decoded_lon, distance, bearing) = air_modes.parseBDS06(msg.data, self._cpr)
                altitude = 0
            elif 9 <= subtype <= 18:
                    (altitude, decoded_lat, decoded_lon, distance, bearing) = air_modes.parseBDS05(msg.data, self._cpr)

            self.model.addRecord(bearing, altitude, distance)
        except ADSBError:
            pass


##############################
# Test stuff
##############################
import random, time

class model_updater(threading.Thread):
    def __init__(self, model):
        super(model_updater, self).__init__()
        self.model = model
        self.setDaemon(1)
        self.done = False
        self.start()

    def run(self):
        for i in range(az_map_model.npoints):
            time.sleep(0.005)
            if(self.model):
                for alt in self.model._altitudes:
                    self.model.addRecord(i*360./az_map_model.npoints, alt, random.randint(0,az_map.maxrange)*alt / max(self.model._altitudes))
        self.done = True
        
class Window(QtGui.QWidget):
    def __init__(self):
        super(Window, self).__init__()
        layout = QtGui.QGridLayout()
        self.model = az_map_model()
        mymap = az_map(None)
        mymap.setModel(self.model)
        self.updater = model_updater(self.model)
        layout.addWidget(mymap, 0, 1)
        self.setLayout(layout)

if __name__ == '__main__':

    import sys

    app = QtGui.QApplication(sys.argv)
    window = Window()
    window.show()
    window.update()
    sys.exit(app.exec_())
