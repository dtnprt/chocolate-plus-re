#include "sysex_split.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

unsigned int native_output_callback = CH_HOST_CALLBACK;

int main(void)
{
    unsigned char packet[64];
    unsigned int cable, cin, value, length, expected, checks = 0;
    for (cable = 0; cable < 16; ++cable)
        for (cin = 0; cin < 16; ++cin)
            for (value = 0; value < 256; ++value) {
                memset(packet, 0xa5, sizeof(packet)); /* padding need not be zero */
                packet[0] = (unsigned char)((cable << 4) | cin);
                packet[cin >= 5 && cin <= 7 ? cin - 4 : 1] = (unsigned char)value;
                expected = cin >= 5 && cin <= 7 && value == 0xf7;
                assert(ch_host_boundary(packet, 4) == (int)expected);
                native_output_callback = 0;
                assert(!ch_host_boundary(packet, 4));
                native_output_callback = CH_HOST_CALLBACK;
                ++checks;
            }
    for (length = 0; length <= 65; ++length) {
        memset(packet, 0, sizeof(packet));
        if (length >= 4 && length <= 64) {
            packet[length - 4] = 5;
            packet[length - 3] = 0xf7;
        }
        expected = length >= 4 && length <= 64 && !(length & 3);
        assert(ch_host_boundary(packet, length) == (int)expected);
        ++checks;
    }
    assert(!ch_host_boundary(NULL, 4));
    /* F7 in data/padding or an earlier event must not terminate a continuation. */
    memset(packet, 0xf7, sizeof(packet));
    packet[0] = packet[4] = 4;
    assert(!ch_host_boundary(packet, 8));
    packet[0] = 5;
    assert(!ch_host_boundary(packet, 8));
    packet[4] = 5;
    packet[5] = 0;
    assert(!ch_host_boundary(packet, 8));
    packet[5] = 0xf7;
    assert(ch_host_boundary(packet, 8));
    printf("SysEx split: %u exhaustive cases plus continuation/padding checks passed\n", checks);
    return 0;
}
