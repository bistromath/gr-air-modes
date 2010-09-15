#ifndef AIR_MODES_TYPES_H
#define AIR_MODES_TYPES_H

typedef enum { No_Packet = 0, Short_Packet = 1, Fruited_Packet = 2, Long_Packet = 3 } framer_packet_type;
typedef enum { No_Error = 0, Solution_Found, Too_Many_LCBs, No_Solution, Multiple_Solutions } bruteResultTypeDef;

struct modes_packet {
	unsigned char data[14];
//	unsigned char confidence[14]; //112 bits of boolean high/low confidence data for each bit
	unsigned char lowconfbits[24]; //positions of low confidence bits within the packet

	unsigned long parity;
	unsigned int numlowconf;
	framer_packet_type type; //what length packet are we
	unsigned int message_type;
	float reference_level;
};

#endif
