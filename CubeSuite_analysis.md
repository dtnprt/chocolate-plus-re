# CubeSuite.apk – analysis

Package `com.cubeSuite`, versionCode `20260511031149`, minSdk 15. Not obfuscated.
- Raw APK contents: `../third-party/apps/CubeSuite_extracted/`
- Java sources (jadx 1.5.6): `../third-party/apps/CubeSuite_decompiled/sources/com/cubeSuite/` (74 methods failed to decompile cleanly; none in the protocol code)

## Supported devices (one `communication/*Communication` class each)
FootCtrl / FootControl2 (FC2), CubeTurner, Looper, LooperDrum, IRBox, SMC Mixer,
SMC Pad, SMK25 II, SMK25 Mini, MIDI keyboard.
Device-type → UI (`bluetooth/BleHandle.java`): 19, 30, 45 → `FC2Fragment`; 31 → `FootCtrlControlFragment`.

## BLE (`config/BleEnum`, `utils/JL_Constant`)
| Purpose | Service | Write | Notify |
|---|---|---|---|
| Sinco control protocol | `0000ae40-…` | `ae41` | `ae42` |
| Jieli OTA | `0000ae00-…` | `ae01` | `ae02` |
| FW version | `180A` (Device Info) | – | `2A26` (read) |

`BLE_MTU_MAX = 203`. Classic: SPP `1101`, A2DP `110b`.

## Control protocol (`communication/Communication.java`) – confirmed
All multi-byte fields little-endian.

```
00 59 | cmd | len(u24) | payload ... | checksum
```
- `len` = payload length (bytes after the 6-byte header, excluding checksum)
- `checksum` = `~(sum of payload bytes) & 0xFF` (sum starts at offset 6)

| cmd | meaning | payload |
|---|---|---|
| `0x11` | query name+version | – (reply `"NAME_VVV..."`, split on `_`) |
| `0x12` | short msg / other info | – |
| `0x13` | firmware version | – |
| `0x15` | MIDI write | raw MIDI bytes |
| `0x17` | device type | – |
| `0x1B` | sound data addr | – |
| `0x20` | codec value | – |
| `0x21` | erase | `type(u8) addr(u32)` (len 5) |
| `0x22` | write | `type(u8) addr(u32) n(u24) data[n]` |
| `0x23` | read | `type(u8) addr(u32) n(u24)` (len 8) |

Memory type: NOR=0, NAND=1, SD=2, EFF=3, **DEV=4** (config, default), USR=5, **RAM=6**, RSV2=7.
Reply parsing: `getAllLen` = bytes 3..5, `getAddr` = bytes 7..10, `getLen` = bytes 11..13.
Large transfers are chunked by `CommunicationUtil.splitReadData/splitWriteData`.

## FootCtrl v1 – `FootCtrlCommunication.java`
- `readFootCtrlData` → read DEV @ `ADDRESS_BASE`, 1000 bytes → native `dataToFootCtrlEntry`.
- Bluetooth-pedal mode: read 13 bytes @ base; channel/toggle at `2*i+2` / `2*i+3`; writes at 1 and 12.
- Other field offsets come from native `libGetOffset.so` (`getFootCtrlAddr(name)`, strcmp chain).
  Disassembled (arm64, capstone) → `../third-party/apps/CubeSuite_native/libGetOffset_arm64.asm`.

### FootCtrl v1 struct (`getFootCtrlSize` = 0x742 = 1858 bytes)
| Offset | Size | Field |
|---|---|---|
| 0x000 | 1 | state |
| 0x001 | 1 | usrchan |
| 0x002 | 10 | usr[5] (u16 LE each) |
| 0x00C | 1 | trsmidi |
| 0x00D | 161 | customData1 |
| 0x0AE | 161 | customData2 |
| 0x14F | 161 | customData3 |
| 0x1F0 | 161 | customData4 |
| 0x291 | 161 | customData5 |
| 0x332 | 4×128 | sysExA[0..3] (`0x332 + 128*i`) |
| 0x532 | 4×128 | sysExB[0..3] (`0x532 + 128*i`) |
| 0x732 | 16 | customKeyboard (app writes 4-byte entries at `+4*i`) |

`getFootCtrlAddr` returns 0 for unknown names (so "state" and typos both map to 0).

`CustomData` (161 bytes): `mode(1)` + `midiCodeA[16]` (5 B each, @+1) + `midiCodeB[16]` (5 B each, @+0x51).
`MidiCode` (5 bytes): isEnable, channel, type, data1, data2.

`dataToFootCtrlEntry` builds
`FootCtrlEntry(byte state, byte usrchan, int[5] usr, byte trsmidi, CustomData[5], byte[4][128] sysExA, byte[4][128] sysExB, byte[16] customKeyboard)`.

### CubeTurner (`getCubeTurnerStructSize` = 14 bytes)
software @0, hardware @1, state @2, usr @4, usrchan @12.

## FootControl2 – `entity/fc2/FC2Struct.java` – confirmed layout
Read as DEV (type 4) @ addr 0, **23646 (0x5C5E) bytes** (`FC2Fragment.java:729`).

`MidiCode` = 5 bytes: isEnable, channel, type, data1, data2
`AdvCustom` = 417 bytes: mode(1) + midiCodeA[16]×5 + midiCodeB[16]×5 + sysExA[128] + sysExB[128]

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | state (0..12) |
| 1 | 1 | trs (0..1) |
| 2 | 1 | ch (0..16) |
| 3 | 10 | usr[5][2] |
| 13 | 80 | midiCodeTap[16] (MidiCode) |
| 93 | 13344 | advCustom1[8][4] (AdvCustom) |
| 13437 | 72 | customKey[6][4][3] |
| 13509 | 10128 | mixKey[6][4], 422 B each: type, tunerdat, hidkeydat[3], midiUsrPlus (AdvCustom) |
| 23637 | 3 | bankMax[3] |
| 23640 | 1 | usrpage |
| 23641 | 1 | hidpage |
| 23642 | 1 | polar |
| 23643 | 1 | bankMidi |
| 23644 | 1 | pcdisp |
| 23645 | 1 | mixpage |

## Firmware / network (plain HTTP)
- On start, `StartActivity` fetches the directory listing `http://47.107.244.214:7080/resources/APP/Firmware/`,
  parses `<a>` links ending in `ufw` named `NAME_NNN.ufw` → `firmwareListMap[NAME] = NNN`.
- `BleHandle.getFirmwareFullUrl(name)` → `…/Firmware/<name>_<NNN>.ufw`
  (same naming as `FootCtrlPlus_012.ufw`). Saved locally as `OTAFile.ufw`, flashed via Jieli OTA (`ae00`).
- App update: `…/APP/App/UpdateInfo.json`, `…/APP/App/CubeSuite.apk`. Manuals: `…/resources/Pdf/`.

## Next steps
1. Look for the FC2 23646-byte default config inside `FootCtrlPlus_012` / `fw_extract/`.
