#!/usr/bin/python
import mlat
import numpy

#here's some test data to validate the algorithm
teststations = [[37.76225, -122.44254, 100], [37.409044, -122.077748, 100], [37.585085, -121.986395, 100]]
testalt      = 8000
testplane    = numpy.array(mlat.llh2ecef([37.617175,-122.380843, testalt]))
testme       = mlat.llh2geoid(teststations[0])
teststamps   = [10, 
                10 + numpy.linalg.norm(testplane-numpy.array(mlat.llh2geoid(teststations[1]))) / mlat.c,
                10 + numpy.linalg.norm(testplane-numpy.array(mlat.llh2geoid(teststations[2]))) / mlat.c,
               ]

replies = []
for i in range(0, len(teststations)):
    replies.append((teststations[i], teststamps[i]))

ans = mlat.mlat(replies, testalt)
error = numpy.linalg.norm(numpy.array(mlat.llh2ecef(ans))-numpy.array(testplane))
range = numpy.linalg.norm(mlat.llh2geoid(ans)-numpy.array(mlat.llh2geoid(teststations[0])))
print "Error: %.2fm" % (error)
print "Range: %.2fkm (from first station in list)" % (range/1000)
