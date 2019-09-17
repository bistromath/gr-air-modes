#
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

import time, os, sys, threading
import air_modes
import sqlite3
from air_modes.exceptions import *
from gnuradio.gr.pubsub import pubsub

class output_sql:
  def __init__(self, cpr, filename, lock, publisher):
    #pubsub.__init__(self)
    self._cpr = cpr
    self._lock = lock;
    #create the database
    self.filename = filename
    self._db = sqlite3.connect(filename)
    #now execute a schema to create the tables you need
    c = self._db.cursor()
    query = """CREATE TABLE IF NOT EXISTS "positions" (
              "icao" INTEGER KEY NOT NULL,
              "seen" TEXT NOT NULL,
              "alt"  INTEGER,
              "lat"  REAL,
              "lon"  REAL
          );"""
    c.execute(query)
    query = """CREATE TABLE IF NOT EXISTS "vectors" (
              "icao"     INTEGER KEY NOT NULL,
              "seen"     TEXT NOT NULL,
              "speed"    REAL,
              "heading"  REAL,
              "vertical" REAL
          );"""
    c.execute(query)
    query = """CREATE TABLE IF NOT EXISTS "ident" (
              "icao"     INTEGER PRIMARY KEY NOT NULL,
              "ident"    TEXT NOT NULL,
              "type"     TEXT NOT NULL
          );"""
    c.execute(query)
    c.close()
    self._db.commit()
    #we close the db conn now to reopen it in the output() thread context.
    self._db.close()
    self._db = None
    publisher.subscribe("type17_dl", self.insert)

  def insert(self, message):
    with self._lock:
      try:
        #we're checking to see if the db is empty, and creating the db object
        #if it is. the reason for this is so that the db writing is done within
        #the thread context of output(), rather than the thread context of the
        #constructor.
        if self._db is None:
          self._db = sqlite3.connect(self.filename)

        query = self.make_insert_query(message)
        if query is not None:
            c = self._db.cursor()
            c.execute(query)
            c.close()
            self._db.commit()

      except ADSBError:
        pass

  def make_insert_query(self, msg):
    #assembles a SQL query tailored to our database
    #this version ignores anything that isn't Type 17 for now, because we just don't care
    query = None
    msgtype = msg.data["df"]
    if msgtype == 17:
      query = self.sql17(msg.data)
      #self["new_adsb"] = data["aa"] #publish change notification

    return query

#TODO: if there's a way to publish selective reports on upsert to distinguish,
#for instance, between a new ICAO that's just been heard, and a refresh of an
#existing ICAO, both of those would be useful publishers for the GUI model.
#otherwise, worst-case you can just refresh everything every time a report
#comes in, but it's going to use more CPU. Not likely a problem if you're only
#looking at ADS-B (no mode S) data.
#It's probably time to look back at the Qt SQL table model and see if it can be
#bent into shape for you.
  def sql17(self, data):
    icao24 = data["aa"]
    bdsreg = data["me"].get_type()
    #self["bds%.2i" % bdsreg] = icao24 #publish under "bds08", "bds06", etc.

    if bdsreg == 0x08:
      (msg, typename) = air_modes.parseBDS08(data)
      return "INSERT OR REPLACE INTO ident (icao, ident, type) VALUES (" + "%i" % icao24 + ", '" + msg + "', '" + typename + "')"
    elif bdsreg == 0x06:
      [ground_track, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS06(data, self._cpr)
      altitude = 0
      if decoded_lat is None: #no unambiguously valid position available
        raise CPRNoPositionError
      else:
        return "INSERT INTO positions (icao, seen, alt, lat, lon) VALUES (" + "%i" % icao24 + ", datetime('now'), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"
    elif bdsreg == 0x05:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS05(data, self._cpr)
      if decoded_lat is None: #no unambiguously valid position available
        raise CPRNoPositionError
      else:
        return "INSERT INTO positions (icao, seen, alt, lat, lon) VALUES (" + "%i" % icao24 + ", datetime('now'), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"
    elif bdsreg == 0x09:
      subtype = data["bds09"].get_type()
      if subtype == 0:
        [velocity, heading, vert_spd, turnrate] = air_modes.parseBDS09_0(data)
        return "INSERT INTO vectors (icao, seen, speed, heading, vertical) VALUES (" + "%i" % icao24 + ", datetime('now'), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ")"
      elif subtype == 1:
        [velocity, heading, vert_spd] = air_modes.parseBDS09_1(data)
        return "INSERT INTO vectors (icao, seen, speed, heading, vertical) VALUES (" + "%i" % icao24 + ", datetime('now'), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ")"
      else:
        raise NoHandlerError
