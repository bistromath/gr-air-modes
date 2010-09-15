#ifndef INCLUDED_AIR_MODES_slicer_H
#define INCLUDED_AIR_MODES_slicer_H

#include <gr_sync_block.h>
#include <gr_msg_queue.h>

class air_modes_slicer;
typedef boost::shared_ptr<air_modes_slicer> air_modes_slicer_sptr;

air_modes_slicer_sptr air_make_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);

/*!
 * \brief mode select slicer detection
 * \ingroup block
 */
class air_modes_slicer : public gr_sync_block
{
private:
    friend air_modes_slicer_sptr air_make_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);
    air_modes_slicer(int channel_rate, gr_msg_queue_sptr queue);

	int d_check_width;
	int d_chip_rate;
	int d_samples_per_chip;
	int d_samples_per_symbol;
	gr_msg_queue_sptr d_queue;
    std::ostringstream d_payload;

public:
    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);
};

#endif /* INCLUDED_AIR_MODES_slicer_H */
