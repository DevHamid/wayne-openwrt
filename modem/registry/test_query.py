#!/usr/bin/env python3
"""Test a fixed AP-side registry query; fixture never opens a real socket."""
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BINARY = Path(os.environ.get('LOCATOR_FIXTURE', HERE / 'build/query-fixture'))
PREFIX = shlex.split(os.environ.get('LOCATOR_RUNNER', ''))


def tlv(tag, value):
    return struct.pack('<BH', tag, len(value)) + value


def response(payload=None, flags=2, txn=0x1234, msg=0x21):
    if payload is None:
        domain = b'msm/modem/wlan_pd'
        entry = bytes([1, len(domain)]) + domain + struct.pack('<IBI', 180, 0, 0)
        payload = (tlv(2, b'\0\0\0\0') + tlv(16, struct.pack('<H', 1)) +
                   tlv(17, struct.pack('<H', 1)) + tlv(18, entry))
    return struct.pack('<BHHH', flags, txn, msg, len(payload)) + payload


class QueryTests(unittest.TestCase):
    def run_case(self, reply, case='reply', port='777'):
        self.assertTrue(BINARY.is_file(), 'fixed locator client fixture not built')
        with tempfile.TemporaryDirectory(prefix='locator-query-') as d:
            file = Path(d) / 'reply.bin'
            file.write_bytes(reply)
            result = subprocess.run([*PREFIX, str(BINARY), port], capture_output=True, text=True,
                                    timeout=4, env=dict(os.environ, FAKE_REPLY=str(file), FAKE_CASE=case))
        self.assertNotIn('AddressSanitizer', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        self.assertIn(result.returncode, (0, 1, 2), result.stderr)
        return result

    def test_valid_reply_prints_only_fixed_mapping(self):
        result = self.run_case(response())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'locator_reply=verified service=wlan/fw domain=msm/modem/wlan_pd instance=180\n')

    def test_every_truncated_prefix_is_refused(self):
        wire = response()
        for n in range(len(wire)):
            with self.subTest(prefix=n):
                result = self.run_case(wire[:n])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_wrong_header_or_peer_is_refused(self):
        for wire in (response(flags=0), response(txn=9), response(msg=0x22), response() + b'x', response() + b'x' * 512):
            result = self.run_case(wire)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
        for case in ('wrong-node', 'wrong-port', 'wrong-family', 'short-address'):
            self.assertNotEqual(self.run_case(response(), case).returncode, 0)

    def test_duplicate_unknown_or_missing_tlv_refused(self):
        payload = response()[7:]
        for value in (payload + tlv(2, b'\0' * 4), payload + tlv(33, b'PRIVATE_ID'),
                      payload[7:], payload[:-3]):
            result = self.run_case(response(value))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertNotIn('PRIVATE_ID', result.stderr)

    def test_rejected_empty_or_wrong_domain_refused(self):
        valid = response()
        for wire in (valid.replace(b'\x02\x04\x00\0\0\0\0', b'\x02\x04\x00\x01\0\x03\0', 1),
                     valid.replace(b'msm/modem/wlan_pd', b'msm/modem/root_pd'),
                     valid.replace(struct.pack('<IBI', 180, 0, 0), struct.pack('<IBI', 181, 0, 0)),
                     response(tlv(2, b'\0' * 4) + tlv(16, b'\0\0') + tlv(17, b'\x01\0'))):
            self.assertNotEqual(self.run_case(wire).returncode, 0)

    def test_transport_failures_never_retry_and_always_close(self):
        for case in ('send-eintr', 'partial-send', 'timeout', 'poll-eintr', 'recv-eintr'):
            with self.subTest(case=case):
                result = self.run_case(response(), case)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_invalid_port_refused_without_socket(self):
        for port in ('0', '-1', '1x', '4294967294', '4294967295', '4294967296'):
            with self.subTest(port=port):
                self.assertNotEqual(self.run_case(response(), port=port).returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
