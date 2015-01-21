#
# Copyright 2008,2009 Free Software Foundation, Inc.
# 
# This application is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This application is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# The presence of this file turns this directory into a Python package

'''
This is the GNU Radio gr-air-modes package. It provides a library and
application for receiving Mode S / ADS-B signals from aircraft. Use
uhd_modes.py as the main application for receiving signals. cpr.py
provides an implementation of Compact Position Reporting. altitude.py
implements Gray-coded altitude decoding. Various plugins exist for SQL,
KML, and PlanePlotter-compliant SBS-1 emulation output. mlat.py provides
an experimental implementation of a multilateration solver.
'''

# ----------------------------------------------------------------
# Temporary workaround for ticket:181 (swig+python problem)
import sys
_RTLD_GLOBAL = 0
try:
    from dl import RTLD_GLOBAL as _RTLD_GLOBAL
except ImportError:
    try:
	from DLFCN import RTLD_GLOBAL as _RTLD_GLOBAL
    except ImportError:
	pass
    
if _RTLD_GLOBAL != 0:
    _dlopenflags = sys.getdlopenflags()
    sys.setdlopenflags(_dlopenflags|_RTLD_GLOBAL)
# ----------------------------------------------------------------


# import swig generated symbols into the gr-air-modes namespace
from air_modes_swig import *

# import any pure python here
#

try:
    import zmq
except ImportError:
    raise RuntimeError("PyZMQ not found! Please install libzmq and PyZMQ to run gr-air-modes")

from rx_path import rx_path
from zmq_socket import zmq_pubsub_iface
from parse import *
from msprint import output_print
from sql import output_sql
from sbs1 import output_sbs1
from kml import output_kml, output_jsonp
from raw_server import raw_server
from radio import modes_radio
from exceptions import *
from az_map import *
from types import *
from altitude import *
from cpr import cpr_decoder
from html_template import html_template
#this is try/excepted in case the user doesn't have numpy installed
try:
    from flightgear import output_flightgear
    from Quaternion import *
except ImportError:
    print "gr-air-modes warning: numpy+scipy not installed, FlightGear interface not supported"
    pass

# ----------------------------------------------------------------
# Tail of workaround
if _RTLD_GLOBAL != 0:
    sys.setdlopenflags(_dlopenflags)      # Restore original flags
# ----------------------------------------------------------------
