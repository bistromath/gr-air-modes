/* -*- c++ -*- */

#define AIR_MODES_API

%include "gnuradio.i"

%{
#include "gr_air_modes/preamble.h"
#include "gr_air_modes/slicer.h"
%}

%include "gr_air_modes/preamble.h"
%include "gr_air_modes/slicer.h"

GR_SWIG_BLOCK_MAGIC2(air_modes,preamble);
GR_SWIG_BLOCK_MAGIC2(air_modes,slicer);

