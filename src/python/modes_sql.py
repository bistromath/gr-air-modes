#!/usr/bin/env python
import time, os, sys
from string import split, join
import modes_parse
import sqlite3

class modes_output_sql(modes_parse.modes_parse):
  def __init__(self):
    #create the database
    self.db = sqlite3.connect(':memory:') #RAM-based database, no persistence
    #now execute a schema to create the tables you need
    c = self.db.cursor()
    query = """CREATE TABLE "positions" (
                "icao" INTEGER KEY NOT NULL,
                "seen" TEXT NOT NULL,
                "alt"  INTEGER,
                "lat"  REAL,
                "lon"  REAL
            );"""
    c.execute(query)
    query = """CREATE TABLE "vectors" (
                "icao"     INTEGER KEY NOT NULL,
                "seen"     TEXT NOT NULL,
                "speed"    REAL,
                "heading"  REAL,
                "vertical" REAL
            );"""
    c.execute(query)
    query = """CREATE TABLE "ident" (
                "icao"     INTEGER PRIMARY KEY NOT NULL,
                "ident"    TEXT NOT NULL
            );"""
    c.execute(query)
    c.close()

  def __del__(self):
    self.db.close()

  def insert(self, message):
    query = self.make_insert_query(message)
    if query is not None:
      c = self.db.cursor()
      c.execute(query)
      c.close()
      self.db.commit() #not sure if i have to do this
  
  def make_insert_query(self, message):
    #assembles a SQL query tailored to our database
    #this version ignores anything that isn't Type 17 for now, because we just don't care
    [msgtype, shortdata, longdata, parity, ecc, reference] = message.split()

    shortdata = long(shortdata, 16)
    longdata = long(longdata, 16)
    parity = long(parity, 16)
    ecc = long(ecc, 16)
#   reference = float(reference)

    msgtype = int(msgtype)

    query = None

    if msgtype == 17:
      query = self.sql17(shortdata, longdata, parity, ecc)

    return query

  def sql17(self, shortdata, longdata, parity, ecc):
    icao24 = shortdata & 0xFFFFFF	
    subtype = (longdata >> 51) & 0x1F

    retstr = None

    if subtype == 4:
      msg = self.parseBDS08(shortdata, longdata, parity, ecc)
      retstr = "INSERT OR REPLACE INTO ident (icao, ident) VALUES (" + "%i" % icao24 + ", '" + msg + "')"

    elif subtype >= 5 and subtype <= 8:
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS06(shortdata, longdata, parity, ecc)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "INSERT INTO positions (icao, seen, alt, lat, lon) VALUES (" + "%i" % icao24 + ", datetime('now'), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"

    elif subtype >= 9 and subtype <= 18 and subtype != 15: #i'm eliminating type 15 records because they don't appear to be valid position reports.
      [altitude, decoded_lat, decoded_lon, rnge, bearing] = self.parseBDS05(shortdata, longdata, parity, ecc)
      if decoded_lat is None: #no unambiguously valid position available
        retstr = None
      else:
        retstr = "INSERT INTO positions (icao, seen, alt, lat, lon) VALUES (" + "%i" % icao24 + ", datetime('now'), " + str(altitude) + ", " + "%.6f" % decoded_lat + ", " + "%.6f" % decoded_lon + ")"

    elif subtype == 19:
      subsubtype = (longdata >> 48) & 0x07
      if subsubtype == 0:
        [velocity, heading, vert_spd] = self.parseBDS09_0(shortdata, longdata, parity, ecc)
        retstr = "INSERT INTO vectors (icao, seen, speed, heading, vertical) VALUES (" + "%i" % icao24 + ", datetime('now'), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ")";

      elif subsubtype == 1:
        [velocity, heading, vert_spd] = self.parseBDS09_1(shortdata, longdata, parity, ecc)
        retstr = "INSERT INTO vectors (icao, seen, speed, heading, vertical) VALUES (" + "%i" % icao24 + ", datetime('now'), " + "%.0f" % velocity + ", " + "%.0f" % heading + ", " + "%.0f" % vert_spd + ")";

    return retstr




