import os
from pathlib import Path
import subprocess
import unittest

SCRIPT=Path(__file__).with_name('verify-profiles.awk')
AWK=os.environ.get('PROFILE_TEST_AWK','awk')
HEADER='Service Version Instance Node Port\n'

def complete() -> list[list[int | str]]:
 return [[4096,key,0,1,16000+key] for key in range(1,11)]

class ProfileDiscoveryTest(unittest.TestCase):
 def invoke(self,rows,node='1',header=HEADER):
  text=header+''.join(' '.join(map(str,row))+'\n' for row in rows)
  result=subprocess.run([AWK,'-v','expected_node='+node,'-f',str(SCRIPT)],input=text,capture_output=True,text=True,timeout=5)
  self.assertEqual(result.stdout,'')
  return result.returncode
 def test_complete_set_in_any_order(self):self.assertEqual(self.invoke(complete()[::-1]),0)
 def test_explicit_other_local_node(self):
  rows=complete()
  for row in rows:row[3]=9
  self.assertEqual(self.invoke(rows,'9'),0)
 def test_missing_profile(self):self.assertNotEqual(self.invoke(complete()[:-1]),0)
 def test_duplicate_version(self):
  rows=complete();rows[-1][1]=9;self.assertNotEqual(self.invoke(rows),0)
 def test_duplicate_port(self):
  rows=complete();rows[-1][4]=rows[0][4];self.assertNotEqual(self.invoke(rows),0)
 def test_unreviewed_raw_key(self):
  rows=complete();rows[-1][1]=11;self.assertNotEqual(self.invoke(rows),0)
 def test_nonzero_logical_instance(self):
  rows=complete();rows[0][2]=1;self.assertNotEqual(self.invoke(rows),0)
 def test_wrong_local_node(self):
  rows=complete();rows[0][3]=0;self.assertNotEqual(self.invoke(rows),0)
 def test_malformed_header(self):self.assertNotEqual(self.invoke(complete(),header='untrusted header\n'),0)
 def test_control_port_is_not_a_data_endpoint(self):
  rows=complete();rows[0][4]=2**32-2;self.assertNotEqual(self.invoke(rows),0)
 def test_invalid_port_is_not_exported(self):
  rows=complete();rows[0][4]='private-identifier';self.assertNotEqual(self.invoke(rows),0)
 def test_leading_zero_version_is_not_normalized(self):
  rows=complete();rows[0][1]='01';self.assertNotEqual(self.invoke(rows),0)
 def test_empty_discovery_is_not_ready(self):self.assertNotEqual(self.invoke([]),0)
if __name__=='__main__':unittest.main(verbosity=2)
