import os
from pathlib import Path
import subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent
class ServerPolicyTest(unittest.TestCase):
 def invoke(self,case):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name)
   content=bytes(i%251 for i in range((1<<20)+1)) if case=='rrq-bulk' else b'reviewed firmware fixture'
   (root/'wlanmdsp.mbn').write_bytes(content)
   command=os.environ.get('SERVER_FIXTURE',str(HERE/'build/host/server-fixture'))
   result=subprocess.run([command,str(root),case],capture_output=True,text=True,timeout=5)
   self.assertFalse((root/'server_check.txt').exists())
   return result
 def test_check_read_returns_only_the_received_ram_bytes(self):
  r=self.invoke('ramcheck-readback');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('check_reads=1 errors=0',r.stdout)
 def test_check_rejects_duplicate_negotiation_options(self):
  r=self.invoke('ramcheck-duplicate-option');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_check_vendor_options_complete_without_disk_writes(self):
  r=self.invoke('ramcheck-vendor-options');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_check_retains_default_deny_for_other_paths(self):
  r=self.invoke('ramcheck-other-path');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_check_request_budget_is_bounded(self):
  r=self.invoke('ramcheck-cap');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_check_invalid_packets_cannot_commit_data(self):
  for fault in ('timeout','node','port','family','sockaddr','short','oversize','block','opcode'):
   with self.subTest(fault=fault):
    r=self.invoke('ramcheck-fault-'+fault);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_opt_in_check_write_is_acked_without_creating_a_file(self):
  r=self.invoke('ramcheck-write');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('check_acks=1 errors=0',r.stdout)
 def test_ramcheck_opt_in_validates_without_socket_or_file_creation(self):
  r=self.invoke('ramcheck-validate');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('socket_calls=0',r.stdout)
 def test_validate_exits_before_socket(self):
  r=self.invoke('validate');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('socket_calls=0',r.stdout)
 def test_missing_readonly_policy_refuses_before_socket(self):
  r=self.invoke('no-policy');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('socket_calls=0',r.stdout)
 def test_write_request_is_denied_at_protocol_boundary(self):
  r=self.invoke('wrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertIn('error_code=2',r.stdout)
 def test_denied_write_reports_target_name_without_payload(self):
  r=self.invoke('wrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  line=[l for l in r.stdout.splitlines() if l.startswith('readonly_write=denied')]
  self.assertEqual(len(line),1,r.stderr)
  self.assertIn('name=/readwrite/server_check.txt',line[0])
  self.assertRegex(line[0],r'request_len=\d+ name_len=\d+')
 def test_denied_write_name_is_bounded_and_printable(self):
  r=self.invoke('wrq-long');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  line=[l for l in r.stdout.splitlines() if l.startswith('readonly_write=denied')][0]
  shown=line.split('name=',1)[1]
  self.assertLessEqual(len(shown),96)
  self.assertTrue(all(32 <= ord(c) < 127 for c in shown),shown)
  self.assertIn('name_len=',line)
 def test_nonfirmware_read_is_denied_without_logging_its_path(self):
  r=self.invoke('denied-rrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('/readwrite/',r.stderr)
 def test_firmware_rrq_sends_data(self):
  r=self.invoke('rrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('data_sends=1',r.stdout)
 def test_all_truncated_rrq_prefixes_are_rejected(self):
  r=self.invoke('truncated-rrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_short_error_packet_is_not_decoded(self):
  r=self.invoke('short-error');self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertNotIn('received error',r.stderr)
 def test_vendor_windowed_read_transfers_every_byte(self):
  r=self.invoke('rrq-bulk');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_large_window_is_rejected_before_allocation(self):
  r=self.invoke('huge-window');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_read_sessions_are_bounded(self):
  r=self.invoke('session-cap');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_stock_raw_keys_have_distinct_listener_ports(self):
  r=self.invoke('listen-all');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_tenth_listener_is_in_receive_dispatch(self):
  r=self.invoke('listen-last');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_partial_publication_failure_closes_all_owned_sockets(self):
  r=self.invoke('listen-publish-fail');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_partial_socket_failure_closes_prior_listeners(self):
  r=self.invoke('listen-socket-fail');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_select_error_closes_every_listener(self):
  r=self.invoke('listen-select-fail');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_listener_records_rrq_before_filename_parse(self):
  r=self.invoke('listen-rx-rrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertIn('readonly_rx=rrq profile=1',r.stdout)
  self.assertNotIn('readonly_firmware_open=accepted',r.stderr)
 def test_every_listener_datagram_is_logged_before_dispatch(self):
  r=self.invoke('listen-rx-short');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertIn('readonly_listener_rx bytes=1 profile=1',r.stdout)
  self.assertNotIn('readonly_rx=',r.stdout)
 def test_out_of_range_descriptor_is_rejected_before_fd_set(self):
  r=self.invoke('listen-high-fd');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
