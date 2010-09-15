#include <air_modes_types.h>
#include <modes_energy.h>

//helper functions to calculate bit energy and Eb/No

//this is a really cheesy early/late gate synchronizer. compares bit energy 
int early_late(const float *data, int samples_per_chip) {
	float gate_sum_early=0, gate_sum_now=0, gate_sum_late=0;

	gate_sum_early = bit_energy(&data[-1], samples_per_chip);
	gate_sum_now = bit_energy(&data[0], samples_per_chip);
	gate_sum_late = bit_energy(&data[1], samples_per_chip);

	if(gate_sum_early > gate_sum_now) return -1;
	else if(gate_sum_late > gate_sum_now) return 1;
	else return 0;
}

//return total bit energy of a chip centered at the current point (we bias right for even samples per chip)
float bit_energy(const float *data, int samples_per_chip) {
	float energy = 0;
	if(samples_per_chip <= 2) {
		energy = data[0];
	} else {
		for(int j = 1-samples_per_chip/2; j < samples_per_chip/2; j++) {
			energy += data[j];
		}
	}
	return energy;
}
