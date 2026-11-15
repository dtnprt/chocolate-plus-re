import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from firmware import split_143 as build
from firmware.split_143 import crc
from firmware.fwsctool import member_decrypt


BASELINE = Path(__file__).resolve().parents[1] / "firmware/out/142-baseline/FootCtrlPlus_142-dtnprt.fwsc"
MODULE = BASELINE.parent.parent / "sysex-split-143"


@unittest.skipUnless(BASELINE.is_file() and (MODULE / "sources.json").is_file(),
                     "Local vendor 142 and compiled extension required; not redistributed")
class CompiledSplitTests(unittest.TestCase):
    def setUp(self):
        self.original = build.candidate_image(BASELINE)
        self.blob, self.hooks, _ = build.read_module(MODULE)

    def test_complete_image_metadata_and_unchanged_user_regions(self):
        raw, plain = build.patch_image(self.original, self.blob, self.hooks)
        self.assertEqual(raw[:4096], self.original[:4096])
        self.assertLess(len(raw), 0x28000)
        self.assertEqual(len(raw) % 256, 0)
        self.assertEqual(member_decrypt(raw[4096:4096 + len(plain)], 0x180F, 0x20000), plain)
        for pos, name in ((0, "app_area_head"), (32, "app.bin"), (64, "cfg_tool.bin"),
                          (0x60, "VM"), (0x80, "PRCT"), (0xA0, "BTIF"), (0xC0, "EXIF"),
                          (0xE0, "USRFLASH"), (0x26410, "config.dat"), (0x26590, "md5.bin"),
                          (build.RESOURCE_HEADER, "sysexsplit.bin")):
            build.check_entry(plain, pos, name)
        self.assertEqual(plain[0x265B0:0x265D0], hashlib.md5(plain[0x120:0x260B0]).hexdigest().encode())
        self.assertEqual(plain[0x265F0:0x265F0 + len(self.blob)], self.blob)
        payload = plain[0x265F0:]
        self.assertEqual(crc(payload), int.from_bytes(plain[0x265D2:0x265D4], "little"))
        self.assertEqual(build.reservations(raw)["USRFLASH"], build.reservations(self.original)["USRFLASH"])

    def test_previous_timer_setting_and_save_hooks_are_stock_142(self):
        _, plain = build.patch_image(self.original, self.blob, self.hooks)
        baseline = member_decrypt(self.original[4096:], 0x180F, 0x20000)
        for offset in (0x11A16, 0x125D2, 0x18B44):
            with self.subTest(offset=offset):
                self.assertEqual(plain[offset:offset + 32], baseline[offset:offset + 32])
        self.assertEqual(set(self.hooks), {"boundary"})

    def test_tampered_exports_and_source_hashes_are_rejected(self):
        for filename in ("sysex-split.bin", "hook-boundary.bin", "sources.json"):
            with tempfile.TemporaryDirectory() as directory:
                copy = Path(directory) / "module"
                shutil.copytree(MODULE, copy)
                if filename == "sources.json":
                    (copy / filename).write_text("{}")
                else:
                    data = bytearray((copy / filename).read_bytes())
                    data[0] ^= 1
                    (copy / filename).write_bytes(data)
                with self.assertRaises(ValueError):
                    build.read_module(copy)

    def test_added_ram_and_missing_native_binding_are_rejected(self):
        for what in ("writable", "symbol"):
            with tempfile.TemporaryDirectory() as directory:
                copy = Path(directory) / "module"
                shutil.copytree(MODULE, copy)
                elf = bytearray((copy / "sysex-split.elf").read_bytes())
                if what == "writable":
                    table = struct.unpack_from("<I", elf, 32)[0]
                    flags = struct.unpack_from("<I", elf, table + 40 + 8)[0]
                    struct.pack_into("<I", elf, table + 40 + 8, flags | 1)
                else:
                    pos = elf.index(b"native_packet_return\0")
                    elf[pos] = ord("x")
                (copy / "sysex-split.elf").write_bytes(elf)
                with self.assertRaises(ValueError):
                    build.read_module(copy)

    def test_nonempty_tail_and_changed_hook_are_rejected(self):
        raw = bytearray(self.original)
        raw[-1] = 0
        with self.assertRaisesRegex(ValueError, "baseline"):
            build.patch_image(raw, self.blob, self.hooks)
        plain = bytearray(member_decrypt(self.original[4096:], 0x180F, 0x20000))
        plain[0x11A16] ^= 1
        raw = self.original[:4096] + member_decrypt(plain, 0x180F, 0x20000)
        with self.assertRaisesRegex(ValueError, "baseline"):
            build.patch_image(raw, self.blob, self.hooks)

    def test_build_manifest_does_not_claim_hardware_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build.build(BASELINE, MODULE, Path(directory) / "candidate")
            self.assertFalse(report["device_access"])
            self.assertEqual(report["added_wait_ms"], 0)
            self.assertFalse(report["configurable_gap"])
            self.assertEqual(report["patch_hooks"], ["boundary"])
            self.assertEqual(report["status"], "offline_candidate_not_hardware_validated")
            self.assertGreater(len(report["hardware_tests_pending"]), 0)
            self.assertEqual(json.loads((Path(directory) / "candidate/manifest.json").read_text()), report)


if __name__ == "__main__":
    unittest.main()
