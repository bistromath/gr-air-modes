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

import time, os, sys, math
from string import split, join
import modes_parse
import sqlite3
from modes_exceptions import *

class modes_output_sql(modes_parse.modes_parse):
  def __init__(self, mypos, filename):
    modes_parse.modes_parse.__init__(self, mypos)
    #create the database
    self.filename = filename
    self.db = sqlite3.connect(filename)
    #now execute a schema to create the tables you need
    c = self.db.cursor()
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
                "ident"    TEXT NOT NULL
            );"""
    c.execute(query)
    query = """CREATE TABLE IF NOT EXISTS "aircraft" (
                "icao" integer primary key not null,
                "seen" text not null,
                "rssi" real,
                "latitude" real,
                "longitude" real,
                "altitude" real,
                "speed" real,
                "heading" real,
                "vertical" real,
                "ident" text,
                "type" text
            );"""
    c.execute(query)
    c.close()
    #we close the db conn now to reopen it in the output() thread context.
    self.db.close()
    self.db = None

  def __del__(self):
    self.db = None

  def output(self, message):
    try:
      #we're checking to see if the db is empty, and creating the db object
      #if it is. the reason for this is so that the db writing is done within
      #the thread context of output(), rather than the thread context of the
      #constructor. that way you can spawn a thread to do output().
      if self.db is None:
        self.db = sqlite3.connect(self.filename)
          
      self.make_insert_query(message)
      self.db.commit() #don't know if this is necessary
    except ADSBError:
      pass

  def make_insert_query(self, message):
    #assembles a SQL query tailored to our database
    #this version ignores anything that isn't Type 17 for now, because we just don't care
    [data, ecc, reference, timestamp] = message.split()

    data = modes_parse.modes_reply(long(data, 16))
    ecc = long(ecc, 16)
    rssi = 10.0*math.log10(float(reference))


    query = None
    msgtype = data["df"]
    if msgtype == 17:
      query = self.sql17(data, rssi)

    return query

  def sql17(self, data, rssi):
    icao24 = data["aa"]
    subtype = data["ftc"]
    c = self.db.cursor()

    if subtype == 4:
      (ident, typename) = self.parseBDS08(data)
      c.execute("insert or ignore into aircraft (icao, seen, rssi, ident, type) values (%i, datetime('now'), %f, '%s', '%s')" % (icao24, rssi, ident, typename))
      c.execute("update aircraft set seen=datetime('now'), rssi=%f, ident='%s', type='%s' where icao=%i" % (rssi, ident, typename, icao24))

    elif subtype >= 5 and subtype <= 8:
      [ground_track, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(data)
      altitude = 0
      if decoded_lat is None: #no unambiguously valid position available
        c.execute("insert or ignore into aircraft (icao, seen, rssi) values (%i, datetime('now'), %f)" % (icao24, rssi))
        c.execute("update aircraft set seen=datetime('now'), rssi=%f where icao=%i" % (icao24, rssi))
      else:
        c.execute("insert or ignore into aircraft (icao, seen, rssi, latitude, longitude, altitude) \
                   values (%i, datetime('now'), %f, %.6f, %.6f, %i)" % (icao24, rssi, decoded_lat, decoded_lon, altitude))
        c.execute("update aircraft set seen=datetime('now'), rssi=%f, latitude=%.6f, longitude=%.6f, altitude=%i" % (rssi, decoded_lat, decoded_lon, altitude))

    elif subtype >= 9 and subtype <= 18 and subtype != 15: #i'm eliminating type 15 records because they don't appear to be valid position reports.
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(data)
      if decoded_lat is None: #no unambiguously valid position available
        c.execute("insert or ignore into aircraft (icao, seen, rssi) values (%i, datetime('now'), %f);" % (icao24, rssi))
        c.execute("update aircraft set seen=datetime('now'), rssi=%f where icao=%i" % (icao24, rssi))
      else:
        c.execute("insert or ignore into aircraft (icao, seen, rssi, latitude, longitude, altitude)  \
                   values (%i, datetime('now'), %f, %.6f, %.6f, %i)" % (icao24, rssi, decoded_lat, decoded_lon, altitude))
        c.execute("update aircraft set seen=datetime('now'), rssi=%f, latitude=%.6f, longitude=%.6f, altitude=%i where icao=%i" % (rssi, decoded_lat, decoded_lon, altitude, icao24))

    elif subtype == 19:
      subsubtype = data["sub"]
      if subsubtype == 0:
        [velocity, heading, vert_spd] = self.parseBDS09_0(data)

      elif 1 <= subsubtype <= 2:
        [velocity, heading, vert_spd] = self.parseBDS09_1(data)
      else:
        return None
      
      c.execute("insert or ignore into aircraft (icao, seen, rssi, speed, heading, vertical) \
                 values (%i, datetime('now'), %f, %.0f, %.0f, %.0f);" % (icao24, rssi, velocity, heading, vert_spd))
      c.execute("update aircraft set seen=datetime('now'), rssi=%f, speed=%.0f, heading=%.0f, vertical=%.0f where icao=%i" % (rssi, velocity, heading, vert_spd, icao24))


    c.close()
