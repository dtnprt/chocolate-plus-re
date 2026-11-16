#!/usr/bin/env python3
"""
Build the dtnprt custom firmware 142 plus E/F switches and power-on mode selection ("152-ef").

    python3 -I ef_build.py FootCtrlPlus_012.fwsc [-o out] [--extras]

Runs the unmodified chocolate-plus-re build (142: debounce, tap fix, greeting, LED, bank screen, ...) and then
applies, in flash.bin and flash2.bin (code: ef.c + patch.s, linked by ef.ld into sec_*.bin):

  hook   0x1e00426  greet(): call vbat_percent -> boot_sel (hold A-D at power-on: switch to the mapped mode)
  combo  0x1e11f34  A+B / C+D detection: with E/F on, only the second switch is consumed, the first is flagged
  ef     0x1e13268  mode 3 handler (m3_key) + ef_cur() + alias()               (was stock mode 3 handler)
  ef3    0x1e13436  mode 6/7/8 handler (fix_key) + mode 11 wrapper + boot_sel  (was 3 identical stock handlers)
  ef2    0x1e135b4  mode 10 handler (kb10_key)                                 (was stock mode 10 handler)
  key table 0x1e18da4: entries 3, 6, 7, 8, 10, 11 -> the new handlers

E/F on: mode 3 = "Max group count" 1 (bankMax[2] == 0); mode 10 / 11 = CFG bit 0 / 1. CFG / SCR: see ef.c.
"""
import sys, os, struct, hashlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(HERE, '..')
sys.path.insert(0, FW)
import build as B                                   # noqa: E402
from fwsctool import member_decrypt                 # noqa: E402

VERSION = 152              # odd version number = development build (see chocolate-plus-re README)
SUFFIX = '-ef'

def rd(name):
    return open(os.path.join(HERE, name), 'rb').read()

def sym(name):
    """address of a symbol in ef.elf (from `nm`, saved next to the sections by the build step)"""
    for line in open(os.path.join(HERE, 'ef.syms')):
        a, t, n = line.split()
        if n == name:
            return int(a, 16)
    raise KeyError(name)

# (address, end, sha256 of the bytes expected there after the 142 patches, new code)
PATCHES = [
    (0x1e00426, 0x1e0042a, '96386e62652bbf48f3982c05edbede9fcd141ab3ca3b6c0bbad3d93b4bb83f2f', rd('sec_hook.bin')),
    (0x1e11f34, 0x1e11f82, '66f5b8805a1c1235b1e2a507882b1e8181b4186fbf3a9f4a5bcfaf73d1cb6ac5', rd('sec_combo.bin')),
    (0x1e13268, 0x1e1337c, '1e1057ab51228329a2a3ec2927f9b4d11adfd38576c2bc05d9aea747c0f760a0', rd('sec_ef.bin')),
    (0x1e13436, 0x1e1354a, '1eabf40d18ad93719d1766134bcd18887b1df7d0294445468694d9ea749201e4', rd('sec_ef3.bin')),
    (0x1e135b4, 0x1e1369e, '3af9ec81fbb84b226a9b6fdd6bd21d111316d1bee52e81ea980d6b4623c5f6e3', rd('sec_ef2.bin')),
]
KEY_TABLE = 0x1e18da4      # mode key handlers [13]
TABLE = {  # mode: (stock handler, new handler)
    3: (0x1e13268, sym('m3_key')),
    6: (0x1e13436, sym('fix_key')),
    7: (0x1e13492, sym('fix_key')),
    8: (0x1e134ee, sym('fix_key')),
    10: (0x1e135b4, sym('kb10_key')),
    11: (0x1e1369e, sym('mix_wrap')),
}

orig_patch_member = B.patch_member

def patch_member(member, *args, **kw):
    new, plain, stock_plain = orig_patch_member(member, *args, **kw)
    d = bytearray(plain)
    for addr, end, digest, code in PATCHES:
        o, e = B.a(addr), B.a(end)
        assert len(code) <= e - o, f'{addr:#x}: patch too long ({len(code)} > {e - o})'
        got = hashlib.sha256(d[o:e]).hexdigest()
        assert got == digest, f'{addr:#x}: unexpected bytes before patching ({got})'
        d[o:e] = code + bytes(e - o - len(code))     # rest: nop (0x0000), never reached
    for mode, (old, new_fn) in TABLE.items():
        o = B.a(KEY_TABLE + 4 * mode)
        assert struct.unpack_from('<I', d, o)[0] == old, f'key table entry {mode}: unexpected value'
        struct.pack_into('<I', d, o, new_fn)
    B.rebuild_area_crcs(d)
    new = member[:B.UBOOT] + member_decrypt(bytes(d), B.KEY, B.POS)
    assert len(new) == len(member)
    return new, bytes(d), stock_plain

B.patch_member = patch_member

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('-o', '--out', default='.')
    ap.add_argument('--extras', action='store_true')
    args = ap.parse_args()
    stock = B.load_stock(args.stock)
    frames = ['   ', 'Uer', f'{VERSION:03d}', 'bAt']
    base = B.build(stock, args.out, '', D=3, F=6, version=VERSION, ident=f'FootCtrlPlus_{VERSION:03d}{SUFFIX}',
                   greeting=(frames, 'nod'), suffix=SUFFIX, extras=args.extras)
    out = base + '.fwsc'
    print(f'written: {out}\nSHA-256: {hashlib.sha256(open(out, "rb").read()).hexdigest()}')

if __name__ == '__main__':
    sys.exit(main())
