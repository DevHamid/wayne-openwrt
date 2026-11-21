import os
from pathlib import Path
import subprocess
import unittest

FIXTURE=os.environ.get('PUBLISH_FIXTURE',str(Path(__file__).parent/'build/host/publish-fixture'))
class PublishTest(unittest.TestCase):
 def check(self,mode,node):
  result=subprocess.run([FIXTURE,mode],capture_output=True,text=True,timeout=5)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertIn('delivered=1 dropped=0',result.stdout)
  self.assertIn('advertised_node='+str(node),result.stdout)
  self.assertIn('advertised_port=16480',result.stdout)
 def test_publication_when_remote_node_zero_exists(self):self.check('remote',1)
 def test_publication_without_remote_node(self):self.check('no-remote',1)
 def test_local_node_is_not_hardcoded(self):self.check('node9',9)
if __name__=='__main__':unittest.main(verbosity=2)
