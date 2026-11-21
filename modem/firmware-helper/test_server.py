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
 def test_validate_exits_before_socket(self):
  r=self.invoke('validate');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('socket_calls=0',r.stdout)
 def test_missing_readonly_policy_refuses_before_socket(self):
  r=self.invoke('no-policy');self.assertEqual(r.returncode,0,r.stderr);self.assertIn('socket_calls=0',r.stdout)
 def test_write_request_is_denied_at_protocol_boundary(self):
  r=self.invoke('wrq');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
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
