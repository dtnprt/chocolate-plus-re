/* Experimental 143: one complete SysEx per HOST transfer.
 * No added delay, setting, persistent record or mutable static RAM.
 */
#include "sysex_split.h"

extern unsigned int native_output_callback;

int ch_host_boundary(const unsigned char *chunk, unsigned int length)
{
    unsigned int cin;
    if (native_output_callback != CH_HOST_CALLBACK || !chunk ||
        length < 4 || length > 64 || (length & 3))
        return 0;
    chunk += length - 4;
    cin = chunk[0] & 15;
    return cin >= 5 && cin <= 7 && chunk[cin - 4] == 0xf7;
}
