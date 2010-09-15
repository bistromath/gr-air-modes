#ifndef INCLUDED_AIR_MODES_FRAMER_H
#define INCLUDED_AIR_MODES_FRAMER_H

#include <gr_sync_block.h>

class air_modes_framer;
typedef boost::shared_ptr<air_modes_framer> air_modes_framer_sptr;

air_modes_framer_sptr air_make_modes_framer(int channel_rate);

/*!
 * \brief mode select framer detection
 * \ingroup block
 */
class air_modes_framer : public gr_sync_block
{
private:
    friend air_modes_framer_sptr air_make_modes_framer(int channel_rate);
    air_modes_framer(int channel_rate);

	int d_check_width;
	int d_chip_rate;
	int d_samples_per_chip;
	int d_samples_per_symbol;

public:
    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};


#endif /* INCLUDED_AIR_MODES_framer_H */
