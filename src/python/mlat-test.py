#!/usr/bin/python
import mlat
import numpy

ans = mlat.mlat(mlat.teststations, mlat.teststamps, mlat.testalt)
error = numpy.linalg.norm(numpy.array(mlat.llh2ecef(ans))-numpy.array(mlat.testplane))
print error
