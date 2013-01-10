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

#this is a timestamp that preserves precision when used with UTC timestamps
#ordinary double-precision timestamp would lose significant fractional precision
#when the mantissa is as large as necessary for UTC timestamps.
class stamp:
    def __init__(self, secs, frac_secs):
        self.secs = secs
        self.frac_secs = frac_secs
    def __lt__(self, other):
        if self.secs == other.secs:
            return self.frac_secs < other.frac_secs
        else:
            return self.secs < other.secs
    def __gt__(self, other):
        if self.secs == other.secs:
            return self.frac_secs > other.frac_secs
        else:
            return self.secs > other.secs
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.secs == other.secs and self.frac_secs == other.frac_secs
        elif isinstance(other, float):
            return float(self) == other
        else:
            raise TypeError
    def __ne__(self, other):
        return self.secs != other.secs or self.frac_secs != other.frac_secs
    def __le__(self, other):
        return (self == other) or (self < other)
    def __ge__(self, other):
        return (self == other) or (self > other)

    #to ensure we don't hash by stamp
    __hash__ = None
    
    #good to within ms for comparison
    def __float__(self):
        return self.secs + self.frac_secs

modes_report = namedtuple('modes_report', ['data', 'ecc', 'reference', 'timestamp'])
