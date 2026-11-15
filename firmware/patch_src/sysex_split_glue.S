.section .text.glue,"ax",@progbits
.global ch_boundary_glue

ch_boundary_glue:
    r0 = r8
    r1 = r7
    r8 += r7
    r5 += r7
    call ch_host_boundary
    if (r0 == 0) goto boundary_continue
    goto native_packet_return
boundary_continue:
    goto native_packet_continue

.section .hook_boundary,"ax",@progbits
    goto ch_boundary_glue
