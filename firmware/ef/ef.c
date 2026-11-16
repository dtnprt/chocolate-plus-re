/* E/F switches (modes 3, 10, 11) and power-on mode selection for the FootCtrlPlus custom firmware 151-ef.
 *
 * k = 0..3 switches A-D, 4/5 = combos A+B (E) / C+D (F), 0x80 = expression pedal.
 * ev: 1 press, 0 release, 2 long press, 3 release after long press.
 *
 * "E/F on" (no groups): mode 3 when its max group index is 0, mode 10 / 11 when CFG bit 0 / 1 is set.
 * E/F settings live in group 2 switch A / B of the mode. The combo code (combo.s) flags A/C in SCR[0]/SCR[1]
 * when the combo is detected; every event of that press is then reported as E/F.
 *
 * Settings RAM used as config/scratch: group 8 / switch D / SysEx B bytes 116..127 of Advanced custom
 * (offsets 13425..13436). CFG = bytes 116..121 (saved with the settings), SCR = bytes 122..127 (runtime).
 *   CFG[0]   bit 0: E/F in mode 10, bit 1: E/F in mode 11
 *   CFG[1+i] power-on mode when switch A+i is held: 0 = nothing, else mode + 1 (sticky: saved by the firmware)
 */
typedef unsigned char u8;
#define SET     ((volatile u8 *)0x13490)     /* settings block in RAM */
#define MODE    SET[0]
#define BANKMAX SET[0x5c57]                  /* advanced custom: max group index (0 = one group) */
#define BANK    SET[0x5c58]                  /* advanced custom: current group */
#define HIDPAGE SET[0x5c59]                  /* custom keyboard: current group */
#define MIXPAGE SET[0x5c5d]                  /* mixed key: current group */
#define SHOWN   (*(volatile u8 *)0x193ca)    /* stock: shown group number */
#define CFG     ((volatile u8 *)0x16901)
#define SCR     ((volatile u8 *)0x16907)
#define RAM193  ((volatile u8 *)0x193a0)
#define DISPLAY (*(volatile unsigned *)0x19494)   /* 0x193a0 + 0xf4: display segments */
#define SAVE_TIMER (*(volatile unsigned short *)0x193f0) /* 0x193a0 + 0x50: settings save countdown */
#define HIDKEY  ((const u8 *)0x1e18e0c)       /* key index -> HID usage / modifier bits */
#define PINS    ((const unsigned *)0x1e18b30) /* footswitch GPIO numbers A..D */

extern void adv_send(volatile u8 *entry, volatile u8 *toggle, volatile u8 *lng, int ev, int sw);
extern void pedal(int v);
extern void bank_now(void);
extern int gpio_read(unsigned pin);
extern int vbat_percent(void);
extern void disp3(int c0, int c1, int c2, int r3);
extern void hid_send(int id, u8 *buf, int len);
extern void mix_key(int k, int ev);          /* stock mode 11 handler */

/* E/F enabled in the current mode? (also called from combo.s, keeps r4-r14) */
int __attribute__((section(".ef"))) ef_cur(void)
{
    unsigned m = MODE;
    if (m == 3) return BANKMAX == 0;
    if (m == 10) return CFG[0] & 1;
    if (m == 11) return CFG[0] & 2;
    return 0;
}

/* A/C held as part of E/F -> 4/5; clears the flag on the release event */
int __attribute__((section(".ef"))) alias(int k, int ev)
{
    if ((k & ~2) == 0 && SCR[k >> 1]) {
        if (ev == 0 || ev == 3) SCR[k >> 1] = 0;
        k = 4 + (k >> 1);
    }
    return k;
}

/* Mixed key mode (mode 11) key handler (key table entry 11): wraps the stock handler. E/F = stock handler for
 * switch A/B with the current group set to group 2 for the call (they share A/B's "alternate" toggle state). */
void __attribute__((section(".ef3"))) mix_wrap(int k, int ev)
{
    if (k < 6 && ef_cur()) {
        k = alias(k, ev);
        if (k >= 4) { MIXPAGE = 1; k -= 4; }
        mix_key(k, ev);
        MIXPAGE = 0;
        return;
    }
    mix_key(k, ev);
}

/* Custom keyboard mode (mode 10) key handler (key table entry 10), replaces stock 0x1e135b4..0x1e1369e.
 * Press: HID report from customKey[group][k] = {mod1, mod2, key} (codes via table 0x1e18e0c), display "---";
 * release: all keys up, display "N4<group>"; E/F (groups on): group down/up over 6 groups + save timer.
 * E/F on: one group; E/F = customKey[1][0..1] == customKey[0][4..5]. */
void __attribute__((section(".ef2"))) kb10_key(int k, int ev)
{
    u8 rep[8] = {0};
    u8 g = HIDPAGE;
    if (k > 5) return;
    if (CFG[0] & 1) {
        k = alias(k, ev);
        g = HIDPAGE = 0;
    } else if (k >= 4) {
        if (k == 4) g = g ? g - 1 : 5;
        else g = g >= 5 ? 0 : g + 1;
        HIDPAGE = g;
        disp3('N', '4', '1' + g, 0);
        SAVE_TIMER = 0xfa;
        return;
    }
    if (ev == 1) {
        volatile u8 *p = SET + 0x347d + g * 12 + k * 3;
        rep[0] = HIDKEY[p[0]] | HIDKEY[p[1]];
        rep[2] = HIDKEY[p[2]];
        DISPLAY = 0x101010;
        RAM193[0x15] = 0;
        RAM193[0x16] = 0;
    } else if (ev == 0 || ev == 3) {
        disp3('N', '4', '1' + g, 0);
    } else return;
    hid_send(3, rep, 8);
}

/* power-on mode selection: replaces greet()'s call of vbat_percent (switches are read ~2.4 s after power-on,
 * the greeting then shows the new mode number) */
int __attribute__((section(".ef3"))) boot_sel(void)
{
    for (int i = 0; i < 4; i++) {
        if (!gpio_read(PINS[i])) {
            u8 m = CFG[1 + i];
            if (m && m <= 13) MODE = m - 1;
            break;
        }
    }
    return vbat_percent();
}

/* Advanced custom mode (mode 3) key handler (key table entry 3) */
void __attribute__((section(".ef"))) m3_key(int k, int ev)
{
    volatile u8 *tog, *lng;
    if (k > 5) { if (k == 0x80) pedal(ev); return; }
    if (BANKMAX == 0) {
        k = alias(k, ev);
        BANK = 0;
        if (k >= 4) { tog = SCR - 2 + k; lng = SCR + k; goto send; }
    } else if (k >= 4) {                             /* E/F: group down/up */
        u8 b = BANK;
        if (k == 4) b = b ? b - 1 : BANKMAX;
        else b = b >= BANKMAX ? 0 : b + 1;
        BANK = b;
        SHOWN = b + 1;
        bank_now();
        return;
    }
    tog = (volatile u8 *)0x193cb + k;
    lng = (volatile u8 *)0x193bd + k;
send:
    adv_send(SET + 0x5d + (BANK * 4 + k) * 0x1a1, tog, lng, ev, k);
}

/* Video (6), Keyboard A (7), Keyboard B (8) key handler (key table entries 6..8), replaces the three identical
 * stock handlers 0x1e13436 / 0x1e13492 / 0x1e134ee. Press: HID key from the mode's 4-byte table (video 0x1e19304,
 * A 0x1e19300, B 0x1e192fc), display "---"; release: all keys up, display "AUD" / "N10" / "N20". */
void __attribute__((section(".ef3"))) fix_key(int k, int ev)
{
    u8 rep[8] = {0};
    unsigned m = MODE;
    if (k > 3) return;
    if (ev == 1) {
        DISPLAY = 0x101010;
        RAM193[0x15] = 0;
        RAM193[0x16] = 0;
        rep[2] = ((const u8 *)0x1e1931c)[k - 4 * (int)m];
    } else if (ev == 0 || ev == 3) {
        if (m == 6) disp3('A', 'U', 'D', 0);
        else disp3('N', '1' + m - 7, '0', 0);
    } else return;
    hid_send(3, rep, 8);
}
