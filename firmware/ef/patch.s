// A+B / C+D combo detection, replaces stock 0x1e11f34..0x1e11f82 (78 bytes) in the 5 ms poll 0x1e11cf2.
// In: r14 = 0x193a0 (switch [count,state] pairs at +0x1ee: A,B,C,D), r9 = mode key handler.
// Stock: both switches pending (0x64) -> both states = 4 (ignored until released), handler(4|5, 0).
// E/F on in the current mode (ef_cur, see ef.c): only the second switch is consumed; the first stays pending and
// runs through the normal state machine (press / long / release), flagged in SCR (0x16907 + 0|1) so the mode's
// key handler reports E/F. Out: r4 = r14 + 0x1f3 (expected by the following stock code).
    .section .combo,"ax"
    r4 = r14 + 0x1ef
    r5 = 0x4
L_pair:
    r0 = b[r4+0x0] (u)
    if (r0 != 0x64) goto L_next
    r0 = b[r4+0x2] (u)
    if (r0 != 0x64) goto L_next
    r0 = 0x4
    b[r4+0x2] = r0
    call ef_cur                 // clobbers r0/r1 only
    if (r0 == 0x0) goto L_stock
    r0 = 0x1
    r2 = 0x16903
    r2 += r5
    b[r2+0x0] = r0
    goto L_next
L_stock:
    r0 = 0x4
    b[r4+0x0] = r0
    r0 = r5
    r1 = 0x0
    call r9
L_next:
    r4 += 0x4
    r5 += 0x1
    if (r5 != 0x6) goto L_pair
    r4 += -0x4

// boot greeting (142 cave D): `call vbat_percent` -> boot_sel (power-on mode selection, then vbat_percent)
    .section .hook,"ax"
    call boot_sel
