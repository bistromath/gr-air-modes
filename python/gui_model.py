#!/usr/bin/env python
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

# This file contains data models, view delegates, and associated classes
# for handling the GUI back end data model.

from PyQt4 import QtCore, QtGui
import air_modes
import threading, math, time
from air_modes.exceptions import *

#fades the ICAOs out as their last report gets older,
#and display ident if available, ICAO otherwise
class ICAOViewDelegate(QtGui.QStyledItemDelegate):
    def paint(self, painter, option, index):
        #draw selection rectangle
        if option.state & QtGui.QStyle.State_Selected:
            painter.setBrush(QtGui.QPalette().highlight())
            painter.drawRect(option.rect)

        #if there's an ident available, use it. otherwise print the ICAO
        if index.model().data(index.model().index(index.row(), 9)) != QtCore.QVariant():
            paintstr = index.model().data(index.model().index(index.row(), 9)).toString()
        else:
            paintstr = index.model().data(index.model().index(index.row(), 0)).toString()
        last_report = index.model().data(index.model().index(index.row(), 1)).toDouble()[0]
        age = (time.time() - last_report)
        max_age = 60. #age at which it grays out
        #minimum alpha is 0x40 (oldest), max is 0xFF (newest)
        age = min(age, max_age)
        alpha = int(0xFF - (0xBF / max_age) * age)
        painter.setPen(QtGui.QColor(0, 0, 0, alpha))
        painter.drawText(option.rect.left()+3, option.rect.top(), option.rect.width(), option.rect.height(), option.displayAlignment, paintstr)

#the data model used to display dashboard data.
class dashboard_data_model(QtCore.QAbstractTableModel):
    def __init__(self, parent):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = []
        self.lock = threading.Lock()
        self._colnames = ["icao", "seen", "rssi", "latitude", "longitude", "altitude", "speed", "heading", "vertical", "ident", "type", "range", "bearing"]
        #custom precision limits for display
        self._precisions = [None, None, None, 6, 6, 0, 0, 0, 0, None, None, 2, 0]
        for field in self._colnames:
            self.setHeaderData(self._colnames.index(field), QtCore.Qt.Horizontal, field)
    def rowCount(self, parent=QtCore.QVariant()):
        return len(self._data)
    def columnCount(self, parent=QtCore.QVariant()):
        return len(self._colnames)
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return QtCore.QVariant()
        if index.row() >= self.rowCount():
            return QtCore.QVariant()
        if index.column() >= self.columnCount():
            return QtCore.QVariant()
        if (role != QtCore.Qt.DisplayRole) and (role != QtCore.Qt.EditRole):
            return QtCore.QVariant()
        if self._data[index.row()][index.column()] is None:
            return QtCore.QVariant()
        else:
            #if there's a dedicated precision for that column, print it out with the specified precision.
            #this only works well if you DON'T have other views/widgets that depend on numeric data coming out.
            #i don't like this, but it works for now. unfortunately it seems like Qt doesn't give you a
            #good alternative.
            if self._precisions[index.column()] is not None:
                return QtCore.QVariant("%.*f" % (self._precisions[index.column()], self._data[index.row()][index.column()]))
            else:
                if self._colnames[index.column()] == "icao":
                    return QtCore.QVariant("%06x" % self._data[index.row()][index.column()]) #return as hex string
                else:
                    return QtCore.QVariant(self._data[index.row()][index.column()])

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        self.lock.acquire()
        if not index.isValid():
            return False
        if index.row() >= self.rowCount():
            return False
        if index.column >= self.columnCount():
            return False
        if role != QtCore.Qt.EditRole:
            return False
        self._data[index.row()][index.column()] = value
        self.lock.release()

    #addRecord implements an upsert on self._data; that is,
    #it updates the row if the ICAO exists, or else it creates a new row.
    def addRecord(self, record):
        self.lock.acquire()
        icaos = [x[0] for x in self._data]
        if record["icao"] in icaos:
            row = icaos.index(record["icao"])
            for column in record:
                self._data[row][self._colnames.index(column)] = record[column]
            #create index to existing row and tell the model everything's changed in this row
            #or inside the for loop, use dataChanged on each changed field (might be better)
            self.dataChanged.emit(self.createIndex(row, 0), self.createIndex(row, len(self._colnames)-1))

        #only create records for ICAOs with ADS-B reports
        elif ("latitude" or "speed" or "ident") in record:
            #find new inserted row number
            icaos.append(record["icao"])
            newrowoffset = sorted(icaos).index(record["icao"])
            self.beginInsertRows(QtCore.QModelIndex(), newrowoffset, newrowoffset)
            newrecord = [None for x in xrange(len(self._colnames))]
            for col in xrange(0, len(self._colnames)):
                if self._colnames[col] in record:
                    newrecord[col] = record[self._colnames[col]]
            self._data.append(newrecord)
            self._data = sorted(self._data, key = lambda x: x[0]) #sort by icao
            self.endInsertRows()
        self.lock.release()
        self.prune()

    #weeds out ICAOs older than 1 minute
    def prune(self):
        self.lock.acquire()
        for (index,row) in enumerate(self._data):
            if time.time() - row[1] >= 60:
                self.beginRemoveRows(QtCore.QModelIndex(), index, index)
                self._data.pop(index)
                self.endRemoveRows()
        self.lock.release()
                
class dashboard_output:
    def __init__(self, cprdec, model, pub):
        self.model = model
        self._cpr = cprdec
        pub.subscribe("modes_dl", self.output)
    def output(self, msg):
        try:
            msgtype = msg.data["df"]
            now = time.time()
            newrow = {"rssi": msg.rssi, "seen": now}
            if msgtype in [0, 4, 20]:
                newrow["altitude"] = air_modes.altitude.decode_alt(msg.data["ac"], True)
                newrow["icao"] = msg.ecc
                self.model.addRecord(newrow)
            
            elif msgtype == 17:
                icao = msg.data["aa"]
                newrow["icao"] = icao
                subtype = msg.data["ftc"]
                if subtype == 4:
                    (ident, actype) = air_modes.parseBDS08(msg.data)
                    newrow["ident"] = ident
                    newrow["type"] = actype
                elif 5 <= subtype <= 8:
                    (ground_track, decoded_lat, decoded_lon, rnge, bearing) = air_modes.parseBDS06(msg.data, self._cpr)
                    newrow["heading"] = ground_track
                    newrow["latitude"] = decoded_lat
                    newrow["longitude"] = decoded_lon
                    newrow["altitude"] = 0
                    if rnge is not None:
                        newrow["range"] = rnge
                        newrow["bearing"] = bearing
                elif 9 <= subtype <= 18:
                    (altitude, decoded_lat, decoded_lon, rnge, bearing) = air_modes.parseBDS05(msg.data, self._cpr)
                    newrow["altitude"] = altitude
                    newrow["latitude"] = decoded_lat
                    newrow["longitude"] = decoded_lon
                    if rnge is not None:
                        newrow["range"] = rnge
                        newrow["bearing"] = bearing
                elif subtype == 19:
                    subsubtype = msg.data["sub"]
                    velocity = None
                    heading = None
                    vert_spd = None
                    if subsubtype == 0:
                        (velocity, heading, vert_spd) = air_modes.parseBDS09_0(msg.data)
                    elif 1 <= subsubtype <= 2:
                        (velocity, heading, vert_spd) = air_modes.parseBDS09_1(msg.data)
                    newrow["speed"] = velocity
                    newrow["heading"] = heading
                    newrow["vertical"] = vert_spd
    
                self.model.addRecord(newrow)

        except ADSBError:
            return

