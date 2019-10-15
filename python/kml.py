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

import sqlite3
import math, threading, time

class output_kml(threading.Thread):
    def __init__(self, filename, dbname, localpos, lock, timeout=5):
        threading.Thread.__init__(self)
        self._dbname = dbname
        self._filename = filename
        self.my_coords = localpos
        self._timeout = timeout
        self._lock = lock

        self.shutdown = threading.Event()
        self.finished = threading.Event()
        self.setDaemon(1)
        self.start()

    def run(self):
        self._db = sqlite3.connect(self._dbname) #read from the db
        while self.shutdown.is_set() is False:
            time.sleep(self._timeout)
            self.writekml()

        self._db.close()
        self._db = None
        self.finished.set()

    def close(self):
        self.shutdown.set()
        self.finished.wait(0.2)
        #there's a bug here where self._timeout is long and close() has
        #to wait for the sleep to expire before closing. we just bail
        #instead with the 0.2 param above.


    def writekml(self):
        kmlstr = self.genkml()
        if kmlstr is not None:
            f = open(self._filename, 'w')
            f.write(kmlstr)
            f.close()

    def locked_execute(self, c, query):
        with self._lock:
            c.execute(query)

    def draw_circle(self, center, rng):
        retstr = ""
        steps=30
        #so we're going to do this by computing a bearing angle based on the steps, and then compute the coordinate of a line extended from the center point to that range.
        [center_lat, center_lon] = center
        esquared = (1/298.257223563)*(2-(1/298.257223563))
        earth_radius_mi = 3963.19059

        #here we figure out the circumference of the latitude ring
        #which tells us how wide one line of longitude is at our latitude
        lat_circ = earth_radius_mi * math.cos(center_lat)
        #the circumference of the longitude ring will be equal to the circumference of the earth

        lat_rad = math.radians(center_lat)
        lon_rad = math.radians(center_lon)

        tmp0 = rng / earth_radius_mi

        for i in range(0, steps+1):
            bearing = i*(2*math.pi/steps) #in radians
            lat_out = math.degrees(math.asin(math.sin(lat_rad)*math.cos(tmp0) + math.cos(lat_rad)*math.sin(tmp0)*math.cos(bearing)))
            lon_out = center_lon + math.degrees(math.atan2(math.sin(bearing)*math.sin(tmp0)*math.cos(lat_rad), math.cos(tmp0)-math.sin(lat_rad)*math.sin(math.radians(lat_out))))
            retstr += " %.8f,%.8f, 0" % (lon_out, lat_out,)

        retstr = retstr.lstrip()
        return retstr

    def genkml(self):
        #first let's draw the static content
        retstr="""<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n\t<Style id="airplane">\n\t\t<IconStyle>\n\t\t\t<Icon><href>airports.png</href></Icon>\n\t\t</IconStyle>\n\t</Style>\n\t<Style id="rangering">\n\t<LineStyle>\n\t\t<color>9f4f4faf</color>\n\t\t<width>2</width>\n\t</LineStyle>\n\t</Style>\n\t<Style id="track">\n\t<LineStyle>\n\t\t<color>5fff8f8f</color>\n\t\t<width>4</width>\n\t</LineStyle>\n\t</Style>"""

        if self.my_coords is not None:
            retstr += """\n\t<Folder>\n\t\t<name>Range rings</name>\n\t\t<open>0</open>"""
            for rng in [100, 200, 300]:     
                retstr += """\n\t\t<Placemark>\n\t\t\t<name>%inm</name>\n\t\t\t<styleUrl>#rangering</styleUrl>\n\t\t\t<LinearRing>\n\t\t\t\t<coordinates>%s</coordinates>\n\t\t\t</LinearRing>\n\t\t</Placemark>""" % (rng, self.draw_circle(self.my_coords, rng),)
            retstr += """\t</Folder>\n"""

        retstr +=  """\t<Folder>\n\t\t<name>Aircraft locations</name>\n\t\t<open>0</open>"""

        #read the database and add KML
        q = "select distinct icao from positions where seen > datetime('now', '-5 minute')"
        c = self._db.cursor()
        self.locked_execute(c, q)
        icaolist = c.fetchall()
        #now we have a list icaolist of all ICAOs seen in the last 5 minutes

        for icao in icaolist:
            #print "ICAO: %x" % icao
            q = "select * from positions where icao=%i and seen > datetime('now', '-2 hour') ORDER BY seen DESC" % icao
            self.locked_execute(c, q)
            track = c.fetchall()
            #print "Track length: %i" % len(track)
            if len(track) != 0:
                lat = track[0][3]
                if lat is None: lat = 0
                lon = track[0][4]
                if lon is None: lon = 0
                alt = track[0][2]
                if alt is None: alt = 0

                metric_alt = alt * 0.3048 #google earth takes meters, the commie bastards

                trackstr = ""

                for pos in track:
                    trackstr += " %f,%f,%f" % (pos[4], pos[3], pos[2]*0.3048)

                trackstr = trackstr.lstrip()
            else:
                alt = 0
                metric_alt = 0
                lat = 0
                lon = 0
                trackstr = str("")

            #now get metadata
            q = "select ident from ident where icao=%i" % icao
            self.locked_execute(c, q)
            r = c.fetchall()
            if len(r) != 0:
                ident = r[0][0]
            else: ident=""
            #if ident is None: ident = ""
            #get most recent speed/heading/vertical
            q = "select seen, speed, heading, vertical from vectors where icao=%i order by seen desc limit 1" % icao
            self.locked_execute(c, q)
            r = c.fetchall()
            if len(r) != 0:
                seen = r[0][0]
                speed = r[0][1]
                heading = r[0][2]
                vertical = r[0][3]

            else:
                seen = 0
                speed = 0
                heading = 0
                vertical = 0
            #now generate some KML
            retstr+= "\n\t\t<Placemark>\n\t\t\t<name>%s</name>\n\t\t\t<Style><IconStyle><heading>%i</heading></IconStyle></Style>\n\t\t\t<styleUrl>#airplane</styleUrl>\n\t\t\t<description>\n\t\t\t\t<![CDATA[Altitude: %s<br/>Heading: %i<br/>Speed: %i<br/>Vertical speed: %i<br/>ICAO: %x<br/>Last seen: %s]]>\n\t\t\t</description>\n\t\t\t<Point>\n\t\t\t\t<altitudeMode>absolute</altitudeMode>\n\t\t\t\t<extrude>1</extrude>\n\t\t\t\t<coordinates>%s,%s,%i</coordinates>\n\t\t\t</Point>\n\t\t</Placemark>" % (ident, heading, alt, heading, speed, vertical, icao[0], seen, lon, lat, metric_alt, )

            retstr+= "\n\t\t<Placemark>\n\t\t\t<styleUrl>#track</styleUrl>\n\t\t\t<LineString>\n\t\t\t\t<extrude>0</extrude>\n\t\t\t\t<altitudeMode>absolute</altitudeMode>\n\t\t\t\t<coordinates>%s</coordinates>\n\t\t\t</LineString>\n\t\t</Placemark>" % (trackstr,)

        retstr+= '\n\t</Folder>\n</Document>\n</kml>'
        return retstr

#we just inherit from output_kml because we're doing the same thing, only in a different format.
class output_jsonp(output_kml):
    def set_highlight(self, icao):
        self.highlight = icao

    def genkml(self):
        retstr="""jsonp_callback(["""

#        if self.my_coords is not None:
#            retstr += """\n\t<Folder>\n\t\t<name>Range rings</name>\n\t\t<open>0</open>"""
#            for rng in [100, 200, 300]:
#                retstr += """\n\t\t<Placemark>\n\t\t\t<name>%inm</name>\n\t\t\t<styleUrl>#rangering</styleUrl>\n\t\t\t<LinearRing>\n\t\t\t\t<coordinates>%s</coordinates>\n\t\t\t</LinearRing>\n\t\t</Placemark>""" % (rng, self.draw_circle(self.my_coords, rng),)
#            retstr += """\t</Folder>\n"""

#        retstr +=  """\t<Folder>\n\t\t<name>Aircraft locations</name>\n\t\t<open>0</open>"""

        #read the database and add KML
        q = "select distinct icao from positions where seen > datetime('now', '-1 minute')"
        c = self._db.cursor()
        self.locked_execute(c, q)
        icaolist = c.fetchall()
        #now we have a list icaolist of all ICAOs seen in the last 5 minutes

        for icao in icaolist:
            icao = icao[0]

            #now get metadata
            q = "select ident, type from ident where icao=%i" % icao
            self.locked_execute(c, q)
            r = c.fetchall()
            if len(r) != 0:
                ident = r[0][0]
                actype = r[0][1]
            else: 
                ident=""
                actype = ""
            if ident is None: ident = ""
            #get most recent speed/heading/vertical
            q = "select seen, speed, heading, vertical from vectors where icao=%i order by seen desc limit 1" % icao
            self.locked_execute(c, q)
            r = c.fetchall()
            if len(r) != 0:
                seen = r[0][0]
                speed = r[0][1]
                heading = r[0][2]
                vertical = r[0][3]

            else:
                seen = 0
                speed = 0
                heading = 0
                vertical = 0

            q = "select lat, lon, alt from positions where icao=%i order by seen desc limit 1" % icao
            self.locked_execute(c, q)
            r = c.fetchall()
            if len(r) != 0:
                lat = r[0][0]
                lon = r[0][1]
                alt = r[0][2]
            else:
                lat = 0
                lon = 0
                alt = 0

            highlight = 0
            if hasattr(self, 'highlight'):
                if self.highlight == icao:
                    highlight = 1

            #now generate some JSONP
            retstr+= """{"icao": "%.6x", "lat": %f, "lon": %f, "alt": %i, "hdg": %i, "speed": %i, "vertical": %i, "ident": "%s", "type": "%s", "highlight": %i},""" % (icao, lat, lon, alt, heading, speed, vertical, ident, actype, highlight)

        retstr+= """]);"""
        return retstr
