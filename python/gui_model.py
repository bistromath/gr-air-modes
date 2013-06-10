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

from PyQt4 import QtCore, QtGui, QtSql
import air_modes
import threading, math, time
from air_modes.exceptions import *
from gnuradio.gr.pubsub import pubsub

#fades the ICAOs out as their last report gets older,
#and display ident if available, ICAO otherwise
class ICAOViewDelegate(QtGui.QStyledItemDelegate):
    def paint(self, painter, option, index):
        #draw selection rectangle
        if option.state & QtGui.QStyle.State_Selected:
            painter.setBrush(QtGui.QPalette().highlight())
            painter.drawRect(option.rect)

        #if there's an ident available, use it. otherwise print the ICAO
        if index.model().data(index.model().index(index.row(), 8)) != QtCore.QVariant():
            paintstr = index.model().data(index.model().index(index.row(), 8)).toString()
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

#TODO must add libqt4-sql, libqt4-sql-sqlite, python-qt4-sql to dependencies
class dashboard_sql_model(QtSql.QSqlQueryModel):
    def __init__(self, parent):
        QtSql.QSqlQueryModel.__init__(self, parent)
        self._sql = None
        self._db = QtSql.QSqlDatabase("QSQLITE")
        self._db.setDatabaseName("adsb.db") #TODO specify this elsewhere
        self._db.open()
        #what is this i don't even
        #fetches the combined data of all three tables for all ICAOs seen in the last minute.
        self.setQuery("""select tab1.icao, tab1.seen, tab1.lat, tab1.lon, tab1.alt, speed, heading, vertical, ident, type
                         from (select * from (select * from positions order by seen desc) group by icao) tab1
                    left join (select * from (select * from vectors order by seen desc)   group by icao) tab2
                        on tab1.icao=tab2.icao
                    left join (select * from (select * from ident)) tab3
                        on tab1.icao=tab3.icao
                    where tab1.seen > datetime('now', '-1 minute')""", self._db)

    #the big club
    def update_all(self, icao):
        self.dataChanged.emit(self.createIndex(0, 0), self.createIndex(self.rowCount(), self.columnCount()))
