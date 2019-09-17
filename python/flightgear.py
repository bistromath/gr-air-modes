#!/usr/bin/env python

#flightgear interface to uhd_modes.py
#outputs UDP data to add traffic to FGFS

import struct
import socket
import air_modes
from air_modes import mlat
import sqlite3
import string, threading, math, time
from air_modes.sql import output_sql
from Quaternion import Quat
import numpy
from air_modes.exceptions import *

class output_flightgear:
    def __init__(self, cprdec, hostname, port, pub):
        self.hostname = hostname
        self.port = port
        self.positions = {}
        self.velocities = {}
        self.callsigns = {}
        self._cpr = cprdec

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#        self.sock.connect((self.hostname, self.port))
        pub.subscribe("type17_dl", self.output)

    def output(self, msg):
        try:
            msgtype = msg.data["df"]
            if msgtype == 17: #ADS-B report
                icao24 = msg.data["aa"]
                bdsreg = msg.data["me"].get_type()
                if bdsreg == 0x08: #ident packet
                    (ident, actype) = air_modes.parseBDS08(msg.data)
                    #select model based on actype
                    self.callsigns[icao24] = [ident, actype]

                elif bdsreg == 0x06: #BDS0,6 pos
                    [ground_track, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS06(msg.data, self._cpr)
                    self.positions[icao24] = [decoded_lat, decoded_lon, 0]
                    self.update(icao24)

                elif bdsreg == 0x05: #BDS0,5 pos
                    [altitude, decoded_lat, decoded_lon, rnge, bearing] = air_modes.parseBDS05(msg.data, self._cpr)
                    self.positions[icao24] = [decoded_lat, decoded_lon, altitude]
                    self.update(icao24)

                elif bdsreg == 0x09: #velocity
                    subtype = msg.data["bds09"].get_type()
                    if subtype == 0:
                      [velocity, heading, vert_spd, turnrate] = air_modes.parseBDS09_0(msg.data)
                    elif subtype == 1:
                      [velocity, heading, vert_spd] = air_modes.parseBDS09_1(msg.data)
                      turnrate = 0
                    else:
                        return

                    self.velocities[icao24] = [velocity, heading, vert_spd, turnrate]

        except ADSBError:
            pass

    def update(self, icao24):
        #check to see that ICAO24 appears in all three records and that the data looks valid
        complete = (icao24 in self.positions)\
               and (icao24 in self.velocities)\
               and (icao24 in self.callsigns)
        if complete:
            print("FG update: %s" % (self.callsigns[icao24][0]))
            msg = fg_posmsg(self.callsigns[icao24][0],
                            self.callsigns[icao24][1],
                            self.positions[icao24][0],
                            self.positions[icao24][1],
                            self.positions[icao24][2],
                            self.velocities[icao24][1],
                            self.velocities[icao24][0],
                            self.velocities[icao24][2],
                            self.velocities[icao24][3]).pack()

            self.sock.sendto(msg, (self.hostname, self.port))

class fg_header:
    def __init__(self):
        self.magic = "FGFS"
        self.proto = 0x00010001
        self.msgid = 0
        self.msglen = 0 #in bytes, though they swear it isn't
        self.replyaddr = 0 #unused
        self.replyport = 0 #unused
        self.callsign = "UNKNOWN"
        self.data = None

    hdrfmt = '!4sLLLLL8s0L'

    def pack(self):
        self.msglen = 32 + len(self.data)
        packed = struct.pack(self.hdrfmt, self.magic, self.proto, self.msgid, self.msglen, self.replyaddr, self.replyport, self.callsign)
        return packed

#so this appears to work, but FGFS doesn't display it in flight for some reason. not in the chat window either. oh well.
class fg_chatmsg(fg_header):
    def __init__(self, msg):
        fg_header.__init__(self)
        self.chatmsg = msg
        self.msgid = 1

    def pack(self):
        self.chatfmt = '!' + str(len(self.chatmsg)) + 's'
        #print "Packing with strlen %i " % len(self.chatmsg)
        self.data = struct.pack(self.chatfmt, self.chatmsg)
        return fg_header.pack(self) + self.data

modelmap = { None:                       'Aircraft/777-200/Models/777-200ER.xml',
            "NO INFO":                   'Aircraft/777-200/Models/777-200ER.xml',
            "LIGHT":                     'Aircraft/c172p/Models/c172p.xml',
            "SMALL":                     'Aircraft/CitationX/Models/Citation-X.xml',
            "LARGE":                     'Aircraft/CRJ700-family/Models/CRJ700.xml',
            "LARGE HIGH VORTEX":         'Aircraft/757-200/Models/757-200.xml',
            "HEAVY":                     'Aircraft/IDG-A32X/Models/A320neo-CFM.xml',
            "HIGH PERFORMANCE":          'Aircraft/SR71-BlackBird/Models/Blackbird-SR71B.xml', #yeah i know
            "ROTORCRAFT":                'Aircraft/ec130/Models/ec130b4.xml',
            "GLIDER":                    'Aircraft/ASK21-MI/Models/ask21mi.xml',
            "BALLOON/BLIMP":             'Aircraft/ZLT-NT/Models/ZLT-NT.xml',
            "ULTRALIGHT":                'Aircraft/cri-cri/Models/MC-15.xml',
            "UAV":                       'Aircraft/YardStik/Models/yardstik.xml', #hahahaha
            "SPACECRAFT":                'Aircraft/SpaceShip-One/Models/spaceshipone.xml',
            "SURFACE EMERGENCY VEHICLE": 'Aircraft/followme/Models/follow_me.xml', #not the best
            "SURFACE SERVICE VEHICLE":   'Aircraft/pushback/Models/Pushback.xml'
}

class fg_posmsg(fg_header):
    def __init__(self, callsign, modelname, lat, lon, alt, hdg, vel, vs, turnrate):
        #from the above, calculate valid FGFS mp vals
        #this is the translation layer between ADS-B and FGFS
        fg_header.__init__(self)
        self.callsign = callsign
        if self.callsign is None:
            self.callsign = "UNKNOWN"
        self.modelname = modelname
        if self.modelname not in modelmap:
            #this should keep people on their toes when strange aircraft types are seen
            self.model = 'Aircraft/santa/Models/santa.xml'
        else:
            self.model = modelmap[self.modelname]
            
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.hdg = hdg
        self.vel = vel
        self.vs = vs
        self.turnrate = turnrate
        self.msgid = 7
        self.time = time.time()
        self.lag = 0

    def pack(self):
        #this is, in order:
        #model, time (time.time() is fine), lag, position, orientation, linear vel, angular vel, linear accel, angular accel (accels unused), 0
        #position is in ECEF format -- same as mlat uses. what luck!
        pos = mlat.llh2ecef([self.lat, self.lon, self.alt * 0.3048]) #alt is in meters!

        #get the rotation quaternion to rotate to local reference frame from lat/lon
        rotquat = Quat([self.lat, self.lon])
        #get the quaternion corresponding to aircraft orientation
        acquat = Quat([self.hdg, 0, 0])
        #rotate aircraft into ECEF frame
        ecefquat = rotquat * acquat
        #get it in angle/axis representation
        (angle, axis) = ecefquat._get_angle_axis()
        orientation = angle * axis
        
        kts_to_ms = 0.514444444 #convert kts to m/s
        vel_ms = self.vel * kts_to_ms
        velvec = (vel_ms,0,0) #velocity vector in m/s -- is this in the local frame? looks like [0] is fwd vel,
                                   #we'll pretend the a/c is always moving the dir it's pointing
        turnvec = (0,0,self.turnrate * (math.pi / 180.) ) #turn rates in rad/s [roll, pitch, yaw]
        accelvec = (0,0,0)
        turnaccelvec = (0,0,0)
        self.posfmt = '!96s' + 'd' + 'd' + '3d' + '3f' + '3f' + '3f' + '3f' + '3f' + 'I'
        self.data = struct.pack(self.posfmt,
                                self.model,
                                self.time,
                                self.lag,
                                pos[0], pos[1], pos[2],
                                orientation[0], orientation[1], orientation[2],
                                velvec[0], velvec[1], velvec[2],
                                turnvec[0], turnvec[1], turnvec[2],
                                accelvec[0], accelvec[1], accelvec[2],
                                turnaccelvec[0], turnaccelvec[1], turnaccelvec[2],
                                0)

        return fg_header.pack(self) + self.data
        

if __name__ == '__main__':
    timeoffset = time.time()
    iof = open('27augrudi3.txt')
    localpos = [37.409066,-122.077836]
    hostname = "localhost"
    port = 5000
    fgout = output_flightgear(localpos, hostname, port)

    for line in iof:
        timetosend = float(line.split()[6])
        while (time.time() - timeoffset) < timetosend:
            time.sleep(0.02)
        fgout.output(line)
