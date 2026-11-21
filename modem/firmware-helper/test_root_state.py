#!/usr/bin/env python3
"""Fixed read-only root query; fixtures intercept all socket syscalls."""
import os
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
BINARY = os.environ.get('PDR_BINARY', str(HERE / 'build/host/pdr_restart'))
FIXTURE = os.environ.get('PDR_FIXTURE', str(HERE / 'build/host/pdr-fixture'))

class RootQueryTests(unittest.TestCase):
    def test_nonhex_decoder_input_is_refused_before_decode(self):
        p = subprocess.run([BINARY, '--parse-root', '020100210007000204000000000g'],
                           capture_output=True, text=True, timeout=4)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)

    def test_fixed_root_query_sends_once_closes_and_never_restarts(self):
        p = subprocess.run([FIXTURE, 'root-success'], capture_output=True, text=True, timeout=4)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('fixture rc=0 sockets=1 connections=1 sends=1 closes=1 guards=0', p.stdout)
        name = b'msm/modem/root_pd'
        packet = bytes([0, 1, 0, 0x21, 0, len(name) + 3, 0, 1, len(name), 0]) + name
        self.assertIn('frame0=' + packet.hex(), p.stdout)
        self.assertIn('root_query=verified state=UP', p.stdout)
        self.assertNotIn('frame1=', p.stdout)
        self.assertNotIn('response_frame=', p.stdout)

    def decode(self, frame):
        p = subprocess.run([BINARY, '--parse-root', frame.hex()],
                           capture_output=True, text=True, timeout=4)
        self.assertNotIn('AddressSanitizer', p.stderr)
        self.assertNotIn('runtime error:', p.stderr)
        return p

    def test_known_absent_and_unknown_states_are_distinct(self):
        import struct
        result = bytes([2, 4, 0, 0, 0, 0, 0])
        for state, label in [(0x7fffffff, 'UNINIT'), (0x0fffffff, 'DOWN'),
                             (0x1fffffff, 'UP'), (0x12345678, 'UNKNOWN'), (None, 'ABSENT')]:
            payload = result + (b'' if state is None else bytes([16, 4, 0]) + struct.pack('<I', state))
            frame = struct.pack('<BHHH', 2, 1, 0x21, len(payload)) + payload
            with self.subTest(state=state):
                p = self.decode(frame)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn('state=' + label, p.stdout)

    def test_all_truncated_prefixes_are_refused(self):
        frame = bytes.fromhex('02010021000e0002040000000000100400ffffff1f')
        for size in range(len(frame)):
            with self.subTest(size=size):
                p = self.decode(frame[:size])
                self.assertNotEqual(p.returncode, 0)
                self.assertNotIn('root_query=verified', p.stdout)

    def test_headers_duplicates_lengths_and_unexpected_tlvs_are_refused(self):
        import struct
        base = bytes.fromhex('02010021000e0002040000000000100400ffffff1f')
        cases = []
        for index, value in [(0, 0), (1, 2), (2, 1), (3, 0x24), (4, 1), (5, 7), (15, 3)]:
            b = bytearray(base); b[index] = value; cases.append(bytes(b))
        for payload in [base[7:14] * 2, base[14:] * 2, base[14:],
                        base[7:14] + b'\x33\x04\x00LEAK', base[7:14] + b'\x10']:
            cases.append(struct.pack('<BHHH', 2, 1, 0x21, len(payload)) + payload)
        for frame in cases:
            with self.subTest(frame=frame.hex()):
                p = self.decode(frame)
                self.assertEqual(p.returncode, 7, p.stdout + p.stderr)
                self.assertNotIn('root_query=verified', p.stdout)
                self.assertNotIn('LEAK', p.stdout)
                self.assertNotIn('state_raw=', p.stdout)

    def test_invalid_endpoints_are_refused_before_socket(self):
        for bad in ['', '-1', '+1', ' 1', '1x', '0xffffffff', '4294967294', '99999999999999999999999']:
            for node, port in [(bad, '1'), ('0', bad)]:
                with self.subTest(node=node, port=port):
                    p = subprocess.run([BINARY, '--query-root', node, port],
                                       capture_output=True, text=True, timeout=4)
                    self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                    self.assertNotIn('root_query_attempt=', p.stdout)

    def test_wrong_peer_is_rejected_even_with_a_valid_qmi_reply(self):
        for scenario in ['root-wrong-node', 'root-wrong-port', 'root-wrong-family', 'root-short-peer']:
            with self.subTest(scenario=scenario):
                p = subprocess.run([FIXTURE, scenario], capture_output=True, text=True, timeout=4)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn('fixture rc=7 sockets=1 connections=1 sends=1 closes=1 guards=0', p.stdout)
                self.assertNotIn('root_query=verified', p.stdout)

    def test_transport_errors_never_retry_and_close_opened_socket(self):
        cases = [('root-socket-fail', 3, 0, 0, 0), ('root-option-fail', 4, 1, 0, 0),
                 ('root-connect-fail', 4, 1, 1, 0), ('root-send-fail', 5, 1, 1, 1),
                 ('root-short-send', 5, 1, 1, 1), ('root-timeout', 6, 1, 1, 1),
                 ('root-oversize', 7, 1, 1, 1), ('root-wrong-txn', 7, 1, 1, 1),
                 ('root-wrong-message', 7, 1, 1, 1), ('root-bad-tail', 7, 1, 1, 1),
                 ('root-refused', 8, 1, 1, 1), ('root-absent', 0, 1, 1, 1)]
        for name, rc, sockets, connects, sends in cases:
            with self.subTest(name=name):
                p = subprocess.run([FIXTURE, name], capture_output=True, text=True, timeout=4)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn(f'fixture rc={rc} sockets={sockets} connections={connects} sends={sends} closes={sockets} guards=0', p.stdout)
                self.assertNotIn('frame1=', p.stdout)
                self.assertNotIn('AddressSanitizer', p.stderr)
                self.assertNotIn('runtime error:', p.stderr)

if __name__ == '__main__':
    unittest.main(verbosity=2)
