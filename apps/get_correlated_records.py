#!/usr/bin/env python
from air_modes import modes_parse, mlat
import numpy
import sys

#sffile = open("27augsf3.txt")
#rudifile = open("27augrudi3.txt")

#sfoutfile = open("sfout.txt", "w")
#rudioutfile = open("rudiout.txt", "w")

sfparse = modes_parse.modes_parse([37.762236,-122.442525])

sf_station = [37.762236,-122.442525, 100]
mv_station = [37.409348,-122.07732, 100]
bk_station = [37.854246, -122.266701, 100]

raw_stamps = []

#first iterate through both files to find the estimated time difference. doesn't have to be accurate to more than 1ms or so.
#to do this, look for type 17 position packets with the same data. assume they're unique. print the tdiff.

#collect a list of raw timestamps for each aircraft from each station
#the raw stamps have to be processed into corrected stamps OR distance has to be included in each
#then postprocess to find clock delay for each and determine drift rate for each aircraft separately
#then come up with an average clock drift rate
#then find an average drift-corrected clock delay
#then find rms error

#ok so get [ICAO, [raw stamps], [distance]] for each matched record

files = [open(arg) for arg in sys.argv[1:]]

#files = [sffile, rudifile]
stations = [sf_station, mv_station]#, bk_station]

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

#print all_heard

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
    offset_list.append({"aircraft": data["shortdata"] & 0xffffff, "times": rel_times})

#this is a list of unique aircraft, heard by all stations, which transmitted position packets
#we do drift calcs separately for each aircraft in the set because mixing them seems to screw things up
#i haven't really sat down and figured out why that is yet
unique_aircraft = list(set([x["aircraft"] for x in offset_list]))
print "Aircraft heard for clock drift estimate: %s" % [str("%x" % ac) for ac in unique_aircraft]
print "Total reports used: %d over %.2f seconds" % (len(position_reports), position_reports[-1]["times"][0]-position_reports[0]["times"][0])

#get a list of reported times gathered by the unique aircraft that transmitted them
#abs_unique_times = [report["times"] for ac in unique_aircraft for report in offset_list if report["aircraft"] == ac]
#print abs_unique_times
#todo: the below can probably be done cleaner with nested list comprehensions
clock_rate_corrections = [0]
for i in range(1,len(stations)):
    drift_error_limited = []
    for ac in unique_aircraft:
        times = [report["times"] for report in offset_list if report["aircraft"] == ac]

        s0_times = [report[0] for report in times]
        rel_times = [report[i]-report[0] for report in times]

        #find drift error rate
        drift_error = [(y-x)/(b-a) for x,y,a,b in zip(rel_times, rel_times[1:], s0_times[0:], s0_times[1:])]
        drift_error_limited.append([x for x in drift_error if abs(x) < 1e-5])

    #flatten the list of lists (tacky, there's a better way)
    drift_error_limited = [x for sublist in drift_error_limited for x in sublist]
    clock_rate_corrections.append(0-numpy.mean(drift_error_limited))

for i in range(len(clock_rate_corrections)):
    print "drift from %d relative to station 0: %.3fppm" % (i, clock_rate_corrections[i] * 1e6)

#let's get the average clock offset (based on drift-corrected, TDOA-corrected derived timestamps)
clock_offsets = [[numpy.mean([x["times"][i]*(1+clock_rate_corrections[i])-x["times"][0] for x in offset_list])][0] for i in range(0,len(stations))]
for i in range(len(clock_offsets)):
    print "mean offset from %d relative to station 0: %.3f seconds" % (i, clock_offsets[i])

#for the two-station case, let's now go back, armed with our clock drift and offset, and get the variance between expected and observed timestamps
error_list = []
for i in range(1,len(stations)):
    for report in offset_list:
        error = abs(((report["times"][i]*(1+clock_rate_corrections[i]) - report["times"][0]) - clock_offsets[i]) * mlat.c)
        error_list.append(error)
        #print error

rms_error = (numpy.mean([error**2 for error in error_list]))**0.5
print "RMS error in TDOA: %.1f meters" % rms_error
