#!/usr/bin/env python3
"""
Build FootCtrlPlus firmware with fast footswitch response.

Root cause (stock 012, poll fn 0x1e11cf2, run every 5 ms via timer_add(fn,5)):
  per switch: state 0 (idle) --pressed D=4 consecutive ticks--> state 0x64 (pending, counter=0)
              pending --still pressed when counter>=F=15--> state 1, EVENT 1 (press)
              pending --released ... counter reaches 15--> back to idle, NO event (tap lost!)
  => press latency (4+15) ticks ~= 95 ms; taps shorter than that are dropped.
  The pending window exists so A+B / C+D pressed together can be detected as combos.

Patch:
  1) D  : imm of `if (r1 < 4)`   @ 0x1e12034  (debounce)
  2) F  : imm of `if (r1 < 0xf)` @ 0x1e12090  (pending/combo window)
  3) tap fix: @0x1e12002 `if (r0 != 1) goto 1e1203e` -> `call cave`; cave in the
     0xff padding at 0x1e26088 sends a pending switch that is RELEASED to the
     press path (1e12088) instead of the drop path, so short taps fire press+release.

Applied to both flash.bin (chunk 0) and flash2.bin (chunk 5, OTA bank: identical code).
CRC chain per bank: app.bin data/head CRC, app_area_head data/head CRC, ufw chunk CRC,
ufw table+header CRC.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # fwsctool.py lives next to this script
from fwsctool import xcode_block, crc16, member_decrypt, fwsc_wrap, fix_header_crc, decode_header

KEY, POS = 0x180f, 0x20000          # correct app-area cipher params
UBOOT = 0x1000                      # plaintext boot header in front of app area
VBASE = 0x01e00000                  # app-area offset 0 == this vaddr

def a(v): return v - VBASE          # vaddr -> app-area offset

def cmp_imm_patch(buf, vaddr, expect_imm, new_imm):
    """`if (rX < imm8) goto` : hw0 bit4 = imm bit7, hw1 bits 9..15 = imm bits 0..6."""
    o = a(vaddr)
    hw0, hw1 = struct.unpack_from('<HH', buf, o)
    imm = ((hw0 >> 4) & 1) << 7 | (hw1 >> 9)
    assert imm == expect_imm, f"{vaddr:#x}: imm {imm:#x} != {expect_imm:#x}"
    hw0 = (hw0 & ~0x10) | (((new_imm >> 7) & 1) << 4)
    hw1 = (hw1 & 0x1ff) | ((new_imm & 0x7f) << 9)
    struct.pack_into('<HH', buf, o, hw0, hw1)

CALL_CAVE   = bytes.fromhex('80ea41a0')                       # @1e12002: call 0x1e26088
CAVE        = bytes.fromhex('00f80902' 'c2ff3e20e101' '80f803c8' 'c2ff8820e101' 'd200' '8000')
CAVE_ADDR   = 0x1e26088

def rebuild_area_crcs(d):
    """app.bin entry @0x20, area head @0x00 (both: u16 head_crc, u16 data_crc, u32 addr, u32 len ...)."""
    app_addr, app_len = struct.unpack_from('<II', d, 0x24)
    struct.pack_into('<H', d, 0x22, crc16(d[app_addr:app_addr + app_len]))
    struct.pack_into('<H', d, 0x20, crc16(d[0x22:0x40]))
    area_len = struct.unpack_from('<I', d, 0x08)[0]
    struct.pack_into('<H', d, 0x02, crc16(d[0x20:area_len]))
    struct.pack_into('<H', d, 0x00, crc16(d[0x02:0x20]))

IDENT_ADDR = 0x1e18c8e                     # "FootCtrlPlus_012" + NUL pad (27-byte slot) = name/version reply
IDENT_SLOT = 27

# Display patches (source: patch_src/greet.s + greet.ld, assembled with patch_src/asm_greet.sh):
# - boot greeting: the app start routine's `call 0x1e1286a` @0x1e144ca -> greet(): scroll text (0.2 s/step),
#   3-char frames (0.4 s), battery percent, mode key + mode number, then the original call.
# - advanced custom mode (3): bank/switch screen "0xy" (bank, switch A-D) -> "x-z" (bank, '-', switch 1-4).
# - status LED (PA0) dimmed: 'on' = input with internal pull-up instead of output high.
# (address, exact stock bytes that must be there, new bytes)
# NEVER use 0x1e04a84 as a cave: it is the BLE pairing-record function, reached indirectly when a bond is
# stored (v4 used it and the pedal crashed/disconnected on pairing).
GREET = [
    (0x1e144ca, bytes.fromhex('bfeacef1'),  # hook: was `call 0x1e1286a`
     bytes.fromhex('bfea9c5f')),
    (0x1e00406, bytes.fromhex('7904041680ea274a4520bfeadafe0816c9ffa0930100049f50a3901806e1d8026716776006e81670786e84e8fa01706660e17f0440e17a0ff06690ea0de100e1e803f06550ec700080ea094a70166116bfeaeafec52185f8df0538ece803'),  # cave D: greeting (unreferenced 104 B function, used since v3)
     bytes.fromhex('7604c6ff90340100c4ff0893e1014539484049414a4281ea402e4c814842f0584c834d3c484049414a4281ea362e4c834840f05880ea317080ea718b484149424a4381ea2a2e684080ea698b684080f8020680ea909768413604c0ea0392')),
    (0x1e11b06, bytes.fromhex('75040416bfea31f850e81b0a4d61055635e94000552052d641624020bfeacdf768e808454861081f81d7c861814350ee4501004440223504ffeaf3f7619e4020'),  # cave A: bank_sw() + show_num() (unreferenced 68 B function, used since v2)
     bytes.fromhex('100400e1301049202217ca31432080eaef03c0ff9494010000ef800d0004412af4e100212316131b8b1e482082f902144831fa3601e1302002e13030c0eaada2')),
    (0x1e1305a, bytes.fromhex('c0ffa093010050ee0a12402af4e1103000e13030e3e10a30991e41e13010d22122174320bfea'),  # mode 3 screen #1 block: call bank_now + led_on (OUT only) + led_pwm
     bytes.fromhex('80ea8f01c0ea100000ef0100ffeac6fc52eeeb11c0ff00501e0002ef01008142c2ef01008000')),
    (0x1e13322, bytes.fromhex('30e1ff4f'),  # bank down: shown bank = new index + 1 (stock: shown bank - 1 -> 255 after boot)
     bytes.fromhex('38810000')),
    (0x1e13346, bytes.fromhex('4881'),  # bank up: shown bank = new index + 1 (stock: shown bank + 1)
     bytes.fromhex('3881')),
    (0x1e13370, bytes.fromhex('402af4e1304000e13040d121'),  # mode 3 bank/switch screen #2: call bank_sw
     bytes.fromhex('12163116bfeac7f3c0ea0900')),
    (0x1e1337c, bytes.fromhex('1217e1e10a40391e41e130104320bfea'),  # rest of stock block #2 (skipped): bank_now()
     bytes.fromhex('c3ffe890010039403a461981ffeabdf3')),
    (0x1e129ee, bytes.fromhex('00ef0100'),  # status LED (PA0) on -> led_on (OUT = 1, DIR left to led_pwm)
     bytes.fromhex('c0ea3803')),
    (0x1e11d78, bytes.fromhex('52eeeb11'),  # 5 ms display timer digit store -> led_pwm (PA0 output only in digit slot 0 = 1/3 duty)
     bytes.fromhex('80ea7709')),
    (0x1e260a0, bytes.fromhex('ffffffffffffffffffffffffffffffff'),  # cave C: show() = disp3 + os_time_dly(r5) (0xff padding)
     bytes.fromhex('43201004bfea276150168804d7ea648e')),
]
TEXT_TABLE = 0x1e19308               # cave B: 32 bytes of 0xff padding
TEXT_TABLE_MAX = 32
DISPLAYABLE = set('0123456789ABCDEFGHIJLNOPQRSTUYabcdefghijlnopqrstuy ')

def greet_texts(scroll, frames, mode_key):
    """Text table for greet(): scroll text, 0, frames (3 chars each), 0, mode key (3 chars)."""
    assert len(scroll) >= 4, 'scroll text needs at least 4 characters'
    assert frames and all(len(f) == 3 for f in frames), 'frames must be 3 characters each'
    assert len(mode_key) == 3, 'mode key must be 3 characters'
    s = scroll + ''.join(frames) + mode_key
    assert all(c in DISPLAYABLE for c in s), f'not displayable on the 7-segment font: {s!r}'
    t = scroll.encode('ascii') + bytes(1) + ''.join(frames).encode('ascii') + bytes(1) + mode_key.encode('ascii')
    assert len(t) <= TEXT_TABLE_MAX, f'texts too long ({len(t)} > {TEXT_TABLE_MAX} bytes)'
    return t

def patch_member(member, D, F, tapfix, ident=None, greeting=None):
    d = bytearray(member_decrypt(member[UBOOT:], KEY, POS))
    assert d[0x30:0x37] == b'app.bin', "unexpected app-area layout"
    # self-test: CRC rebuild must reproduce stock values exactly
    t = bytearray(d); rebuild_area_crcs(t); assert t == d, "CRC chain self-test failed"
    cmp_imm_patch(d, 0x1e12034, 0x4, D)
    cmp_imm_patch(d, 0x1e12090, 0xf, F)
    if tapfix:
        assert d[a(0x1e12002):a(0x1e12006)] == bytes.fromhex('80f81c02')
        assert d[a(CAVE_ADDR):a(0x1e260b0)] == b'\xff' * (0x1e260b0 - CAVE_ADDR)
        d[a(0x1e12002):a(0x1e12006)] = CALL_CAVE
        d[a(CAVE_ADDR):a(CAVE_ADDR) + len(CAVE)] = CAVE
    if ident:
        o = a(IDENT_ADDR)
        assert d[o:o+IDENT_SLOT] == b'FootCtrlPlus_012' + bytes(1) * 11, "ident slot mismatch"
        raw = ident.encode('ascii')
        assert len(raw) < IDENT_SLOT, "ident too long"
        d[o:o+IDENT_SLOT] = raw + bytes(1) * (IDENT_SLOT - len(raw))
    if greeting:
        for addr, stock, new in GREET:
            o = a(addr)
            assert d[o:o+len(stock)] == stock, f"greeting: unexpected stock bytes at {addr:#x}"
            d[o:o+len(new)] = new
        scroll, frames, mode_key = greeting
        t = greet_texts(scroll, frames, mode_key)
        o = a(TEXT_TABLE)
        assert d[o:o+TEXT_TABLE_MAX] == bytes([0xff]) * TEXT_TABLE_MAX, "text table area not empty"
        d[o:o+len(t)] = t
    rebuild_area_crcs(d)
    new = member[:UBOOT] + member_decrypt(bytes(d), KEY, POS)
    assert len(new) == len(member)
    return new, bytes(d)

def build(src_ufw, out_dir, tag, D, F, tapfix=True, version=14, ident='FootCtrlPlus_014-dtnprt', greeting=None, suffix=''):
    ufw = bytearray(open(src_ufw, 'rb').read())
    cnt = decode_header(ufw)['count']
    def rd(i): return bytearray(xcode_block(bytes(ufw[0x40+i*0x50:0x40+(i+1)*0x50])))
    def wr(i, e): ufw[0x40+i*0x50:0x40+(i+1)*0x50] = xcode_block(bytes(e))
    plains = {}
    for i in range(cnt):
        e = rd(i); name = e[0x40:0x50].split(b'\0')[0]
        if name not in (b'flash.bin', b'flash2.bin'): continue
        off, size = struct.unpack_from('<II', e, 0x08)
        member = bytes(ufw[off:off+size])
        assert struct.unpack_from('<H', e, 4)[0] == crc16(member), f"{name}: stock chunk CRC mismatch"
        new, plain = patch_member(member, D, F, tapfix, ident, greeting)
        ufw[off:off+size] = new
        struct.pack_into('<H', e, 4, crc16(new)); wr(i, e)
        plains[name.decode()] = plain
    assert set(plains) == {'flash.bin', 'flash2.bin'}
    ufw = fix_header_crc(bytes(ufw))
    h = decode_header(ufw); assert h['stored_crc'] == h['calc_crc']
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f'FootCtrlPlus_{version:03d}{suffix}' + (f'_{tag}' if tag else ''))
    open(base + '.ufw', 'wb').write(ufw)
    open(base + '.fwsc', 'wb').write(fwsc_wrap(ufw, 'FootCtrlPlus', version, suffix))
    open(base + '_app.bin', 'wb').write(plains['flash.bin'])   # decrypted app area, for disasm check
    print(f"{tag}: D={D} F={F} tapfix={tapfix} ident={ident} greeting={greeting}+battery -> {base}.fwsc")
    return base

if __name__ == '__main__':
    root = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(root, '..', '..', 'third-party', 'stock_firmware', 'FootCtrlPlus_012.ufw')   # stock build input (vendor)
    out = os.path.join(root, 'out')
    # version scheme: <version><build>, e.g. 141 = version 14, build 1 (3 digits: shown on the display,
    # in the name/version reply and in the .fwsc metadata)
    VERSION = 141
    # boot greeting: SCROLL slides in from the right (0.2 s per step), then the FRAMES (0.4 s each),
    # then the battery percent. Blanks around SCROLL make it enter and leave the display completely.
    # The font has no K M V W X Z ("U" stands in for V); B and T show as b and t.
    SCROLL = '   dtnPrt   '
    FRAMES = ['Uer', f'{VERSION:03d}', 'bAt']
    MODE_KEY = 'nod'              # shown before the mode number (no M on 7 segments)
    GREETING = (SCROLL, FRAMES, MODE_KEY)
    # footswitch timing: debounce D=3, combo window F=6 ticks of 5 ms (~40-45 ms press latency, 30 ms combo window)
    SUFFIX = '-dtnprt'            # file name / .fwsc metadata: FootCtrlPlus_141-dtnprt.fwsc
    build(src, out, '', D=3, F=6, version=VERSION, ident=f'FootCtrlPlus_{VERSION:03d}{SUFFIX}', greeting=GREETING, suffix=SUFFIX)
