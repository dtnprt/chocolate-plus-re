# FootCtrlPlus custom firmware build

Everything needed to rebuild the custom firmware from the stock image.

```
build.py          patches the original firmware 012 (checked by SHA-256) and writes FootCtrlPlus_142-dtnprt.fwsc
fwsctool.py       .fwsc/.ufw container, LFSR member cipher, CRC16 (imported by build.py)
FootCtrlPlus_012.fwsc (or the .ufw inside it) - original M-VAVE firmware, the build input (vendor, not in git):
                  https://www.cuvave.com/product?id=chocolate-plus
patch_src/        cave.s + link.ld      - source of the 24-byte tap-fix code cave (pi32v2 asm)
                  greet.s + greet.ld    - boot greeting; asm_greet.sh assembles it (bytes are embedded in build.py)
                  dis.sh                - objdump check of patched images (WSL JieLi toolchain)
                  JieLi toolchain 2.5.3 (Linux/WSL): https://pkgman.jieliapp.com/s/linux-toolchain, unpack to ~/jltc/
                  (or set JL_TOOLCHAIN); guide: https://dtnprt.github.io/chocolate/firmware/build/
../../third-party/firmware_reference/  correct decryption of the stock app area (vendor code, not in git):
                  app_area_decrypted.bin (offset 0 = vaddr 0x01e00000), app_code.elf (ET_EXEC @0x01e00120),
                  app_disasm.txt (objdump), app_decompiled.c (Ghidra pseudo-C), app_strings.txt, func_targets.txt
```

## Build
```
python build.py FootCtrlPlus_012.fwsc              # -> ./FootCtrlPlus_142-dtnprt.fwsc
python build.py FootCtrlPlus_012.fwsc -o <folder>  # other output folder
python build.py FootCtrlPlus_012.fwsc --extras     # also the .ufw and the decrypted app area (_app.bin)
python build.py FootCtrlPlus_012.fwsc --rev-file REVISION   # dev build: FootCtrlPlus_142-dtnprt-<n>.fwsc, n counted up in REVISION
```
The input is checked first: only the original firmware 012 is accepted (`FootCtrlPlus_012.fwsc` SHA-256
`9deb9d90691415aa7f4514103842237a1500c681db34fe35e5f5136d173cb3bc`, or the `.ufw` inside it). Other versions,
damaged downloads and already patched files are refused with an explanation.
Further self-checks on every run: stock CRCs must verify, the app-area CRC chain must reproduce the stock values,
every patch site must contain the expected original bytes. The result is compared with the official build
(`FootCtrlPlus_142-dtnprt.fwsc` SHA-256 `eadd20b993b149753651f83a683d1af25fb4f966d340e0b269a33b300f2e3ba2`).
Step-by-step guide for users: https://dtnprt.github.io/chocolate/firmware/#build

## What it patches (in both flash.bin and flash2.bin)
| Patch | Where | Stock | Custom |
|---|---|---|---|
| Footswitch debounce | `if (r1 < 4)` @ 0x1e12034 | 4 ticks | 3 ticks (5 ms tick) |
| Pending/combo window | `if (r1 < 0xf)` @ 0x1e12090 | 15 ticks | 6 ticks |
| Short taps not dropped | `call 0x1e26088` @ 0x1e12002 + 24 B cave in 0xff padding | taps < ~95 ms lost | press + release sent |
| Name/version reply | 27-byte slot @ 0x1e18c8e | `FootCtrlPlus_014-dtnprt` replaces `FootCtrlPlus_012` | |
| Boot greeting | hook @ 0x1e144ca (`call show_screen`) → `greet` (patch_src/greet.s) | normal screen | `   ` `Uer` `142` `bAt` ` NN` `nod` `  N` (0.6 s each); set `FRAMES`/`MODE_KEY` in build.py |
| Status LED (PA0) dimmed | 20 ms LED timer 'on' @ 0x1e129ee → `led_on` (OUT only); 5 ms display timer digit store @ 0x1e11d78 → `led_pwm` | on = output high | PA0 output only in digit slot 0 → 1/3 duty at ~67 Hz |
| Advanced custom (mode 3) screen | 2 sites @ 0x1e13064 / 0x1e13370 → `bank_sw` (font entry `x` = `-`) | `0xy` (2-digit bank, switch A–D) | `x-z` (bank, `-`, switch 1–4) |
| Start screen blank | mode 2/3 screen fns @ 0x1e13a84 / 0x1e13aa0 | `000` | blank (first greeting frame no longer overwritten) |
| Fixes for not-free caves | `call` @ 0x1e15b06 → nop; imm @ 0x1e1cc26 → 0x1e00100; 0x1e11b06 left stock | – | see below |

Press latency: ~95 ms stock, ~45 ms custom. A+B / C+D combos still work (30 ms window).

## Cipher and checksums
- App area = `member_decrypt(flash.bin[0x1000:], key=0x180f, pos=0x20000)` (32-byte LFSR blocks).
- Inside the app area: app.bin entry @0x20 (head CRC over [0x22:0x40], data CRC over the code) and
  app_area_head @0x00 (head CRC over [2:0x20], data CRC over [0x20:area_len]). build.py rebuilds the chain.
- Then: member CRC in the .ufw directory entry, table CRC and header CRC (`fix_header_crc`), `.fwsc` wrap.

## Flashing / recovery
Flash the built `.fwsc` with SincoOTA (Android). Stock recovery: the original `FootCtrlPlus_012.fwsc` with SincoOTA.
If the pedal is stuck in update/download mode: SincoOTA → *Mandatory upgrade*.

## Display internals (for further changes)
- 3 digits, segment byte per digit: a=bit6 b=bit3 c=bit2 d=bit0 e=bit1 f=bit7 g=bit4 DP=bit5.
- Display content = u32 @ 0x193a0+0xf4 (left digit in bits 16-23); refreshed by the 5 ms poll 0x1e11cf2
  via 74HC164 (data GPIO 0x16, clock 0x15) and digit-select GPIOs.
- `disp3(c0, c1, c2, r3=0)` @ 0x1e122f6 shows 3 ASCII chars. Font: digits @ 0x1e189df, letters @ 0x1e18c74
  (upper/lower case share one table; K M V W X Z are blank).
- `vbat_percent()` @ 0x1e0e4a0 returns 0..100 (linear up to 4.20 V).
- Code caves used: 0x1e00406 (104 B: greet + show_num), 0x1e19308 (32 B: text table + bank_sw), 0x1e26088 (40 B 0xff: tap fix + show), leftovers of the two patched mode-3
  screen blocks (LED routines).
- Status LED: PA0 (port A base 0x1e5000: OUT +0, IN +4, DIR +8 (1 = input), PU +0x10, PD +0x14), driven by the 20 ms timer
  0x1e12970 (blink 400 ms / steady). It is off while byte 0x13490+0x5c63 is set = Bluetooth off: stock B+C hold ~2 s
  toggles it (0x1e1271e Bluetooth off, 0x1e12706 back on). RAM only, not part of the saved settings.
- NEVER use 0x1e04a84 as a cave: it is the BLE pairing-record function, reached indirectly when a bond is stored
  (v4 used it -> pedal crashed/disconnected on pairing).
- 0x1e00406 is NOT unreferenced: it is stock usr_timer_modify(id, 1000 ms), called by the LRC trim timer 0x1e15a40
  (`call` @0x1e15b06, runs in the timer interrupt). 141 left that call in place, so greet() ran inside the ISR
  ~200 ms after boot. Since 142 the call is nop'ed (LRC trim stays at its 10 ms period).
- 0x1e11b06 is NOT free (cave A up to 141): it is the stock USB EP0 IN data-stage handler (copies up to 64 bytes
  to the EP0 buffer, writes JL_USB->EP0_CNT 0x1e1808), reached via a function pointer. Overwriting it broke USB
  enumeration (no 'SINCO' USB-MIDI device). Since 142 it is stock again.
- 0x1e19308 is NOT free padding: the BLE link scheduler 0x1e1cc1c copies it as an 8 x 0xffffffff initializer.
  Since 142 its `r1 = 0x1e19308` @0x1e1cc24 points to 0x1e00100 (empty flash-directory slot, 32 B 0xff) instead.
- Lesson: "no call/pointer found" is not proof that code is free (see also 0x1e04a84). Check every branch target
  in app_disasm.txt, including annotations on the line after a `call` inside an if-block.
