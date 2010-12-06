#!/usr/bin/python
import math
import numpy
from scipy.ndimage import map_coordinates

#functions for multilateration.

#NB: because of the way this solver works, at least 3 stations and timestamps
#are required. this function will not return hyperbolae for underconstrained systems.
#TODO: get HDOP out of this so we can draw circles of likely position and indicate constraint

##########################NOTES#########################################
#you should test your solver with a reference dataset that you've calculated. let's put one together.
#let's say we have you here in SF, ER in MV, and some place in Fremont. the plane can be at SFO at 24000'.
#your pos: 37.76225, -122.44254, 300'
#ettus: 37.409044, -122.077748, 300'
#fremont: 37.585085, -121.986395, 300'
#airplane: 37.617175,-122.380843, 24000'

#calculated using a third-party tool and verified against the algorithms in this file:
#you: -2708399, -4260759, 3884677
#ettus: -2693916, -4298177, 3853611
#fremont: -2680759, -4292379, 3869113
#airplane: -2712433, -4277271, 3876757

#here's how I did it in Octave...
#prange_est = ((stations(:, 1) - xguess(1)).^2 + (stations(:, 2) - xguess(2)).^2 + (stations(:,3) - xguess(3)).^2).^0.5;
#dphat = prange_obs - prange_est;
#H = [[-(stations(:,1)-xguess(1)) ./ prange_est, -(stations(:,2)-xguess(2)) ./ prange_est, -(stations(:,3)-xguess(3)) ./ prange_est]];
#xerr = (H'*H\H'*dphat)';
#xguess = xguess + xerr
#remember the last line of stations is the 0 vector. remember the last line of prange_obs is the height of the a/c above geoid.

#use one of the station positions as a starting guess. calculate alt-above-geoid once as though it were located directly above the starting guess; 300 miles
#is like 4 degrees of latitude and i don't think it'll introduce more than a few meters of error.

#well, there are some places where 4 degrees of latitude would count for 20 meters of error. but since our accuracy is really +/- 250m anyway it's probably not
#a big deal. saves a lot of CPU to only do the lookup once.

#so, the above solver works for pseudorange, but what if you only have time-of-flight info?
#let's modify the prange eq to deal with time difference of arrival instead of pseudorange
#knowns: time of arrival at each station, positions of each station, altitude of a/c
#from this, you can say "it arrived x ns sooner at each of the other stations"
#thus you can say "it's this much closer/farther to station y than to me"

#the stations vector is RELATIVE TO YOU -- so it's [ettus-me; fremont-me; [0,0,0]-me]
#prange_obs is a vector of TDOAs; the first value (earliest) is truncated since the difference is zero (just like stations)
#this implies the TDOAs should arrive sorted, which is probably a good idea, or at the very least the closest station should be first

#prange_est = [norm(stations(1,:)-xguess);
#              norm(stations(2,:)-xguess);
#              norm(stations(3,:)-xguess)]; #only valid for the three-station case we're testing Octave with
#dphat = prange_obs - prange_est;
#H = [[-(stations(:,1)-xguess(1)) ./ prange_est, -(stations(:,2)-xguess(2)) ./ prange_est, -(stations(:,3)-xguess(3)) ./ prange_est]];
#xguess += (H'*H\H'*dphat)';
#err=norm(airplane-(xguess+me)) #just for calculating convergence

#it converges for 500km position error in the initial guess, so it seems pretty good.
#seems to converge quickly in the terminal phase. 250m timing offset gives 450m position error
#250m time offset in the local receiver (830ns) gives 325m position error

#the last question is how to use the altitude data in prange_obs; calculate height above geoid for YOUR position at a/c alt and use that to get height above [0,0,0]
#this will be close enough. you could iterate this along with the rest of it but it won't change more than the variation in geoid height between you and a/c.
#maybe after convergence you can iterate a few more times with the a/c geoid height if you're worried about it.
#there's probably a way to use YOU as the alt. station and just use height above YOU instead. but this works.

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

#here's some test data to validate the algorithm
teststations = [[37.76225, -122.44254, 100], [37.409044, -122.077748, 100], [37.585085, -121.986395, 100]]
testalt      = 8000
testplane    = numpy.array(llh2ecef([37.617175,-122.380843, testalt]))
testme       = llh2geoid(teststations[0])
teststamps   = [10, 
                10 + numpy.linalg.norm(testplane-numpy.array(llh2geoid(teststations[1]))) / c,
                10 + numpy.linalg.norm(testplane-numpy.array(llh2geoid(teststations[2]))) / c,
               ]

#this function is the iterative solver core of the mlat function below
def mlat_iter(rel_stations, prange_obs, xguess = [0,0,0], numrounds = 10):
    for i in range(0,numrounds):
        prange_est = []
        for station in rel_stations:
            prange_est.append([numpy.linalg.norm(station - xguess)])
        dphat = prange_obs - prange_est
        H = []
        for row in range(0,len(rel_stations)):
            H.append((numpy.array(-rel_stations[row,:])-xguess) / prange_est[row])
        H = numpy.array(H)
        #now we have H, the Jacobian, and can solve for residual error
        xerr = numpy.dot(numpy.linalg.solve(numpy.dot(H.T,H), H.T), dphat).flatten()
        xguess += xerr
    return xguess

#func mlat:
#uses a modified GPS pseudorange solver to locate aircraft by multilateration.
#stations is a list of listening station positions in X,Y,Z ECEF format, geoid corrected
#timestamps is a list of times at which the correlated squitters were heard
#altitude is the barometric altitude of the aircraft as returned by the aircraft
#returns the estimated position of the aircraft in (lat, lon, alt) geoid-corrected WGS84.
def mlat(stations, timestamps, altitude):
    if len(timestamps) != len(stations): 
        raise Exception("Must have x timestamps for x stations reporting!")

    me_llh = stations[0]
    me = llh2geoid(stations[0])
    
    rel_stations = [] #list of stations in XYZ relative to me
    for station in stations[1:]:
        rel_stations.append(numpy.array(llh2geoid(station)) - numpy.array(me))
    rel_stations.append([0,0,0]-numpy.array(me)) #arne saknussemm, reporting in
    rel_stations = numpy.array(rel_stations) #convert list of arrays to 2d array
    
    tdoa = []
    for stamp in timestamps[1:]:
        tdoa.append(stamp - timestamps[0])
    
    prange_obs = []
    for stamp in tdoa:
        prange_obs.append([c * stamp])

    #so here we calc the estimated pseudorange to the center of the earth, using station[0] as a reference point for the geoid
    #this is a necessary approximation since we don't know the location of the aircraft yet
    #if the dang earth were actually round this wouldn't be an issue
    prange_obs.append( [numpy.linalg.norm(llh2ecef((me_llh[0], me_llh[1], altitude)))] ) #use ECEF not geoid since alt is MSL not GPS
    #prange_obs.append( [numpy.linalg.norm(testplane)]) #test for error
    prange_obs = numpy.array(prange_obs)
    
    xyzpos = mlat_iter(rel_stations, prange_obs)
    llhpos = ecef2llh(xyzpos+me)
    
    #now, we could return llhpos right now and be done with it.
    #but the assumption we made above, namely that the aircraft is directly above the
    #nearest station, results in significant error due to the oblateness of the Earth's geometry.
    #so now we solve AGAIN, but this time with the corrected pseudorange of the aircraft altitude
    #this might not be really useful in practice but the sim shows >50m errors without it
    prange_obs[-1] = [numpy.linalg.norm(llh2ecef((llhpos[0], llhpos[1], altitude)))]
    
    xyzpos_corr = mlat_iter(rel_stations, prange_obs, xyzpos) #start off with a really close guess
    llhpos = ecef2llh(xyzpos_corr+me)
    
    return llhpos
