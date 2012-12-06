#!/usr/bin/env python

#test stuff for mlat server

import socket, pickle, time, random, sys, math, numpy
import air_modes

class rx_data:
    secs = 0
    frac_secs = 0.0
    data = None

class client_info:
    def __init__(self):
        self.name = ""
        self.position = []
        self.offset_secs = 0
        self.offset_frac_secs = 0.0

info = client_info()
info.name = sys.argv[1]
info.position = [float(sys.argv[2]), float(sys.argv[3]), 100]
info.offset_secs = 0
info.offset_frac_secs = 0.0

data1 = rx_data()
data1.secs = 0
data1.data = int("0x8da81f875857f10eb65b10cb66f3", 16)

ac_starting_pos = [37.617175, -122.400843, 8000]
ac_hdg = 130.
ac_spd = 0.00008
def get_pos(time):
    return [ac_starting_pos[0] + ac_spd * time * math.cos(ac_hdg*math.pi/180.), \
            ac_starting_pos[1] + ac_spd * time * math.sin(ac_hdg*math.pi/180.), \
            ac_starting_pos[2]]

def get_simulated_timestamp(time, position):
    return time + numpy.linalg.norm(numpy.array(air_modes.mlat.llh2ecef(position))-numpy.array(air_modes.mlat.llh2geoid(info.position))) / air_modes.mlat.c

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(1)
sock.connect(("localhost", 31337))
sock.send(pickle.dumps(info))
print sock.recv(1024)
ts = 0.0
while 1:
    pos = get_pos(ts)
    stamp = get_simulated_timestamp(ts, pos)
    print "Timestamp: %.10f" % (stamp)
    print "Position: ", pos
    data1.secs = int(stamp)
    data1.frac_secs = float(stamp)
    data1.frac_secs -= int(data1.frac_secs)
    sock.send(pickle.dumps([data1]))
    ts+=1
    time.sleep(1)

sock.close()
sock = None
