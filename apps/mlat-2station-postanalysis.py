#!/usr/bin/env python
import numpy
import mlat

#rudi says:
#17 8da12615 903bf4bd3eb2c0 36ac95 000000 0.0007421782357 2.54791875
#17 8d4b190a 682de4acf8c177 5b8f55 000000 0.0005142348236 2.81227225

#sf says:
#17 8da12615 903bf4bd3eb2c0 36ac95 000000 0.003357535461 00.1817445
#17 8d4b190a 682de4acf8c177 5b8f55 000000 0.002822938375 000.446215

sf_station = [37.762236,-122.442525, 100]
mv_station = [37.409348,-122.07732, 100]

report1_location = [37.737804, -122.485139, 3345]
report1_sf_tstamp = 0.1817445
report1_mv_tstamp = 2.54791875

report2_location = [37.640836, -122.260218, 2484]
report2_sf_tstamp = 0.446215
report2_mv_tstamp = 2.81227225

report1_tof_sf = numpy.linalg.norm(numpy.array(mlat.llh2ecef(sf_station))-numpy.array(mlat.llh2ecef(report1_location))) / mlat.c
report1_tof_mv = numpy.linalg.norm(numpy.array(mlat.llh2ecef(mv_station))-numpy.array(mlat.llh2ecef(report1_location))) / mlat.c

report1_sf_tstamp_abs = report1_sf_tstamp - report1_tof_sf
report1_mv_tstamp_abs = report1_mv_tstamp - report1_tof_mv

report2_tof_sf = numpy.linalg.norm(numpy.array(mlat.llh2ecef(sf_station))-numpy.array(mlat.llh2ecef(report2_location))) / mlat.c
report2_tof_mv = numpy.linalg.norm(numpy.array(mlat.llh2ecef(mv_station))-numpy.array(mlat.llh2ecef(report2_location))) / mlat.c

report2_sf_tstamp_abs = report2_sf_tstamp - report2_tof_sf
report2_mv_tstamp_abs = report2_mv_tstamp - report2_tof_mv

dt1 = report1_sf_tstamp_abs - report1_mv_tstamp_abs
dt2 = report2_sf_tstamp_abs - report2_mv_tstamp_abs

error = abs((dt1-dt2) * mlat.c)
print error
