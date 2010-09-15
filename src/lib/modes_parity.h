#ifndef INCLUDED_MODES_PARITY_H
#define INCLUDED_MODES_PARITY_H
extern const unsigned int modes_parity_table[112];
int modes_check_parity(unsigned char data[], int length);
bruteResultTypeDef modes_ec_brute(modes_packet &err_packet);
unsigned next_set_of_n_elements(unsigned x);

#endif
