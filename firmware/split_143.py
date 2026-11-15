#!/usr/bin/env python3
"""Build an offline experimental compact 143 image from exact upstream 142.

No device access, installer or OTA wrapper. Vendor binaries remain local.
The existing 142 builder and its reproducible output are unchanged.
"""
from __future__ import annotations

import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

try:
    from .fwsctool import member_decrypt, fwsc_unwrap, xcode_block
except ImportError:
    from fwsctool import member_decrypt, fwsc_unwrap, xcode_block

VBASE = 0x1E00000
COMPACT_SHA256 = "2c7160bbd55144344d19ce40ed24f64683f92e070cd9d0816be5a321af9659b7"
BASELINE_FWSC_SHA256 = "eadd20b993b149753651f83a683d1af25fb4f966d340e0b269a33b300f2e3ba2"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def crc(data):
    return binascii.crc_hqx(data, 0)


def candidate_image(path):
    data = path.read_bytes()
    require(sha(data) == BASELINE_FWSC_SHA256, "Expected exact upstream 142 FWSC baseline")
    ufw = fwsc_unwrap(data, "")
    # The pinned complete package has eight members. Select its compact image.
    matches = []
    for index in range(8):
        entry = xcode_block(ufw[64 + index * 80:144 + index * 80])
        offset, size = struct.unpack_from("<II", entry, 8)
        if bytes(entry[64:80]).split(b"\0", 1)[0] in (b"flash.bin", b"flash2.bin") and size == 0x27600:
            matches.append(ufw[offset:offset + size])
    require(len(matches) == 1 and sha(matches[0]) == COMPACT_SHA256, "Compact baseline differs")
    return matches[0]


def reservations(raw):
    area = member_decrypt(raw[0x1000:], key=0x180F, pos=0x20000)
    records = {}
    for pos in range(0x60, 0x100, 32):
        entry = area[pos:pos + 32]
        require(crc(entry[2:]) == int.from_bytes(entry[:2], "little"),
                "Reservation directory CRC mismatch.")
        name = entry[16:32].split(b"\0", 1)[0].decode("ascii")
        offset, size = struct.unpack_from("<II", entry, 4)
        records[name] = dict(offset=offset, size=size, flags=entry[12])
    require(set(records) == {"VM", "PRCT", "BTIF", "EXIF", "USRFLASH"},
            "Unexpected reservation directory.")
    return records


def vm_geometry(start, size):
    # Audited native 013 at 0x1e14da6..0x1e14e38 and 012/142 at
    # 0x1e14ddc..0x1e14e8a: clamp to 16 KiB, force 4-KiB mode at that
    # length, round start up to 4 KiB and usable length down to 8 KiB.
    require(min(size, 16384) == 16384, "VM size outside the audited native branch.")
    aligned = (start + 4095) & -4096
    usable = (start + 16384 - aligned) & -8192
    return dict(start=aligned, second_bank=aligned + usable // 2,
                bank_bytes=usable // 2, end=aligned + usable)


IDENTITY = "FootCtrlPlus_143-split"
PATCH_ADDRESS = 0x1E265F0
RESOURCE_HEADER = 0x265D0
APP_OFFSET, APP_BYTES = 0x120, 155536
SOURCE_DIR = Path(__file__).resolve().parents[1] / "firmware" / "patch_src"
SOURCES = ("sysex_split.c", "sysex_split.h", "sysex_split_glue.S", "sysex_split.ld",
           "test_sysex_split.c", "build_sysex_split.sh")
HOOKS = {
    "boundary": (0x1E0FF54, bytes.fromhex("78187518"), "ch_boundary_glue", "goto"),
}
BINDINGS = dict(native_output_callback=0x194A0,
                native_packet_return=0x1E1004C, native_packet_continue=0x1E0FF58)


def align(value, boundary):
    return (value + boundary - 1) & -boundary


def branch(data, address, kind):
    require(len(data) == 4 and data[1] == 0xEA and
            data[0] & 0xC0 == {"call": 0x80, "goto": 0xC0}[kind], "Invalid PI32v2 branch")
    delta = ((data[0] & 63) << 16) | int.from_bytes(data[2:], "little")
    if delta & (1 << 21):
        delta -= 1 << 22
    return (address + 4 + delta * 2) & 0x1FFFFFF


def read_module(directory):
    """Cross-check binary exports, native ABI, sections and linked hook targets."""
    elf = (directory / "sysex-split.elf").read_bytes()
    require(len(elf) >= 52 and elf[:7] == b"\x7fELF\x01\x01\x01", "Expected ELF32 little endian")
    fields = struct.unpack_from("<16sHHIIIIIHHHHHH", elf)
    _, kind, machine, version, entry, _, table, _, size, _, _, stride, count, strings = fields
    require((kind, machine, version, size, stride) == (2, 241, 1, 52, 40), "Unexpected PI32v2 ELF")
    require(0 < strings < count < 64 and table + count * stride <= len(elf), "Invalid section table")
    headers = [struct.unpack_from("<10I", elf, table + i * stride) for i in range(count)]

    def extent(h):
        require(h[1] != 8 and h[4] + h[5] <= len(elf), "Invalid section extent")
        return elf[h[4]:h[4] + h[5]]

    def string(data, offset):
        require(0 <= offset < len(data) and b"\0" in data[offset:], "Invalid ELF string")
        return data[offset:].split(b"\0", 1)[0].decode("ascii")

    names = extent(headers[strings])
    sections = {string(names, h[0]): h for h in headers}
    allocated = {name for name, h in sections.items() if h[2] & 2 and h[5]}
    require(allocated == {".patch", *(".hook_" + name for name in HOOKS)}, "Unexpected allocated section")
    require(not any(h[2] & 3 == 3 and h[5] for h in headers), "Added writable RAM section")
    require(not any(h[1] in (4, 9) and h[5] for h in headers), "Unresolved relocations")
    symtab = sections[".symtab"]
    require(symtab[9] == 16 and symtab[5] % 16 == 0 and symtab[6] < count, "Invalid symbol table")
    names = extent(headers[symtab[6]])
    symbols = {}
    for pos in range(0, symtab[5], 16):
        name, value, _, _, _, section = struct.unpack_from("<IIIBBH", extent(symtab), pos)
        require(not (name and section == 0), "Undefined symbol")
        if name:
            symbols[string(names, name)] = value
    require(all(symbols.get(n) == a for n, a in BINDINGS.items()), "Native ABI binding differs")
    blob = (directory / "sysex-split.bin").read_bytes()
    require(0 < len(blob) <= 0x100 and sections[".patch"][3] == PATCH_ADDRESS and
            extent(sections[".patch"]) == blob, "Extension binary/address differs from ELF")
    require(entry == symbols["ch_boundary_glue"], "Wrong ELF entry")
    hooks = {}
    for name, (address, _, symbol, kind) in HOOKS.items():
        data = (directory / f"hook-{name}.bin").read_bytes()
        require(len(data) == 4 and sections[".hook_" + name][3] == address and
                data == extent(sections[".hook_" + name]), f"Hook export differs: {name}")
        target = int.from_bytes(data, "little") if kind == "pointer" else branch(data, address, kind)
        require(target == symbols[symbol] and PATCH_ADDRESS <= target < PATCH_ADDRESS + len(blob),
                f"Wrong hook target: {name}")
        hooks[name] = data
    glue = symbols["ch_boundary_glue"]
    pos = glue - PATCH_ADDRESS
    require(blob[pos:pos + 8] == bytes.fromhex("801671167818dd1d") and
            blob[pos + 12:pos + 14] == bytes.fromhex("0042"),
            "Boundary glue must preserve both displaced additions and the conditional")
    for offset, name, kind in ((8, "ch_host_boundary", "call"), (14, "native_packet_return", "goto"),
                                (18, "native_packet_continue", "goto")):
        require(branch(blob[pos + offset:pos + offset + 4], glue + offset, kind) == symbols[name],
                f"Boundary glue target differs: {name}")
    require({name for name in symbols if name.startswith("native_")} == set(BINDINGS),
            "Unexpected timer, flash or configuration binding")
    sources = {name: sha((SOURCE_DIR / name).read_bytes()) for name in SOURCES}
    require(json.loads((directory / "sources.json").read_text()) == sources,
            "Sources changed since compilation; rebuild the module")
    return blob, hooks, dict(elf_sha256=sha(elf), module_sha256=sha(blob),
                             module_bytes=len(blob), sources=sources,
                             symbols={n: hex(symbols[n]) for n in (*BINDINGS, "ch_host_boundary",
                                      *(v[2] for v in HOOKS.values()))})


def check_entry(data, pos, name, size=None):
    raw = data[pos:pos + 32]
    require(len(raw) == 32 and crc(raw[2:]) == int.from_bytes(raw[:2], "little"), "Directory CRC mismatch")
    require(raw[16:].split(b"\0", 1)[0] == name.encode(), f"Expected {name}")
    if size is not None:
        require(int.from_bytes(raw[8:12], "little") == size, f"Unexpected {name} length")
    return raw


def fix_entry(data, pos, payload=None):
    if payload is not None:
        struct.pack_into("<H", data, pos + 2, crc(payload))
    struct.pack_into("<H", data, pos, crc(data[pos + 2:pos + 32]))


def patch_image(original, blob, hooks):
    require(len(original) == 0x27600 and sha(original) == COMPACT_SHA256, "Expected exact compact 142 baseline")
    require(0 < len(blob) <= 0x100 and set(hooks) == set(HOOKS), "Invalid extension/hook set")
    full = member_decrypt(original[0x1000:], 0x180F, 0x20000)
    require(original[0x1000 + RESOURCE_HEADER:] == b"\xff" * 48, "Resource tail is occupied")
    d = bytearray(full[:RESOURCE_HEADER])
    check_entry(d, 0, "app_area_head", 0x26410)
    check_entry(d, 32, "app.bin", APP_BYTES)
    check_entry(d, 0x40, "cfg_tool.bin", 0x360)
    check_entry(d, 0x26410, "config.dat", 0x180)
    check_entry(d, 0x26590, "md5.bin", 0x40)
    require(int.from_bytes(d[0x2659E:0x265A0], "little") == 1, "MD5 must be the last resource")
    for name, (address, before, _, _) in HOOKS.items():
        pos = address - VBASE
        require(d[pos:pos + 4] == before and len(hooks[name]) == 4, f"Unexpected native hook: {name}")
        d[pos:pos + 4] = hooks[name]
    ident = 0x18C8E
    old = b"FootCtrlPlus_142-dtnprt".ljust(27, b"\0")
    require(d[ident:ident + 27] == old and d[0x19308:0x19318] == b"   Uer142bAt\0nod", "Baseline identity/greeting differs")
    d[ident:ident + 27] = IDENTITY.encode().ljust(27, b"\0")
    d[0x1930E:0x19311] = b"143"
    padded_end = align(PATCH_ADDRESS - VBASE + len(blob), 32)
    image_end = align(0x1000 + padded_end, 256)
    require(image_end < 0x28000, "Compact extension would change native VM banks")
    before = reservations(original)
    for pos, name in ((0x60, "VM"), (0x80, "PRCT")):
        check_entry(d, pos, name)
        offset, size = (image_end, 0x37000 - image_end) if name == "VM" else (0, image_end)
        struct.pack_into("<II", d, pos + 4, offset, size)
        fix_entry(d, pos)
    app = d[APP_OFFSET:APP_OFFSET + APP_BYTES]
    fix_entry(d, 32, app)
    fix_entry(d, 0, d[32:0x26410])
    # Upstream 142 leaves the stock MD5 resource stale; this candidate refreshes it.
    digest = hashlib.md5(app).hexdigest().encode("ascii")
    d[0x265B0:0x265D0] = digest
    struct.pack_into("<H", d, 0x2659E, 0)
    fix_entry(d, 0x26590, digest)
    padded = blob + b"\xff" * (padded_end - (PATCH_ADDRESS - VBASE) - len(blob))
    header = bytearray(struct.pack("<HHIIBBH16s", 0, crc(padded), 32, 32 + len(padded),
                                   0x82, 0xFF, 1, b"sysexsplit.bin\0".ljust(16, b"\xff")))
    fix_entry(header, 0)
    d.extend(header + padded)
    require(len(d) == padded_end, "Resource extent differs from link address")
    raw = original[:0x1000] + member_decrypt(d, 0x180F, 0x20000)
    raw += b"\xff" * (image_end - len(raw))
    after = reservations(raw)
    for name in ("BTIF", "EXIF", "USRFLASH"):
        require(before[name] == after[name], f"{name} reservation moved")
    require(vm_geometry(before["VM"]["offset"], before["VM"]["size"]) ==
            vm_geometry(after["VM"]["offset"], after["VM"]["size"]), "Native VM bank geometry changed")
    # Check the complete original extent, not just the named hook sites.
    allowed = set()
    windows = [(0, 4), (32, 36), (0x60, 0x6C), (0x80, 0x8C),
               (ident, ident + 27), (0x1930E, 0x19311), (0x26590, 0x265D0)]
    windows += [(a - VBASE, a - VBASE + 4) for a, _, _, _ in HOOKS.values()]
    for first, last in windows:
        allowed.update(range(first, last))
    require(all(a == b or i in allowed for i, (a, b) in enumerate(zip(full[:RESOURCE_HEADER], d))),
            "Unexpected change outside extension/metadata/hook windows")
    require(crc(d[APP_OFFSET:APP_OFFSET + APP_BYTES]) == int.from_bytes(d[34:36], "little") and
            crc(d[32:0x26410]) == int.from_bytes(d[2:4], "little"), "Candidate application CRC mismatch")
    return raw, bytes(d)


def build(baseline, module, output):
    original = candidate_image(baseline)
    blob, hooks, report = read_module(module)
    raw, plain = patch_image(original, blob, hooks)
    report.update(schema=1, identity=IDENTITY, status="offline_candidate_not_hardware_validated",
                  baseline="exact upstream 142", image_bytes=len(raw), image_sha256=sha(raw),
                  application_sha256=sha(plain[APP_OFFSET:APP_OFFSET + APP_BYTES]),
                  added_wait_ms=0, configurable_gap=False, patch_hooks=["boundary"],
                  vm=vm_geometry(0x27600, 0xFA00), device_access=False,
                  hardware_tests_pending=["boot and USB/BLE enumeration", "configuration preservation",
                                          "one key, multiple SysEx over HOST, measured timing"])
    output.mkdir(parents=True, exist_ok=False)
    (output / "FootCtrlPlus_143-split.compact.bin").write_bytes(raw)
    (output / "app-area.bin").write_bytes(plain)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build(args.baseline, args.module, args.output)
        print(json.dumps({k: v for k, v in result.items() if k not in ("symbols", "sources")}, indent=2))
    except (ValueError, OSError, KeyError, struct.error) as error:
        parser.exit(2, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
