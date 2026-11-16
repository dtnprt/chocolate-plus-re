#!/bin/bash
# Compile ef.c + patch.s with the JieLi pi32v2 toolchain (Linux x86-64, run in Docker) and build the firmware.
#
#   TOOLCHAIN=/path/to/jieli-linux-toolchains-... ./build.sh /path/to/FootCtrlPlus_012.fwsc [outdir]
#
# TOOLCHAIN (folder with pi32v2/ and common/) is mounted read-only into the container.
set -e
cd "$(dirname "$0")"
STOCK=${1:?usage: TOOLCHAIN=... $0 FootCtrlPlus_012.fwsc [outdir]}
OUT=${2:-out}
: "${TOOLCHAIN:?set TOOLCHAIN to the extracted JieLi toolchain (the folder containing pi32v2/ and common/)}"
TOOLCHAIN=$(cd "$TOOLCHAIN" && pwd)
docker run --rm --platform linux/amd64 -v "$PWD":/ef -v "$TOOLCHAIN":/tc:ro -w /ef ubuntu:22.04 bash -c '
  set -e; TC=/tc/pi32v2/bin
  $TC/clang -target pi32v2 -Os -ffreestanding -fno-builtin -c ef.c -o ef.o
  $TC/clang -target pi32v2 -c patch.s -o patch.o
  $TC/ld -T ef.ld ef.o patch.o -o ef.elf
  $TC/nm -n ef.elf | grep -E " [Tt] " > ef.syms
  for s in hook combo ef ef2 ef3; do $TC/objcopy -O binary -j .$s ef.elf sec_$s.bin; done
  $TC/objdump -d -print-imm-hex ef.elf > ef.dis'
mkdir -p "$OUT"
python3 -I ef_build.py "$STOCK" -o "$OUT" --extras
