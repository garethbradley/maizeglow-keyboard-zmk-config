#ifndef MPR121_H
#define MPR121_H

#include <zephyr.h>

int mpr121_init(void);
int mpr121_read(uint8_t reg, uint8_t *data, size_t len);

#endif // MPR121_H