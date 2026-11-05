    .section .p1,"ax"
    .globl _p1
_p1:
    call cave
    .section .cave,"ax"
    .globl cave
cave:
    if (r0 == 0x1) goto L_rts
    r2 = 0x1e1203e
    if (r0 != 0x64) goto L_go
    r2 = 0x1e12088
L_go:
    goto r2
L_rts:
    rts
