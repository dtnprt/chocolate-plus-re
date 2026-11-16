# 152-ef: E/F switches + power-on mode selection

Built on top of dtnprt's custom firmware 142 (`../build.py` runs unmodified, then these patches are applied).

## Features

- **E / F switches**: A+B and C+D act as two independent switches with every option the other switches have.
  - Advanced custom (mode 3): on when "Max group count" = 1.
  - Custom keyboard (mode 10) and Mixed key (mode 11): Web Config checkbox (CFG bits 0 / 1). This turns groups off.
- **Power-on mode**: hold A, B, C or D while powering on to switch to the mode mapped in Web Config.
  The setting is saved, so the new mode stays after the next power-on.
- **USB configuration**: the stock control protocol over USB-MIDI SysEx. This is a Web Config change only (`../../webconfig/`).

## Build

```
TOOLCHAIN=/path/to/jieli-linux-toolchains-XXXXXXXX ./build.sh /path/to/FootCtrlPlus_012.fwsc [outdir]
```

This needs Docker (the JieLi toolchain is Linux x86-64) and Python 3. The output is `out/FootCtrlPlus_152-ef.fwsc`
(SHA-256 `fbee20e05493b7e3cfa48223ebb4376a445b3b9825339f5e7cbce30c7fb8c528`). Flash it with SincoOTA, and don't rename the file.

## Patch map

| Where | What |
|---|---|
| 0x1e00426 | greet(): `call vbat_percent` → `boot_sel` (reads A–D, applies the mapped mode) |
| 0x1e11f34 | combo detection: with E/F on, flags the pair instead of sending the stock combo event |
| 0x1e13268 | mode 3 handler `m3_key` + `ef_cur` / `alias` |
| 0x1e13436 | merged mode 6/7/8 handler `fix_key`, mode 11 wrapper `mix_wrap`, `boot_sel` |
| 0x1e135b4 | mode 10 handler `kb10_key` (rewritten in C to make room) |
| 0x1e18da4 | key handler table entries 3, 6, 7, 8, 10, 11 |

CFG lives in settings offset 13425 (bytes 116..121 of the group 8 / D / SysEx B buffer, which the Web Config caps
at 115 bytes). Bytes 122..127 are runtime scratch. Each patch region is checked against the SHA-256 of the 142 bytes before it is written.
