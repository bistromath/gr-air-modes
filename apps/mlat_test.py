#!/usr/bin/env python

#test stuff for mlat server

import socket, pickle, time, random, sys

class rx_data:
    secs = 0
    frac_secs = 0.0
    data = None

class client_info:
    def __init__(self):
        self.name = ""
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.offset_secs = 0
        self.offset_frac_secs = 0.0

info = client_info()
info.name = sys.argv[1]
info.latitude = float(sys.argv[2])
info.longitude = float(sys.argv[3])
info.altitude = 123
info.offset_secs = 0
info.offset_frac_secs = 0.0

data1 = rx_data()
data1.secs = 0
data1.data = int("0x8da81f875857f10eb65b10cb66f3", 16)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(1)
sock.connect(("localhost", 31337))
sock.send(pickle.dumps(info))
print sock.recv(1024)
while 1:
    time.sleep(0.05)
    data1.frac_secs = random.random()
    sock.send(pickle.dumps([data1]))

sock.close()
sock = None
