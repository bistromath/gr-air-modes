#!/usr/bin/python
import math
import numpy
from scipy.ndimage import map_coordinates

#functions for multilateration.
#this library is more or less based around the so-called "GPS equation", the canonical
#iterative method for getting position from GPS satellite time difference of arrival data.
#here, instead of multiple orbiting satellites with known time reference and position,
#we have multiple fixed stations with known time references (GPSDO, hopefully) and known
#locations (again, GPSDO).

#NB: because of the way this solver works, at least 3 stations and timestamps
#are required. this function will not return hyperbolae for underconstrained systems.
#TODO: get HDOP out of this so we can draw circles of likely position and indicate constraint
########################END NOTES#######################################


#this is a 10x10-degree WGS84 geoid datum, in meters relative to the WGS84 reference ellipsoid. given the maximum slope, you should probably interpolate.
#NIMA suggests a 2x2 interpolation using four neighbors. we'll go cubic spline JUST BECAUSE WE CAN
wgs84_geoid = numpy.array([[13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13,13],                       #90N
               [3,1,-2,-3,-3,-3,-1,3,1,5,9,11,19,27,31,34,33,34,33,34,28,23,17,13,9,4,4,1,-2,-2,0,2,3,2,1,1],                                       #80N
               [2,2,1,-1,-3,-7,-14,-24,-27,-25,-19,3,24,37,47,60,61,58,51,43,29,20,12,5,-2,-10,-14,-12,-10,-14,-12,-6,-2,3,6,4],                    #70N
               [2,9,17,10,13,1,-14,-30,-39,-46,-42,-21,6,29,49,65,60,57,47,41,21,18,14,7,-3,-22,-29,-32,-32,-26,-15,-2,13,17,19,6],                 #60N
               [-8,8,8,1,-11,-19,-16,-18,-22,-35,-40,-26,-12,24,45,63,62,59,47,48,42,28,12,-10,-19,-33,-43,-42,-43,-29,-2,17,23,22,6,2],            #50N
               [-12,-10,-13,-20,-31,-34,-21,-16,-26,-34,-33,-35,-26,2,33,59,52,51,52,48,35,40,33,-9,-28,-39,-48,-59,-50,-28,3,23,37,18,-1,-11],     #40N
               [-7,-5,-8,-15,-28,-40,-42,-29,-22,-26,-32,-51,-40,-17,17,31,34,44,36,28,29,17,12,-20,-15,-40,-33,-34,-34,-28,7,29,43,20,4,-6],       #30N
               [5,10,7,-7,-23,-39,-47,-34,-9,-10,-20,-45,-48,-32,-9,17,25,31,31,26,15,6,1,-29,-44,-61,-67,-59,-36,-11,21,39,49,39,22,10],           #20N
               [13,12,11,2,-11,-28,-38,-29,-10,3,1,-11,-41,-42,-16,3,17,33,22,23,2,-3,-7,-36,-59,-90,-95,-63,-24,12,53,60,58,46,36,26],             #10N
               [22,16,17,13,1,-12,-23,-20,-14,-3,14,10,-15,-27,-18,3,12,20,18,12,-13,-9,-28,-49,-62,-89,-102,-63,-9,33,58,73,74,63,50,32],          #0
               [36,22,11,6,-1,-8,-10,-8,-11,-9,1,32,4,-18,-13,-9,4,14,12,13,-2,-14,-25,-32,-38,-60,-75,-63,-26,0,35,52,68,76,64,52],                #10S
               [51,27,10,0,-9,-11,-5,-2,-3,-1,9,35,20,-5,-6,-5,0,13,17,23,21,8,-9,-10,-11,-20,-40,-47,-45,-25,5,23,45,58,57,63],                    #20S
               [46,22,5,-2,-8,-13,-10,-7,-4,1,9,32,16,4,-8,4,12,15,22,27,34,29,14,15,15,7,-9,-25,-37,-39,-23,-14,15,33,34,45],                      #30S
               [21,6,1,-7,-12,-12,-12,-10,-7,-1,8,23,15,-2,-6,6,21,24,18,26,31,33,39,41,30,24,13,-2,-20,-32,-33,-27,-14,-2,5,20],                   #40S
               [-15,-18,-18,-16,-17,-15,-10,-10,-8,-2,6,14,13,3,3,10,20,27,25,26,34,39,45,45,38,39,28,13,-1,-15,-22,-22,-18,-15,-14,-10],           #50S
               [-45,-43,-37,-32,-30,-26,-23,-22,-16,-10,-2,10,20,20,21,24,22,17,16,19,25,30,35,35,33,30,27,10,-2,-14,-23,-30,-33,-29,-35,-43],      #60S
               [-61,-60,-61,-55,-49,-44,-38,-31,-25,-16,-6,1,4,5,4,2,6,12,16,16,17,21,20,26,26,22,16,10,-1,-16,-29,-36,-46,-55,-54,-59],            #70S
               [-53,-54,-55,-52,-48,-42,-38,-38,-29,-26,-26,-24,-23,-21,-19,-16,-12,-8,-4,-1,1,4,4,6,5,4,2,-6,-15,-24,-33,-40,-48,-50,-53,-52],     #80S
               [-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30,-30]], #90S
               dtype=numpy.float)
               
#ok this calculates the geoid offset from the reference ellipsoid
#combined with LLH->ECEF this gets you XYZ for a ground-referenced point
def wgs84_height(lat, lon):
    yi = numpy.array([9-lat/10.0])
    xi = numpy.array([18+lon/10.0])
    return float(map_coordinates(wgs84_geoid, [yi, xi]))

#WGS84 reference ellipsoid constants
wgs84_a = 6378137.0
wgs84_b = 6356752.314245
wgs84_e2 = 0.0066943799901975848
wgs84_a2 = wgs84_a**2 #to speed things up a bit
wgs84_b2 = wgs84_b**2

#convert ECEF to lat/lon/alt without geoid correction
#returns alt in meters
def ecef2llh((x,y,z)):
    ep  = math.sqrt((wgs84_a2 - wgs84_b2) / wgs84_b2)
    p   = math.sqrt(x**2+y**2)
    th  = math.atan2(wgs84_a*z, wgs84_b*p)
    lon = math.atan2(y, x)
    lat = math.atan2(z+ep**2*wgs84_b*math.sin(th)**3, p-wgs84_e2*wgs84_a*math.cos(th)**3)
    N   = wgs84_a / math.sqrt(1-wgs84_e2*math.sin(lat)**2)
    alt = p / math.cos(lat) - N
    
    lon *= (180. / math.pi)
    lat *= (180. / math.pi)
    
    return [lat, lon, alt]

#convert lat/lon/alt coords to ECEF without geoid correction, WGS84 model
#remember that alt is in meters
def llh2ecef((lat, lon, alt)):
    lat *= (math.pi / 180.0)
    lon *= (math.pi / 180.0)
    
    n = lambda x: wgs84_a / math.sqrt(1 - wgs84_e2*(math.sin(x)**2))
    
    x = (n(lat) + alt)*math.cos(lat)*math.cos(lon)
    y = (n(lat) + alt)*math.cos(lat)*math.sin(lon)
    z = (n(lat)*(1-wgs84_e2)+alt)*math.sin(lat)
    
    return [x,y,z]
    
#do both of the above to get a geoid-corrected x,y,z position
def llh2geoid((lat, lon, alt)):
    (x,y,z) = llh2ecef((lat, lon, alt + wgs84_height(lat, lon)))
    return [x,y,z]


c = 299792458 / 1.0003 #modified for refractive index of air, why not

#this function is the iterative solver core of the mlat function below
#we use limit as a goal to stop solving when we get "close enough" (error magnitude in meters for that iteration)
#basically 20 meters is way less than the anticipated error of the system so it doesn't make sense to continue
#it's possible this could fail in situations where the solution converges slowly
#THIS WORKS PLEASE DON'T MESS WITH IT
def mlat_iter(stations, prange_obs, guess = [0,0,0], limit = 20, maxrounds = 100):
    xerr = [1e9, 1e9, 1e9, 1e9]
    rounds = 0
    while numpy.linalg.norm(xerr[:3]) > limit:
        #get p_i, the estimated pseudoranges based on the latest position guess
        prange_est = [[numpy.linalg.norm(station - guess)] for station in stations]
        #get the difference d_p^ between the observed and calculated pseudoranges
        dphat = prange_obs - prange_est
        #create a matrix of partial differentials to find the slope of the error in X,Y,Z,t directions
        H = numpy.array([(numpy.array(-stations[row,:])+guess) / prange_est[row] for row in range(len(stations))])
        H = numpy.append(H, numpy.ones(len(prange_obs)).reshape(len(prange_obs),1)*c, axis=1)
        #now we have H, the Jacobian, and can solve for residual error
        solved = numpy.linalg.lstsq(H, dphat)
        xerr = solved[0].flatten()
        guess += xerr[:3] #we ignore the time error for xguess
        rounds += 1
        if rounds > maxrounds:
            raise Exception("Failed to converge!")
    return (guess, xerr[3])

#func mlat:
#uses a modified GPS pseudorange solver to locate aircraft by multilateration.
#replies is a list of reports, in ([lat, lon, alt], timestamp) format
#altitude is the barometric altitude of the aircraft as returned by the aircraft, if any
#returns the estimated position of the aircraft in (lat, lon, alt) geoid-corrected WGS84.
#let's make it take a list of tuples so we can sort by them
def mlat(replies, altitude):
    sorted_replies = sorted(replies, key=lambda time: time[1])

    stations = [sorted_reply[0] for sorted_reply in sorted_replies]
    timestamps = [sorted_reply[1] for sorted_reply in sorted_replies]
    nearest_llh = stations[0]
    stations_xyz = numpy.array([llh2geoid(station) for station in stations])

    #the absolute time shouldn't matter at all except perhaps in
    #maintaining floating-point precision; in other words you can
    #add a constant here and it should fall out in the solver as time error
    prange_obs = [[c*stamp] for stamp in timestamps]

    #if no alt, use a reasonably large number (in meters)
    #since if all your stations lie in a plane (they basically will),
    #there's a reasonable solution at negative altitude as well
    if altitude is None:
        altitude = 20000
    firstguess = numpy.array(llh2ecef((nearest_llh[0], nearest_llh[1], altitude)))

    prange_obs = numpy.array(prange_obs)
    xyzpos, time_offset = mlat_iter(stations_xyz, prange_obs, firstguess, maxrounds=100)
    llhpos = ecef2llh(xyzpos)
    
    return (llhpos, time_offset)

#tests the mlat_iter algorithm using sample data from Farrell & Barth (p.147)
def farrell_barth_test():
    pranges = numpy.array([[22228206.42],
                           [24096139.11],
                           [21729070.63],
                           [21259581.09]])
    svpos = numpy.array([[7766188.44, -21960535.34, 12522838.56],
                         [-25922679.66, -6629461.28, 31864.37],
                         [-5743774.02, -25828319.92, 1692757.72],
                         [-2786005.69, -15900725.80, 21302003.49]])

    #this is the "correct" resolved position, not the real receiver position
    known_pos = numpy.array( [-2430745.0959362, -4702345.11359277, 3546568.70599656])

    pos, time_offset = mlat_iter(svpos, pranges)
    print "Position: ", pos
    print "LLH: ", ecef2llh(pos)
    error = numpy.linalg.norm(pos - known_pos)
    print "Error: ", error
    if error < 1e-3:
        print "Farrell & Barth test OK"
    else:
        raise Exception("ERROR: Failed Farrell & Barth test")

if __name__ == '__main__':
    #check to see that you haven't screwed up mlat_iter
    farrell_barth_test()

    #construct simulated returns from these stations
    teststations = [[37.76225, -122.44254, 100], [37.680016,-121.772461, 100], [37.385844,-122.083082, 100], [37.701207,-122.309418, 100]]
    testalt      = 8000
    testplane    = numpy.array(llh2ecef([37.617175,-122.400843, testalt]))
    tx_time      = 10 #time offset to apply to timestamps
    teststamps   = [tx_time+numpy.linalg.norm(testplane-numpy.array(llh2geoid(station))) / c for station in teststations]

    print "Actual pranges: ", sorted([numpy.linalg.norm(testplane - numpy.array(llh2geoid(station))) for station in teststations])

    replies = [(station, stamp) for station,stamp in zip(teststations, teststamps)]

    ans, offset = mlat(replies, testalt)
    error = numpy.linalg.norm(numpy.array(llh2ecef(ans))-numpy.array(testplane))
    rng = numpy.linalg.norm(llh2geoid(ans)-numpy.array(llh2geoid(teststations[0])))
    print "Resolved lat/lon/alt: ", ans
    print "Error: %.2fm" % (error)
    print "Range: %.2fkm (from first station in list)" % (rng/1000)
    print "Aircraft-local transmit time: %.8fs" % (offset)
