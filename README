========================================================================
Copyright 2010, 2011, 2012 Nick Foster

Quaternion.py copyright 2009 Smithsonian Astrophysical Observatory
   Released under New BSD / 3-Clause BSD License
   All rights reserved

This file is part of gr-air-modes
 
gr-air-modes is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3, or (at your option)
any later version.
 
gr-air-modes is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
 
You should have received a copy of the GNU General Public License
along with gr-air-modes; see the file COPYING.  If not, write to
the Free Software Foundation, Inc., 51 Franklin Street,
Boston, MA 02110-1301, USA.

========================================================================
AUTHOR

Nick Foster <bistromath@gmail.com>

========================================================================
OVERVIEW

gr-air-modes implements a software-defined radio receiver for Mode S
transponder signals, including ADS-B reports from equipped aircraft.

Mode S is the transponder protocol used in modern commercial aircraft.
A Mode S-equipped aircraft replies to radar interrogation by either
ground radar (secondary surveillance) or other aircraft ("Traffic
Collision Avoidance System", or TCAS). The protocol is an extended
version of the Mode A/C protocol used in transponders since the 1940s.
Mode S reports include a unique airframe identifier (referred to
as the "ICAO number") and altitude (to facilitate separation control).
This receiver listens to the 1090MHz downlink channel; interrogation
requests at 1030MHz are not received or decoded by this program.

Automatic Dependent Surveillance-Broadcast (ADS-B) is a communication
protocol using the Extended Squitter capability of the Mode S transport
layer. There are other implementations (VDL Mode 2 and UAT, for
instance) but Mode S remains the primary ADS-B transport for commercial
use. The protocol is:

* Automatic: it requires no pilot input
* Dependent: it is dependent on altimeter, GPS, and other aircraft
  instrumentation for information
* Surveillance: it provides current information about the transmitting
  aircraft
* Broadcast: it is one-way, broadcast to all receivers within range.

ADS-B-equipped aircraft broadcast ("squitter") their position, velocity,
flight number, and other interesting information to any receiver within
range of the aircraft. Position reports are typically generated once per
second and flight indentification every five seconds.

Implementation of ADS-B is mandatory in European airspace as well as
in Australia. North American implementation is still voluntary, with
a mandate arriving in 2020 via the FAA's "NextGen" program.

The receiver modes_rx is written for use with Ettus Research USRP
devices, although the "RTLSDR" receivers are also supported via the
Osmocom driver. In theory, any receiver which outputs complex samples at
at least 2Msps should work via the file input or UDP input options, or
by means of a Gnuradio interface. Multiple output formats are supported:

* Raw (or minimally processed) output of packet data
* Parsed text
* SQLite database
* KML for use with Google Earth
* SBS-1-compatible output for use with e.g. PlanePlotter or Virtual
  Radar Server
* FlightGear multiplayer interface for real-time display of traffic
  within the simulator

Most of the common ADS-B reports are fully decoded per specification.
Those that are not are generally ones which are not commonly used.

Should you receive a large number of reports which result in
"not implemented" or "No handler" messages, please use the -w option to
save raw data and forward it to the author. To save time, note that
receiving a small number of spurious reports is expected; false reports
can be excluded by looking for multiple reports from the same aircraft
(i.e., the same ICAO 6-digit hexadecimal number).

========================================================================
REQUIREMENTS

gr-air-modes requires:

* Python >= 2.5 (written for Python 2.7, Python 3.0 might work)
** NumPy and SciPy are required for the FlightGear output plugin.
* PyZMQ
* Gnuradio >= 3.5.0
* Ettus UHD >= 3.4.0 for use with USRPs
* osmosdr (any version) for use with RTLSDR dongles
* SQLite 3.7 or later
* CMake 2.6 or later

========================================================================
BUILDING

gr-air-modes uses CMake as its build system. To build, from the top
level directory, type:

$ mkdir build
$ cd build
$ cmake ../
$ make
$ sudo make install
$ sudo ldconfig

This will build gr-air-modes out of the source tree in build/ and
install it on your system, generally in /usr/local/bin.

========================================================================
USAGE

The main application is modes_rx. For a complete list of options,
run:

$ modes_rx --help

For use with Ettus UHD-compatible devices, the defaults should suffice
to receive reports and print to the screen. Use the -d option to look
for an RTLSDR-type dongle using the osmosdr driver.

In particular, the --location option can be used to set the receiving
location's GPS coordinates. This enables range and bearing calculations
in the printed display as well as range rings in the Google Earth
interface.

========================================================================
FILES

Interesting files and libraries included with the package:

* apps/modes_rx: The main application.
* apps/get_correlated_records.py: Demonstration program for computing
  multilaterated time error for two unsynchronized receiver stations.
* lib/air_modes_int_and_dump.cc: Unused integrate-and-dump filter for
  demodulating Mode S waveforms.
* lib/air_modes_preamble.cc: Mode S preamble detector.
* lib/air_modes_slicer.cc: Bit slicer (1 vs 0) and packet aggregator.
* lib/modes_crc.cc: Computes parity check for Mode S packets.
* python/altitude.py: Mode S altitude encoding/decoding routines
* python/cpr.py: Compact Position Reporting encoder/decoder
* python/modes_flightgear.py: FlightGear (open-source flight simulator)
  plugin which inserts live traffic into the simulator via the
  multiplayer interface.
* python/mlat.py: Multilateration algorithms for determining position of
  non-ADS-B-equipped or non-cooperative aircraft using multiple
  receivers.
* python/modes_kml.py: KML output plugin for Google Earth.
* python/modes_parse.py: Mode S/ADS-B packet parsing routines.
* python/modes_print.py: Human-readable printout plugin
* python/modes_raw_server.py: UDP output plugin for raw data output
* python/modes_sbs1.py: SBS-1-compatible output plugin for use with
  Virtual Radar Server, PlanePlotter, or other compatible programs.
* python/modes_sql.py: SQLite interface for storing reports in a
  database.
* python/Quaternion.py: Quaternion library used to calculate
  orientation of aircraft for FlightGear plugin.
