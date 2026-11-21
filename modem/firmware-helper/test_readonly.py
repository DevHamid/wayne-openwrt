import os
from pathlib import Path
import subprocess,tempfile,unittest
HERE=Path(__file__).resolve().parent
class ReadonlyPolicyTest(unittest.TestCase):
 def invoke(self,request,flags=0,link=False):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name)/'firmware';root.mkdir()
   data=root/'wlanmdsp.mbn'
   if link:
    secret=Path(name)/'outside';secret.write_text('do not serve')
    data.symlink_to(secret)
   else:data.write_text('reviewed firmware fixture')
   os.link(data,root/'WLANMDSP.MBN',follow_symlinks=False)
   command=os.environ.get('POLICY_FIXTURE',str(HERE/'build/host/policy-fixture'))
   result=subprocess.run([command,str(root),request,str(flags)],capture_output=True,text=True,timeout=5)
   self.assertFalse((root/'server_check.txt').exists())
   return result
 def test_exact_firmware_read_without_remoteproc(self):
  r=self.invoke('/readonly/firmware/image/wlanmdsp.mbn')
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(r.stdout,'read=reviewed firmware fixture\n')
 def test_only_reviewed_firmware_paths_are_readable(self):
  for path in ('/readwrite/server_check.txt','/readonly/firmware/image/../../etc/passwd',
               '/readonly/firmware/image//wlanmdsp.mbn','/readonly/firmware/image/modemst1',
               '/etc/passwd','wlanmdsp.mbn','/readonly/firmware/image/wlanmdsp.mbn/extra'):
   with self.subTest(path=path):
    r=self.invoke(path);self.assertEqual(r.returncode,3,r.stdout+r.stderr)
 def test_all_write_flags_are_denied(self):
  for flag in (os.O_WRONLY,os.O_RDWR,os.O_CREAT,os.O_TRUNC,os.O_APPEND):
   with self.subTest(flag=flag):
    r=self.invoke('/readonly/firmware/image/wlanmdsp.mbn',flag)
    self.assertEqual(r.returncode,3,r.stdout+r.stderr)
 def test_symlink_firmware_is_refused(self):
  r=self.invoke('/readonly/firmware/image/wlanmdsp.mbn',link=True)
  self.assertEqual(r.returncode,3,r.stdout+r.stderr)
 def test_fifo_is_rejected_without_blocking(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);os.mkfifo(root/'wlanmdsp.mbn')
   command=os.environ.get('POLICY_FIXTURE',str(HERE/'build/host/policy-fixture'))
   try:r=subprocess.run([command,str(root),'/readonly/firmware/image/wlanmdsp.mbn','0'],capture_output=True,text=True,timeout=1)
   except subprocess.TimeoutExpired:self.fail('non-regular firmware open blocked')
   self.assertEqual(r.returncode,3,r.stdout+r.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
