#!/usr/bin/env python3
"""Offline checks for pdr_restart: exact QMI bytes, no network."""
import struct
import subprocess
import sys
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent / "build" / "host" / "pdr_restart"


def run(*args):
    return subprocess.run([str(BIN), *args], capture_output=True, text=True)


def request_bytes(name: bytes) -> bytes:
    """7-byte packed QMI header: type, txn u16, msg_id u16, len u16."""
    payload = 3 + len(name)
    return (bytes([0x00]) + struct.pack("<H", 1) + struct.pack("<H", 0x24)
            + struct.pack("<H", payload) + bytes([0x01])
            + struct.pack("<H", len(name)) + name)


def response_hex(result=0, error=0, msg_id=0x24, txn=1,
                 prefix_tlv=b"", qmi_type=0x02) -> str:
    payload = prefix_tlv + bytes([0x02, 4, 0]) + struct.pack("<HH", result, error)
    return (bytes([qmi_type]) + struct.pack("<H", txn) + struct.pack("<H", msg_id)
            + struct.pack("<H", len(payload)) + payload).hex()


class PacketTests(unittest.TestCase):
    def test_domain_path_encoding(self):
        name = b"msm/modem/wlan_pd"
        proc = run("--packet", name.decode())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), request_bytes(name).hex())

    def test_length_is_17_and_payload_20(self):
        proc = run("--packet", "msm/modem/wlan_pd")
        raw = bytes.fromhex(proc.stdout.strip())
        self.assertEqual(raw[0], 0x00)
        self.assertEqual(raw[3:5], b"\x24\x00")
        self.assertEqual(raw[5:7], b"\x14\x00")  # 3 + 17
        self.assertEqual(raw[8:10], b"\x11\x00")  # name length 17

    def test_max_length_name_accepted(self):
        name = "p" * 64
        proc = run("--packet", name)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        raw = bytes.fromhex(proc.stdout.strip())
        self.assertEqual(raw[5:7], struct.pack("<H", 67))
        self.assertEqual(len(raw), 7 + 67)

    def test_overlong_name_rejected(self):
        self.assertEqual(run("--packet", "p" * 65).returncode, 2)

    def test_empty_name_rejected(self):
        self.assertEqual(run("--packet", "").returncode, 2)


class ResponseTests(unittest.TestCase):
    def test_success(self):
        proc = run("--parse", response_hex())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("parse=ok", proc.stdout)
        self.assertIn("qmi_result=0", proc.stdout)
        self.assertIn("qmi_error=0", proc.stdout)

    def test_disabled_error_surfaces(self):
        proc = run("--parse", response_hex(result=1, error=0x30))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("qmi_result=1", proc.stdout)
        self.assertIn("qmi_error=48", proc.stdout)

    def test_wrong_message_id_rejected(self):
        proc = run("--parse", response_hex(msg_id=0x25))
        self.assertEqual(proc.returncode, 3)
        self.assertIn("parse=rejected", proc.stdout)

    def test_wrong_transaction_rejected(self):
        proc = run("--parse", response_hex(txn=0x09))
        self.assertEqual(proc.returncode, 3)

    def test_request_type_rejected_as_response(self):
        proc = run("--parse", response_hex(qmi_type=0x00))
        self.assertEqual(proc.returncode, 3)

    def test_truncated_rejected(self):
        self.assertEqual(run("--parse", response_hex()[:16]).returncode, 3)

    def test_unknown_tlv_skipped(self):
        proc = run("--parse", response_hex(prefix_tlv=bytes([0x11, 2, 0, 0xaa, 0xbb])))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("qmi_result=0", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
