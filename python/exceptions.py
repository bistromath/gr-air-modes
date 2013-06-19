#
# Copyright 2012 Nick Foster
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

class ADSBError(Exception):
    pass

class MetricAltError(ADSBError):
    pass

class ParserError(ADSBError):
    pass

class NoHandlerError(ADSBError):
    def __init__(self, msgtype=None):
        self.msgtype = msgtype

class MlatNonConvergeError(ADSBError):
    pass

class CPRNoPositionError(ADSBError):
    pass

class CPRBoundaryStraddleError(CPRNoPositionError):
    pass

class FieldNotInPacket(ParserError):
    def __init__(self, item):
        self.item = item

