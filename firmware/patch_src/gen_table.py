#!/usr/bin/env python3
"""Copy the assembled patch bytes from patch_src/greet.elf into the GREET table of build.py.

Run after `asm_greet.sh` (WSL JieLi toolchain):  python -I patch_src/gen_table.py
Each entry stores the exact stock bytes (from ../thirdparty/firmware_reference/app_area_decrypted.bin) that build.py checks before patching.
"""
import os, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DESC = {
    '.hook': 'hook: was `call 0x1e1286a`',
    '.cave_d': 'cave D: greeting (unreferenced 104 B function, used since v3)',
    '.cave_a': 'cave A: bank_sw() + show_num() (unreferenced 68 B function, used since v2)',
    '.site_a_bank': 'mode 3 screen #1 block: call bank_now + led_on (OUT only) + led_pwm',
    '.bank_down_fix': 'bank down: shown bank = new index + 1 (stock: shown bank - 1 -> 255 after boot)',
    '.bank_up_fix': 'bank up: shown bank = new index + 1 (stock: shown bank + 1)',
    '.site_a': 'mode 3 bank/switch screen #1: call bank_sw',
    '.site_a_tail': 'rest of stock block #1 (skipped): led_on',
    '.site_b': 'mode 3 bank/switch screen #2: call bank_sw',
    '.site_b_tail': 'rest of stock block #2 (skipped): bank_now()',
    '.site_led_on': 'status LED (PA0) on -> led_on (OUT = 1, DIR left to led_pwm)',
    '.site_pwm': '5 ms display timer digit store -> led_pwm (PA0 output only in digit slot 0 = 1/3 duty)',
    '.cave_c': 'cave C: show() = disp3 + os_time_dly(r5) (0xff padding)',
}
SKIP = {'.cave_b'}   # text table: written by build.py from its settings


def sections(elf_path):
    e = open(elf_path, 'rb').read()
    shoff, = struct.unpack_from('<I', e, 0x20)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', e, 0x2e)
    secs = [struct.unpack_from('<IIIIIIIIII', e, shoff + i * shentsize) for i in range(shnum)]
    so = secs[shstrndx][4]
    name = lambda o: e[so + o:e.index(b'\0', so + o)].decode()
    out = []
    for s in secs:
        n = name(s[0])
        if not n or n in SKIP or n in ('.shstrtab', '.symtab', '.strtab'):
            continue
        assert n in DESC, f'unknown section {n}: add it to DESC (every section must be patched)'
        out.append((n, s[3], e[s[4]:s[4] + s[5]]))
    return out


def main():
    stock = open(os.path.join(ROOT, '..', 'thirdparty', 'firmware_reference', 'app_area_decrypted.bin'), 'rb').read()
    lines = []
    for n, addr, code in sections(os.path.join(HERE, 'greet.elf')):
        o = addr - 0x1e00000
        assert n in DESC, f'add a description for section {n}'
        assert addr != 0x1e04a84, 'never use the pairing-record function 0x1e04a84 as a cave'
        lines.append(f"    (0x{addr:x}, bytes.fromhex('{stock[o:o + len(code)].hex()}'),  # {DESC[n]}\n"
                     f"     bytes.fromhex('{code.hex()}')),")
    p = os.path.join(ROOT, 'build.py')
    src = open(p, 'rb').read().decode('ascii')
    a = src.index('GREET = [\n')
    b = src.index('TEXT_TABLE = ')
    src = src[:a] + 'GREET = [\n' + '\n'.join(lines) + '\n]\n' + src[b:]
    open(p, 'wb').write(src.encode('ascii'))
    print(f'updated GREET in build.py ({len(lines)} entries)')


if __name__ == '__main__':
    main()
