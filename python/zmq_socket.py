# Copyright 2013 Nick Foster
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

#this serves as a bridge between ZMQ subscriber and the GR pubsub callbacks interface
#creates a thread, publishes socket data to pubsub subscribers
#just a convenient way to create an aggregating socket with callbacks on receive
#can use this for inproc:// signalling with minimal overhead
#not sure if it's a good idea to use this yet

import time
import threading
import zmq
from gnuradio.gr.pubsub import pubsub
import queue

class zmq_pubsub_iface(threading.Thread):
    def __init__(self, context, subaddr=None, pubaddr=None):
        threading.Thread.__init__(self)
        #private data
        self._queue = queue.Queue()
        self._subsocket = context.socket(zmq.SUB)
        self._pubsocket = context.socket(zmq.PUB)
        self._subaddr = subaddr
        self._pubaddr = pubaddr
        if type(self._subaddr) is str:
            self._subaddr = [self._subaddr]
        if type(self._pubaddr) is str:
            self._pubaddr = [self._pubaddr]
        self._sub_connected = False
        self._pubsub = pubsub()
        if self._pubaddr is not None:
            for addr in self._pubaddr:
                self._pubsocket.bind(addr.encode('ascii'))

        self._poller = zmq.Poller()
        self._poller.register(self._subsocket, zmq.POLLIN)

        #public data
        self.shutdown = threading.Event()
        self.finished = threading.Event()
        #init
        self.setDaemon(True)
        self.start()

    def subscribe(self, key, subscriber):
        if not self._sub_connected:
            if not self._subaddr:
                raise Exception("No subscriber address set")
            for addr in self._subaddr:
                self._subsocket.connect(addr.encode('ascii'))
            self._sub_connected = True
        self._subsocket.setsockopt(zmq.SUBSCRIBE, key.encode('ascii'))
        self._pubsub.subscribe(key.encode('ascii'), subscriber)

    def unsubscribe(self, key, subscriber):
        self._subsocket.setsockopt(zmq.UNSUBSCRIBE, key.encode('ascii'))
        self._pubsub.unsubscribe(key.encode('ascii'), subscriber)

    #executed from the thread context(s) of the caller(s)
    #so we use a queue to push sending into the run loop
    #since sockets must be used in the thread they were created in
    def __setitem__(self, key, val):
        if not self._pubaddr:
            raise Exception("No publisher address set")
        if not self.shutdown.is_set():
            self._queue.put([key.encode('ascii'), val])

    def __getitem__(self, key):
        return self._pubsub[key.encode('ascii')]

    def run(self):
        done = False
        while not self.shutdown.is_set() and not done:
            if self.shutdown.is_set():
                done = True
            #send
            while True:
                try:
                    msg = self._queue.get(block=False)
                    self._pubsocket.send_multipart(msg)
                except queue.Empty:
                    break
            #receive
            if self._sub_connected:
                socks = [s[0].underlying for s in self._poller.poll(timeout=0) if s[1] == zmq.POLLIN]
                while self._subsocket.underlying in socks:
                    [address, msg] = self._subsocket.recv_multipart()
                    self._pubsub[address] = msg
                    socks = [s[0].underlying for s in self._poller.poll(timeout=0) if s[1] == zmq.POLLIN]
            #snooze
            if not done:
                time.sleep(0.1)

        self._subsocket.close()
        self._pubsocket.close()
        self.finished.set()

    def close(self):
        self.shutdown.set()
        #self._queue.join() #why does this block forever
        self.finished.wait(0.2)

def pr(x):
    print(x)

if __name__ == "__main__":
    #create socket pair
    context = zmq.Context(1)
    sock1 = zmq_pubsub_iface(context, subaddr="inproc://sock2-pub", pubaddr="inproc://sock1-pub")
    sock2 = zmq_pubsub_iface(context, subaddr="inproc://sock1-pub", pubaddr=["inproc://sock2-pub", "tcp://*:5433"])
    sock3 = zmq_pubsub_iface(context, subaddr="tcp://localhost:5433", pubaddr=None)

    sock1.subscribe("data1", pr)
    sock2.subscribe("data2", pr)
    sock3.subscribe("data3", pr)

    for i in range(10):
        sock1["data2"] = "HOWDY"
        sock2["data3"] = "DRAW"
        sock2["data1"] = "PARDNER"
        time.sleep(0.1)

    time.sleep(0.1)

    sock1.close()
    sock2.close()
    sock3.close()
