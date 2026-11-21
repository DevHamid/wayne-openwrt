#!/usr/bin/env python3
"""Offline assertions for the actual C transport; all syscalls wrapped."""
import os
import subprocess
import unittest
from pathlib import Path

BIN = os.environ.get('PDR_FIXTURE', str(Path(__file__).resolve().parent/'build/host/pdr-fixture'))

class ListenerTransport(unittest.TestCase):
    def case(self, name):
        p = subprocess.run([BIN, name], capture_output=True, text=True, timeout=4)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
        return p.stdout

    def test_register_then_restart_same_socket(self):
        text = self.case('success')
        self.assertIn('fixture rc=0 sockets=1 connections=1 sends=2 closes=1 guards=2', text)
        name = b'msm/modem/wlan_pd'
        register = b'\x00\x01\x00\x20\x00\x18\x00\x01\x01\x00\x01\x02\x11\x00'+name
        restart = b'\x00\x02\x00\x24\x00\x14\x00\x01\x11\x00'+name
        self.assertIn('frame0='+register.hex(), text)
        self.assertIn('frame1='+restart.hex(), text)

    def test_listener_refusal_prevents_restart(self):
        text = self.case('refused')
        self.assertIn('fixture rc=8 sockets=1 connections=1 sends=1 closes=1 guards=1', text)

    def test_provider_expired_before_any_socket(self):
        self.assertIn('fixture rc=9 sockets=0 connections=0 sends=0 closes=0 guards=1', self.case('dead-before'))

    def test_provider_expired_after_registration(self):
        self.assertIn('fixture rc=9 sockets=1 connections=1 sends=1 closes=1 guards=2', self.case('dead-after'))

    def test_reused_pid_with_wrong_executable(self):
        self.assertIn('fixture rc=9 sockets=0 connections=0 sends=0 closes=0 guards=1', self.case('wrong-exe'))

    def test_timeout_does_not_retry(self):
        self.assertIn('fixture rc=6 sockets=1 connections=1 sends=1 closes=1 guards=1', self.case('timeout'))

    def test_unmatched_response_does_not_restart(self):
        self.assertIn('fixture rc=7 sockets=1 connections=1 sends=1 closes=1 guards=1', self.case('wrong-txn'))

    def test_malformed_tail_after_result_does_not_restart(self):
        self.assertIn('fixture rc=7 sockets=1 connections=1 sends=1 closes=1 guards=1', self.case('bad-tail'))

    def test_length_mismatch_does_not_restart(self):
        self.assertIn('fixture rc=7 sockets=1 connections=1 sends=1 closes=1 guards=1', self.case('trailing'))

    def test_restart_refusal_is_reported(self):
        text = self.case('restart-refused')
        self.assertIn('response=restart qmi_result=1 qmi_error=9', text)
        self.assertIn('fixture rc=8 sockets=1 connections=1 sends=2 closes=1 guards=2', text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
