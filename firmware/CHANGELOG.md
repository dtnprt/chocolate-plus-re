# FootCtrlPlus custom firmware – Changelog

Base: stock M-VAVE **FootCtrlPlus 012** (Android build, JieLi AC636N).
Current: **FootCtrlPlus 142-dtnprt** (version 14, build 2) → `FootCtrlPlus_142-dtnprt.fwsc`, built with `build.py` from the original 012 (flash with SincoOTA).

Version scheme: `<version><build>` as 3 digits, e.g. `142` = version 14, build 2. It appears on the display,
in the name/version reply and in the `.fwsc` metadata.

All changes are binary patches applied by `build.py` to the stock image, in both firmware copies
(`flash.bin` and the OTA copy `flash2.bin`), with every checksum rebuilt.

---

## 142 (version 14, build 2) – current

### Fix: USB-MIDI not detected (bug since the first greeting builds, still in 141)
- In stock firmware the pedal shows up on the computer as the USB-MIDI device `SINCO`. Custom builds up to 141 did not.
- **Cause:** places used as free space for the patches are in use by the stock firmware:
  - `0x1e11b06` is the stock USB function that sends the replies (descriptors) to the computer while the device
    is being detected. It is only reached through a pointer, so it looked unused. The bank screen code was put there
    (since 014 + greeting v2), so the computer never got an answer. Now it is stock again.
  - `0x1e00406` is a stock timer function. The LRC clock-trim timer calls it from its interrupt about 200 ms after boot.
    In 141 that call ran the greeting inside the timer interrupt. Now the call is removed, and the trim timer keeps
    running every 10 ms instead of switching to 1 s.
  - `0x1e19308` (the greeting text) is a block of 0xff that the Bluetooth link scheduler copies as start values.
    In 141 it got the greeting text instead. The scheduler now reads another 32-byte 0xff block (`0x1e00100`).
- **Boot greeting shorter:** no `dtnPrt` any more (that also made room for the fix). It now starts with a blank screen,
  then `Uer` `142` `bAt` ` NN` `nod` `  N` (0.6 s each).
- **No `000` at power-on.** In modes 2 and 3 the stock firmware writes `000` to the display about 5 ms after power-on
  (and when switching to these modes). That overwrote the first greeting frame. It is blank now. In mode 2 the stock
  `000` after a footswitch release is unchanged.
- The `-` of the bank screen now comes from the font: the blank `x` entry was changed to `-`. Stock never shows an `x`.
- Everything else is the same as 141.

## 141 (version 14, build 1)

### Footswitches
- **Faster response.** A press now registers after about **40–45 ms** instead of about **95 ms**.
  - Debounce: 4 → 3 checks of 5 ms each.
  - Two-switch window: 15 → 6 checks of 5 ms each.
- **Short taps no longer get lost.** Stock firmware silently dropped any tap shorter than about 95 ms.
  Every tap now sends a press and a release.
- **Combos still work.** A+B and C+D two-switch combos still work, with a 30 ms window to press both switches.

### Boot greeting (display)
Shown on power-on, then the normal screen:

| Step | Display | Time |
|---|---|---|
| Scrolling text | `dtnPrt` slides in from the right and out to the left | 0.25 s per step |
| Version | `Uer` → `141` | 0.6 s each |
| Battery | `bAt` → ` 85` (percent, `100` when full) | 0.6 s each |
| Mode | `nod` → `  3` (current mode, 0-based; 3 = advanced custom) | 0.6 s each |

- **Font limits:** a 7-segment display has no K, M, V, W, X or Z. `U` stands in for V and `n` for M. B and T show as `b` and `t`.
- **Settings:** text, frames and mode key are set in `build.py` (`SCROLL`, `FRAMES`, `MODE_KEY`).

### Advanced custom mode (mode 3)
- **New bank/switch screen.** It shows `x-z` (bank, dash, switch 1–4), e.g. `2-3` for bank 2, switch C.
  The stock screen showed `0xy` (2-digit bank, switch letter), e.g. `02C`.
- **Bank screen right after boot.** In mode 3 the greeting ends on the bank screen (current bank and the last
  used switch), instead of leaving the mode number on the display until the first switch press.

### Bank number fix (stock bug)
- **Bank-down after boot fixed.** In stock firmware the shown bank started at `0` after power-on, and
  bank-down from there jumped to an invalid bank ("-1", actually 255) instead of the last bank.
  It only came back into range after wrapping past the last bank once.
- **Cause:** the shown bank was counted ±1 from its own value, separately from the real (saved) bank index.
- **Now:** the shown bank always follows the real index, so bank up/down wraps correctly between 1 and the
  last bank right after boot. The selected presets were always correct; only the number was wrong.

### Status LED
- **Dimmed by PWM.** The LED is pulsed in step with the display refresh: it's driven during one of the three
  digit slots of the 5 ms display timer, i.e. on 1/3 of the time at about 67 Hz, the same rate as the display.
  Blinking and timing are unchanged. (A first attempt via the internal pull-up was too weak: the LED stayed dark.)
- **Stock B+C combo (unchanged):** holding B+C for about 2 s switches **Bluetooth** off and on.
  The LED stays dark while Bluetooth is off. It is not an LED-off switch.

### Identification
- **New name/version reply:** the pedal reports `FootCtrlPlus_142-dtnprt` instead of `FootCtrlPlus_012`.
  - CubeSuite shows it as version `142`.
  - The web config page shows the full `142-dtnprt`.
- **Bluetooth name unchanged (`FootCtrlPlus`), on purpose.** SincoOTA and CubeSuite only find the pedal by that exact
  name. Renaming it would make SincoOTA unable to flash it, including in update mode.

---

## History

| Version | Changes |
|---|---|
| 013-CUSTOM | First test build: only the Bluetooth version string changed. Proved the decrypt, patch, re-checksum and flash pipeline. |
| 014 | Faster footswitches and short-tap fix (BALANCED variant; the INSTANT variant was dropped). Name/version reply `FootCtrlPlus_014-dtnprt`. |
| 014 + greeting v1 | Boot greeting `dtn`, `Prt`, `014`, battery. First frame stayed dark after power-on. |
| 014 + greeting v2 | `Uer`/`bAt` key/value frames, 0.4 s each. |
| 014 + greeting v3 | `dtnPrt` scrolls right to left. |
| 014 + greeting v4 | Mode key/value (`nod` + number). Advanced custom screen `x-z`. **Bug:** the pedal crashed when a Bluetooth pairing was stored, because a pairing function had been reused as code space. |
| 014 + LED dim (v5) | Pairing bug fixed (that function left untouched). Status LED dimmed. |
| 015 | Version 15. Longer display times: scroll 0.2 → 0.25 s per step, values 0.4 → 0.6 s. Bank number fix (stock bug: shown bank 0 / "-1" after boot). Mode 3 shows the bank screen right after the greeting. |
| 141 | New version scheme (version 14, build 1); file `FootCtrlPlus_141-dtnprt.fwsc`. First finished release. **Bug:** USB-MIDI not detected (stock USB function at 0x1e11b06 overwritten; also: greeting ran in the LRC trim timer interrupt, BLE scheduler start values overwritten). |
| **142** | USB fix: 0x1e11b06 stock again, the stock timer call and the BLE start values are fixed. Greeting without `dtnPrt`. |

---

## Known limits and notes
- **Updating:** use SincoOTA (Bluetooth), with the pedal **not paired** to the phone.
  If it's left in update mode, use SincoOTA's *Mandatory upgrade*.
- **Recovery:** flash the original `FootCtrlPlus_012.fwsc` (M-VAVE download) with SincoOTA.
- **Web Bluetooth flasher** (private, not in this repo): auth and phase 1 work. Reconnecting for phase 2 from Windows is unreliable, so use SincoOTA.
- **Flash space is almost full.** Only unreferenced functions and 0xff padding are used for new code.
  `0x1e04a84` must never be reused (pairing records). `0x1e11b06` (USB), `0x1e00406` and `0x1e19308` were not free either (fixed in 142).
  Not finding a reference does not prove a location is free.
