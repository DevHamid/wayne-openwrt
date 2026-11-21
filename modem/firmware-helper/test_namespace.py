import os
from pathlib import Path
import subprocess
import unittest

FIXTURE=os.environ.get('NAMESPACE_FIXTURE',str(Path(__file__).parent/'build/host/namespace-fixture'))
class NamespaceStorageTest(unittest.TestCase):
 def check(self,mode,count):
  result=subprocess.run([FIXTURE,mode],capture_output=True,text=True,timeout=5)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertIn('namespace_count='+str(count)+' network_calls=0',result.stdout)
 def test_same_port_is_a_negative_control(self):self.check('same',1)
 def test_distinct_ports_preserve_all_stock_keys(self):self.check('distinct',10)
if __name__=='__main__':unittest.main(verbosity=2)
