#!/usr/bin/env python
from modes_parse import modes_parse
import mlat
import numpy

sffile = open("27augsf3.txt")
rudifile = open("27augrudi3.txt")

#sfoutfile = open("sfout.txt", "w")
#rudioutfile = open("rudiout.txt", "w")

sfparse = modes_parse([37.762236,-122.442525])

sf_station = [37.762236,-122.442525, 100]
mv_station = [37.409348,-122.07732, 100]

raw_stamps = []

#first iterate through both files to find the estimated time difference. doesn't have to be accurate to more than 1ms or so.
#to do this, look for type 17 position packets with the same data. assume they're unique. print the tdiff.

#let's do this right for once
#collect a list of raw timestamps for each aircraft from each station
#the raw stamps have to be processed into corrected stamps OR distance has to be included in each
#then postprocess to find clock delay for each and determine drift rate for each aircraft separately
#then come up with an average clock drift rate
#then find rms error

#ok so get [ICAO, [raw stamps], [distance]] for each matched record

files = [sffile, rudifile]
stations = [sf_station, mv_station]

records = []

for each_file in files:
    recordlist = []
    for line in each_file:
        [msgtype, shortdata, longdata, parity, ecc, reference, timestamp] = line.split()
        recordlist.append({"data": {"msgtype": long(msgtype, 10),\
                                    "shortdata": long(shortdata, 16),\
                                    "longdata": long(longdata, 16),\
                                    "parity": long(parity, 16),\
                                    "ecc": long(ecc, 16)},
                           "time": float(timestamp)\
                          })
    records.append(recordlist)

#ok now we have records parsed into something usable that we can == with

def feet_to_meters(feet):
    return feet * 0.3048006096012

all_heard = []
#gather list of reports which were heard by all stations
for station0_report in records[0]: #iterate over list of reports from station 0
    for other_reports in records[1:]:
        stamps = [station0_report["time"]]
        stamp = [report["time"] for report in other_reports if report["data"] == station0_report["data"]]# for other_reports in records[1:]]
        if len(stamp) > 0:
            stamps.append(stamp[0])
    if len(stamps) == len(records): #found same report in all records
        all_heard.append({"data": station0_report["data"], "times": stamps})

#ok, now let's pull out the location-bearing packets so we can find our time offset
position_reports = [x for x in all_heard if x["data"]["msgtype"] == 17 and 9 <= (x["data"]["longdata"] >> 51) & 0x1F <= 18]
offset_list = []
#there's probably a way to list-comprehension-ify this but it looks hard
for msg in position_reports:
    data = msg["data"]
    [alt, lat, lon, rng, bearing] = sfparse.parseBDS05(data["shortdata"], data["longdata"], data["parity"], data["ecc"])
    ac_pos = [lat, lon, feet_to_meters(alt)]
    rel_times = []
    for time, station in zip(msg["times"], stations):
        #here we get the estimated time at the aircraft when it transmitted
        range_to_ac = numpy.linalg.norm(numpy.array(mlat.llh2ecef(station))-numpy.array(mlat.llh2ecef(ac_pos)))
        timestamp_at_ac = time - range_to_ac / mlat.c
        rel_times.append(timestamp_at_ac)
    offset_list.append({"aircraft": data["shortdata"], "times": rel_times})

#this is a list of unique aircraft, heard by all stations, which transmitted position packets
unique_aircraft = list(set([x["aircraft"] for x in offset_list]))
#todo: the below can be done cleaner with nested list comprehensions
for ac in unique_aircraft:
    for i in range(1,len(stations)):
        #pull out a list of unique aircraft from the offset list
        rel_times_for_one_ac = [report["times"][i]-report["times"][0] for report in offset_list if report["aircraft"] == ac]
        abs_times_for_one_ac = [report["times"][0] for report in offset_list if report["aircraft"] == ac]

        #find drift error
        drift_error = [(y-x)/(b-a) for x,y,a,b in zip(rel_times_for_one_ac, rel_times_for_one_ac[1:], abs_times_for_one_ac, abs_times_for_one_ac[1:])]
        drift_error_limited = [x for x in drift_error if abs(x) < 1e-5]
        print "drift from %d relative to station 0 for ac %x: %.3fppm" % (i, ac & 0xFFFFFF, numpy.mean(drift_error_limited) * 1e6)
        
