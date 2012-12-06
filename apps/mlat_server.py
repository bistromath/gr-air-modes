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

import time, os, sys, socket, struct
from string import split, join
from datetime import *
import air_modes
import pickle
import time
import bisect

#simple multilateration server app.
#accepts connections from clients (need a raw_client output thing)
#looks at received messages and then attempts to multilaterate positions
#will not attempt clock synchronization yet; it's up to clients to present
#accurate timestamps. later on we can do clock sync based on ADS-B packets.


#how to store records for quick retrieval?
#the data is really a hash; we use it to find correlated records.
#self._records should be a dict of replies
#so: { <adsbdata>: [{ "addr": "192.168.10.1", "secs": 11, "frac_secs": 0.123456 }, {....}...] ... }
#adsbdata should be an int.

#change this to 0 for ASCII format for debugging. use HIGHEST_PROTOCOL
#for actual use to keep the pickle size down.
#pickle_prot = 0
pickle_prot = pickle.HIGHEST_PROTOCOL

class rx_data:
    def __init__(self):
        self.secs = 0
        self.frac_secs = 0.0
        self.data = None

class stamp:
    def __init__(self, clientinfo, secs, frac_secs):
        self.clientinfo = clientinfo
        self.secs = secs
        self.frac_secs = frac_secs
    def __lt__(self, other):
        if self.secs == other.secs:
            return self.frac_secs < other.frac_secs
        else:
            return self.secs < other.secs
    def __gt__(self, other):
        if self.secs == other.secs:
            return self.frac_secs > other.frac_secs
        else:
            return self.secs > other.secs
    def __eq__(self, other):
        return self.secs == other.secs and self.frac_secs == other.frac_secs
    def __ne__(self, other):
        return self.secs != other.secs or self.frac_secs != other.frac_secs
    #good to within ms for comparison
    def tofloat(self):
        return self.secs + self.frac_secs

def ordered_insert(a, item):
    a.insert(bisect.bisect_right(a, item), item)

class client_info:
    def __init__(self):
        self.name = ""
        self.position = []
        self.offset_secs = 0
        self.offset_frac_secs = 0.0

class connection:
    def __init__(self, addr, sock, clientinfo):
        self.addr = addr
        self.sock = sock
        self.clientinfo = clientinfo
    
class mlat_server:
    def __init__(self, mypos, port):
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._s.bind(('', port))
        self._s.listen(1)
        self._s.setblocking(0) #nonblocking
        self._conns = [] #list of active connections
        self._reports = {} #hashed by data
        self._lastreport = 0 #used for pruning

        self._parser = air_modes.parse(None)

    def __del__(self):
        self._s.close()

    def get_messages(self):
        for conn in self._conns:
            pkt = None
            try:
                pkt = conn.sock.recv(1024)
            except socket.error:
                self._conns.remove(conn)
            if not pkt: break
            try:
                msglist = pickle.loads(pkt)
                for msg in msglist:
                    st = stamp(conn.clientinfo, msg.secs, msg.frac_secs)
                    if msg.data not in self._reports:
                        self._reports[msg.data] = []

                    #ordered insert
                    ordered_insert(self._reports[msg.data], st)
                    if st.tofloat() > self._lastreport:
                        self._lastreport = st.tofloat()

            except Exception as e:
                print "Invalid message from %s: %s" % (conn.addr, pkt)
                print e

        #self.prune()

    #prune should delete all reports in self._reports older than 5s.
    #not really tested well
    def prune(self):
        for data, stamps in self._reports.iteritems():
            #check the last stamp first so we don't iterate over
            #the whole list if we don't have to
            if self._lastreport - stamps[-1].tofloat() > 5:
                del self._reports[data]
            else:
                for i,st in enumerate(stamps):
                    if self._lastreport - st.tofloat() > 5:
                        del self._reports[data][i]
                if len(self._reports[data]) == 0:
                    del self._reports[data]

    #return a list of eligible messages for multilateration
    #eligible reports are:
    #1. bit-identical
    #2. from distinct stations (at least 3)
    #3. within 0.003 seconds of each other
    #traverse the reports for each data pkt (hash) looking for >3 reports
    #within 0.003s, then check for unique IPs (this should pass 99% of the time)
    #let's break a record for most nested loops. this one goes four deep.
    #it's loop-ception!
    def get_eligible_reports(self):
        groups = []
        for data,stamps in self._reports.iteritems():
            if len(stamps) > 2: #quick check before we do a set()
                stations = set([st.clientinfo for st in stamps])
                if len(stations) > 2:
                    i=0
                    #it's O(n) since the list is already sorted
                    #can probably be cleaner and more concise
                    while(i < len(stamps)):
                        refstamp = stamps[i].tofloat()
                        reps = []
                        while (i<len(stamps)) and (stamps[i].tofloat() < (refstamp + 0.003)):
                            reps.append(stamps[i])
                            i+=1
                        deduped = []
                        for cinfo in stations:
                            for st in reps[::-1]:
                                if st.clientinfo == cinfo:
                                    deduped.append(st)
                                    break
                        if len(deduped) > 2:
                            groups.append({"data": data, "stamps": deduped})

        if len(groups) > 0:
            return groups
        return None

    #issue multilaterated positions
    def output(self, msg):
        #do something here to compose a message
            if msg is not None:
                try:
                    for conn in self._conns[:]: #iterate over a copy of the list
                        conn.sock.send(msg)
                except socket.error:
                    print "Client %s disconnected" % conn.clientinfo.name
                    self._conns.remove(conn)
                    print "Connections: ", len(self._conns)

    #add a new connection to the list
    def add_pending_conns(self):
        try:
            conn, addr = self._s.accept()
            conn.send("HELO\n") #yeah it's like that
            msg = conn.recv(1024)
            if not msg:
                return
            try:
                clientinfo = pickle.loads(msg)
            except:
                print "Invalid pickle received from client"
                return
    
            if clientinfo.__class__.__name__ != "client_info":
                print "Invalid datatype received from client"
                return

            conn.send("OK")
            self._conns.append(connection(addr[0], conn, clientinfo))
            print "New connection from %s: %s" % (addr[0], clientinfo.name)
        except socket.error:
            pass
            
#retrieve altitude from a mode S packet or None if not available
#returns alt in meters
def get_modes_altitude(data):
    df = data["df"] #reply type
    f2m = 0.3048
    if df == 0 or df == 4:
        return air_modes.altitude.decode_alt(data["ac"], True)
    elif df == 17:
        bds = data["me"].get_type()
        if bds == 0x05:
            #return f2m*air_modes.altitude.decode_alt(data["me"]["alt"], False)
            return 8000
    else:
        return None

if __name__=="__main__":
    srv = mlat_server("nothin'", 31337)
    while 1:
        srv.output("Buttes")
        srv.get_messages()
        srv.add_pending_conns()
        reps = srv.get_eligible_reports()
        if reps:
            for rep in reps:
                print "Report with data %x" % rep["data"]
                for st in rep["stamps"]:
                    print "Stamp from %s: %f" % (st.clientinfo.name, st.tofloat())
        srv.prune()

        #now format the reports to get them ready for multilateration
        #it's expecting a list of tuples [(station[], timestamp)...]
        #also have to parse the data to pull altitude out of the mix
        if reps:
            for rep in reps:
                alt = get_modes_altitude(air_modes.modes_reply(rep["data"]))
                if (alt is None and len(rep["stamps"]) > 3) or alt is not None:
                    mlat_list = [(st.clientinfo.position, st.tofloat()) for st in rep["stamps"]]
                    print mlat_list
                    #multilaterate!
                    try:
                        pos = air_modes.mlat.mlat(mlat_list, alt)
                        if pos is not None:
                            print pos
                    except Exception as e:
                        print e
            
        time.sleep(0.3)
