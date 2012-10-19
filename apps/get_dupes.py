#!/usr/bin/env python

import sys, re

if __name__== '__main__':
    data = sys.stdin.readlines()
    icaos = []
    num_icaos = 0
    for line in data:
        match = re.match(".*Type.*from (\w+)", line)
        if match is not None:
            icao = int(match.group(1), 16)
            icaos.append(icao)

    #get dupes
    dupes = sorted([icao for icao in set(icaos) if icaos.count(icao) > 1])
    count = sum([icaos.count(icao) for icao in dupes])
    for icao in dupes:
        print "%x" % icao
    print "Found %i replies from %i non-unique aircraft, out of a total %i replies (%i likely spurious replies)." \
            % (count, len(dupes), len(icaos), len(icaos)-count)


