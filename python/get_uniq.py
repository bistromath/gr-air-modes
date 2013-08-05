#!/usr/bin/env python

import sys, re

if __name__== '__main__':
    data = sys.stdin.readlines()
    icaos = []
    num_icaos = 0
    for line in data:
        match = re.match(".*from (\w+)", line)
        if match is not None:
            icao = int(match.group(1), 16)
            icaos.append(icao)

    #get dupes
    dupes = sorted([icao for icao in set(icaos) if icaos.count(icao) > 1])
    for icao in dupes:        
        print "%x" % icao
    print "Found non-unique replies from %i aircraft" % len(dupes)


