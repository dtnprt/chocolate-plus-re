#!/bin/bash
TC="${JL_TOOLCHAIN:-$HOME/jltc/jieli-linux-toolchains-20260730.1}/pi32v2/bin"   # override with JL_TOOLCHAIN=<toolchain root>
for v in INSTANT BALANCED; do
  echo "== $v"
  $TC/objdump -d -print-imm-hex $v.elf > $v.dis
  grep -E '^ *(1e11ffe|1e12000|1e12002|1e12006|1e12034|1e12090|1e26088|1e2608c|1e26092|1e26096|1e2609c|1e2609e|1e260a0):' $v.dis
done
