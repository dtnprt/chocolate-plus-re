#!/usr/bin/env bash
# Offline only. JL_TOOLCHAIN is the extracted JieLi Linux toolchain root.
set -euo pipefail
study=$(cd -- "$(dirname -- "$0")" && pwd)
out="$study/../out/sysex-split-143"
tc=${JL_TOOLCHAIN:?Set JL_TOOLCHAIN to the JieLi toolchain root}
mkdir -p "$out"
cd "$study"
cc -std=c99 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -fno-omit-frame-pointer sysex_split.c test_sysex_split.c -o "$out/test-sysex-split"
"$out/test-sysex-split"
"$tc/pi32v2/bin/cc" -mcpu=r3 -std=c99 -Oz -Wall -Wextra -Werror \
  -ffreestanding -fno-builtin -c sysex_split.c -o "$out/split.o"
"$tc/pi32v2/bin/cc" -mcpu=r3 -c sysex_split_glue.S -o "$out/glue.o"
"$tc/pi32v2/bin/cc" -mcpu=r3 -nostdlib -Wl,-T,sysex_split.ld \
  "$out/split.o" "$out/glue.o" -o "$out/sysex-split.elf"
"$tc/common/bin/objcopy" -O binary -j .patch "$out/sysex-split.elf" "$out/sysex-split.bin"
"$tc/common/bin/objcopy" -O binary -j .hook_boundary \
  "$out/sysex-split.elf" "$out/hook-boundary.bin"
"$tc/common/bin/objdump" --mcpu=r3 --address-mask=0x1ffffff -h -t -d \
  "$out/sysex-split.elf" > "$out/disassembly.txt"
"$tc/common/bin/objdump" --mcpu=r3 -h "$out/sysex-split.elf"
python3 - "$out" <<'PY'
import hashlib, json, sys
from pathlib import Path
names = ("sysex_split.c", "sysex_split.h", "sysex_split_glue.S", "sysex_split.ld",
         "test_sysex_split.c", "build_sysex_split.sh")
values = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in names}
(Path(sys.argv[1]) / "sources.json").write_text(json.dumps(values, indent=2) + "\n")
PY
