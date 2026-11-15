ENTRY(ch_boundary_glue)
native_output_callback = 0x194a0;
native_packet_return = 0x1e1004c;
native_packet_continue = 0x1e0ff58;
SECTIONS {
  .patch 0x1e265f0 : ALIGN(4) { *(.text*) *(.rodata*) }
  .hook_boundary 0x1e0ff54 : { *(.hook_boundary) }
  ASSERT(SIZEOF(.hook_boundary) == 4, "Boundary hook size")
  ASSERT(SIZEOF(.patch) <= 0x100, "Unexpected boundary extension size")
  .unexpected : { *(.data*) *(.bss*) *(COMMON) }
  ASSERT(SIZEOF(.unexpected) == 0, "No added static RAM is permitted")
  /DISCARD/ : { *(.comment) *(.note*) *(.debug*) *(.llvm*) }
}
