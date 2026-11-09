// FootCtrlPlus display/LED patches (pi32v2).
//
// IMPORTANT: "no reference found" does not mean free. Reached indirectly (function pointers) and NOT free:
//   0x1e04a84 BLE pairing-record function (v4 crashed on pairing), 0x1e11b06 USB EP0 IN handler (USB broken up
//   to 141). Only use the caves listed here.
//
// Boot greeting: replaces `call 0x1e1286a` (r0 = arg) in the app start routine at 0x1e144ca. Runs in the
// app task; the display keeps refreshing from the 5 ms hardware timer while we sleep.
//   1. frames of 3 chars (0.6 s each), e.g. "   " "Uer" "142" "bAt" (since 142 no scrolling and no "dtn" "Prt";
//      the first frame is blank: the first frame after power-on is not shown correctly)
//   3. battery percent " NN" / "100"
//   4. mode key (3 chars from the table, e.g. "nod") and the mode number " NN"
//   then the original call with the original argument (reloaded from 0x13491).
// Text table in cave B: <frames> 0 <mode key, 3 chars>   (patched by build.py)
//
// Advanced custom mode (mode 3) bank/switch screen: stock shows "0xy" (2-digit bank, switch letter A-D);
// both places that draw it call bank_sw(bank, sw) which shows "x-z" (bank digit, '-', switch 1-4).
// The rest of the two stock code blocks (now skipped) holds the LED routines.
//
// Status LED (PA0) dimmed by PWM: the 5 ms display timer cycles 3 digits; PA0 is an output only in digit slot 0
// and an input (LED dark) in slots 1 and 2 -> 1/3 duty at ~67 Hz. The 20 ms LED timer still decides on/off/blink
// via the OUT bit; its 'on' path no longer forces DIR = output.
//
// Firmware entry points used (defined in greet.ld):
//   disp3(c0, c1, c2, r3=0)  0x1e122f6   ASCII -> segments, left to right (space = blank)
//   vbat_percent()           0x1e0e4a0   0..100
//   orig_call(arg)           0x1e1286a   original call target at the hook (arg = byte 0x13491)
//   os_time_dly(ticks)       ROM 0x117d78 (call via 0x2117d78), 10 ms ticks
//   display word             0x19494 = 0x193a0+0xf4 (left digit bits 16-23, middle 8-15, right 0-7)
//   current mode             byte 0x13490 (3 = advanced custom)

    .section .hook,"ax"          // at 0x1e144ca (4 bytes, was: call 0x1e1286a)
    call greet

    .section .cave_d,"ax"        // at 0x1e00406, max 104 bytes (stock usr_timer_modify(id, 1000); its only caller
                                 // @0x1e15b06 in the LRC trim timer ISR is nop'ed by build.py since 142)
    .globl greet
greet:
    [--sp] = {rets, r6-r4}
    r6 = 0x13490                 // mode byte; +1 = argument of the original call
    r4 = texts
    r5 = 0x3c                    // 60 ticks = 0.6 s per frame
L_frame:                         // frames of 3 chars until a 0 byte
    r0 = b[r4+0x0] (u)
    r1 = b[r4+0x1] (u)
    r2 = b[r4+0x2] (u)
    call show
    r4 += 0x3
    r0 = b[r4+0x0] (u)
    if (r0 != 0x0) goto L_frame
    call vbat_percent            // battery percent 0..100
    call show_num
    r0 = b[r4+0x1] (u)           // mode key, e.g. "nod" (follows the frames terminator)
    r1 = b[r4+0x2] (u)
    r2 = b[r4+0x3] (u)
    call show
    r0 = b[r6+0x0] (u)           // current mode 0..12
    call show_num
    r0 = b[r6+0x0] (u)
    if (r0 != 0x3) goto L_end    // advanced custom mode: end on the bank screen
    call bank_now
L_end:
    r0 = b[r6+0x1] (u)           // original argument
    {rets, r6-r4} = [sp++]
    goto orig_call               // original call, returns to the app start routine

// show_num lives in cave D, bank_sw in cave B since 142. Up to 141 both were at 0x1e11b06, which is NOT free:
// it is the stock USB EP0 IN data-stage handler (sends the descriptors during enumeration, reached via a
// function pointer) -> USB was not detected. 0x1e11b06 is stock again.
show_num:                        // r0 = 0..199: show " NN" or "1NN" for r5 ticks
    r1 = 0xa
    r2 = r0 / r1 (u)             // tens (0..19)
    r3 = r2
    r3 *= r1
    r3 = r0 - r3                 // ones
    r0 = 0x20                    // ' '
    if (r2 < 0xa) goto L_num
    r0 = 0x31                    // '1'
    r2 += -0xa
L_num:
    r1 = r2 + 0x30
    r2 = r3 + 0x30
    goto show                    // tail call: returns to our caller

// Bank number fix (stock bug): the shown bank (byte 0x193a0+0x2a, 1-based) was only counted +-1 from its
// own value, while the real bank index (byte 0x190e8 = 0x13490+0x5c58, 0-based, saved) wraps correctly.
// After boot the shown bank is 0, so "bank down" gave 255. Now: shown bank = index + 1 everywhere.
    .section .site_a_bank,"ax"   // at 0x1e1305a..0x1e13082 (stock: r1 = shown bank; tens/ones/letter math; disp3)
    call bank_now                // mode 3 screen after a switch press
    goto site_a_end
led_on:                          // LED timer 'on': stock `[r0+0x0] |= 0x1` + `DIR = output`; keep only OUT = 1,
    [r0+0x0] |= 0x1              // the display timer (led_pwm) drives DIR
    goto led_on_ret
led_pwm:                         // replaces `b[r14+0x1b] = r1` (new digit index 0..2) in the 5 ms display timer
    b[r14+0x1b] = r1
    r0 = 0x1e5000                // PORTA (OUT +0, DIR +8)
    [r0+0x8] |= 0x1              // PA0 input: LED dark
    if (r1 != 0x0) goto L_pwm
    [r0+0x8] &= 0xFFFFFFFE       // digit slot 0: PA0 output -> LED shows OUT (on/off from the LED timer)
L_pwm:
    rts

    .section .bank_down_fix,"ax" // at 0x1e13322 (stock: r0 = r4 - 1, shown bank - 1), 4 bytes
    r0 = r3 + 0x1                // new shown bank = new index + 1
    nop
    .section .bank_up_fix,"ax"   // at 0x1e13346 (stock: r0 = r4 + 1, shown bank + 1), 2 bytes
    r0 = r3 + 0x1                // new shown bank = new index + 1

    .section .site_b,"ax"        // at 0x1e13370 (stock: same math after a bank change)
    r2 = r1                      // switch index
    r1 = r3                      // bank
    call bank_sw
    goto site_b_end
    .section .site_b_tail,"ax"   // at 0x1e1337c, 18 bytes of the stock block, now unreachable from stock code
bank_now:                        // show "x-z" for the current bank and switch (also used after the greeting)
    r3 = 0x190e8                 // bank index (0-based); +6 = current switch index (0..3)
    r1 = b[r3+0x0] (u)
    r2 = b[r3+0x6] (u)
    r1 += 0x1                    // -> bank 1..N
    goto bank_sw

    .section .site_led_on,"ax"   // at 0x1e129ee (stock: [r0+0x0] |= 0x1), 4 bytes
    goto led_on

    .section .site_pwm,"ax"      // at 0x1e11d78 (stock: b[r14+0x1b] = r1, display digit index), 4 bytes
    call led_pwm

    .section .cave_b,"ax"        // at 0x1e19308, max 32 bytes (stock: 0xff initializer of the BLE scheduler
                                 // 0x1e1cc1c; build.py re-points it to 0x1e00100 since 142)
texts:                           // max 16 bytes (build.py writes the real table), bank_sw follows
    .ascii "   Uer142bAt"
    .byte 0
    .ascii "nod"

    .section .cave_b2,"ax"       // at 0x1e19318, 16 bytes (rest of cave B)
bank_sw:                         // r1 = bank (1..6), r2 = switch index (0..3): show "x-z"
    r0 = r1 + 0x30
    r1 = 0x78                    // 'x': its font entry (blank in stock) is patched to '-' (segment g) by build.py
    r2 = r2.b0 (u)
    r2 += 0x31
    r3 = 0x0
    goto disp3                   // tail call

    .section .cave_c,"ax"        // at 0x1e260a0, 16 bytes (rest of the 0xff padding)
show:                            // disp3(r0, r1, r2), then sleep r5 ticks
    r3 = 0x0
    [--sp] = rets
    call disp3
    r0 = r5
    {rets} = [sp++]
    goto os_time_dly
