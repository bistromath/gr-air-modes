#!/usr/bin/python
import mlat
import numpy

replies = []
for i in range(0, len(mlat.teststations)):
    replies.append((mlat.teststations[i], mlat.teststamps[i]))

ans = mlat.mlat(replies, mlat.testalt)
error = numpy.linalg.norm(numpy.array(mlat.llh2ecef(ans))-numpy.array(mlat.testplane))
range = numpy.linalg.norm(mlat.llh2geoid(ans)-numpy.array(mlat.llh2geoid(mlat.teststations[0])))
print "Error: %.2fm" % (error)
print "Range: %.2fkm (from first station in list)" % (range/1000)
