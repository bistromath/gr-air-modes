#
# Copyright 2013 Nick Foster
# 
# This file is part of gr-air-modes
# 
# gr-air-modes is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# gr-air-modes is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with gr-air-modes; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

from collections import namedtuple

#this is a timestamp that preserves precision when used with UTC timestamps.
#ordinary double-precision timestamps lose significant fractional precision
#when the exponent is as large as necessary for UTC.
class stamp:
    def __init__(self, secs, frac_secs):
        self.secs = secs
        self.frac_secs = frac_secs
        self.secs += int(self.frac_secs)
        self.frac_secs -= int(self.frac_secs)
    def __lt__(self, other):
        if isinstance(other, self.__class__):
            if self.secs == other.secs:
                return self.frac_secs < other.frac_secs
            else:
                return self.secs < other.secs
        elif isinstance(other, float):
            return float(self) > other
        else:
            raise TypeError
    def __gt__(self, other):
        if type(other) is type(self):
            if self.secs == other.secs:
                return self.frac_secs > other.frac_secs
            else:
                return self.secs > other.secs
        elif type(other) is type(float):
            return float(self) > other
        else:
            raise TypeError
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.secs == other.secs and self.frac_secs == other.frac_secs
        elif isinstance(other, float):
            return float(self) == other
        else:
            raise TypeError
    def __ne__(self, other):
        return not (self == other)
    def __le__(self, other):
        return (self == other) or (self < other)
    def __ge__(self, other):
        return (self == other) or (self > other)

    def __add__(self, other):
        if isinstance(other, self.__class__):
            ipart = self.secs + other.secs
            fpart = self.frac_secs + other.frac_secs
            return stamp(ipart, fpart)
        elif isinstance(other, float):
            return self + stamp(0, other)
        elif isinstance(other, int):
            return self + stamp(other, 0)            
        else:
            raise TypeError
            
    def __sub__(self, other):
        if isinstance(other, self.__class__):
            ipart = self.secs - other.secs
            fpart = self.frac_secs - other.frac_secs
            return stamp(ipart, fpart)
        elif isinstance(other, float):
            return self - stamp(0, other)
        elif isinstance(other, int):
            return self - stamp(other, 0)
        else:
            raise TypeError

    #to ensure we don't hash by stamp
    #TODO fixme with a reasonable hash in case you feel like you'd hash by stamp
    __hash__ = None
    
    #good to within ms for comparison
    def __float__(self):
        return self.secs + self.frac_secs

    def __str__(self):
        return "%f" % float(self)

#a Mode S report including the modes_reply data object
modes_report = namedtuple('modes_report', ['data', 'ecc', 'rssi', 'timestamp'])
#lat, lon, alt
#TODO: a position class internally represented as ECEF XYZ which can easily be used for multilateration and distance calculation
llh = namedtuple('llh', ['lat', 'lon', 'alt'])
mlat_report = namedtuple('mlat_report', ['data', 'nreps', 'timestamp', 'llh', 'hdop', 'vdop'])
