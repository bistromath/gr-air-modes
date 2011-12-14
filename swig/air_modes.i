/* -*- c++ -*- */

%include "gnuradio.i"			// the common stuff

%{
#include "air_modes_preamble.h"
#include "air_modes_slicer.h"
#include <gr_msg_queue.h>
%}

// ----------------------------------------------------------------

/*
 * First arg is the package prefix.
 * Second arg is the name of the class minus the prefix.
 *
 * This does some behind-the-scenes magic so we can
 * access howto_square_ff from python as howto.square_ff
 */
GR_SWIG_BLOCK_MAGIC(air,modes_preamble);

air_modes_preamble_sptr air_make_modes_preamble (int channel_rate, float threshold_db);

class air_modes_preamble : public gr_sync_block
{
private:
  air_modes_preamble (int channel_rate, float threshold_db);
};

GR_SWIG_BLOCK_MAGIC(air,modes_slicer);

air_modes_slicer_sptr air_make_modes_slicer (int channel_rate, gr_msg_queue_sptr queue);

class air_modes_slicer : public gr_block
{
private:
	air_modes_slicer (int channel_rate, gr_msg_queue_sptr queue);
};

// ----------------------------------------------------------------

