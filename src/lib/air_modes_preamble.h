#ifndef INCLUDED_AIR_MODES_PREAMBLE_H
#define INCLUDED_AIR_MODES_PREAMBLE_H

#include <gr_sync_block.h>

class air_modes_preamble;
typedef boost::shared_ptr<air_modes_preamble> air_modes_preamble_sptr;

air_modes_preamble_sptr air_make_modes_preamble(int channel_rate, float threshold_db);

/*!
 * \brief mode select preamble detection
 * \ingroup block
 */
class air_modes_preamble : public gr_sync_block
{
private:
    friend air_modes_preamble_sptr air_make_modes_preamble(int channel_rate, float threshold_db);
    air_modes_preamble(int channel_rate, float threshold_db);

	int d_check_width;
	int d_chip_rate;
	float d_preamble_length_us;
	int d_samples_per_chip;
	int d_samples_per_symbol;
	float d_threshold_db;
	float d_threshold;

public:
    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};

#endif /* INCLUDED_AIR_MODES_PREAMBLE_H */
