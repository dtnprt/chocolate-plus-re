#!/bin/bash
TC="${JL_TOOLCHAIN:-$HOME/jltc/jieli-linux-toolchains-20260730.1}/pi32v2/bin"   # override with JL_TOOLCHAIN=<toolchain root>
cd "$(dirname "$0")"
$TC/clang -target pi32v2 -c greet.s -o greet.o && $TC/ld -T greet.ld greet.o -o greet.elf && $TC/objdump -d -print-imm-hex greet.elf && $TC/objdump -h greet.elf
