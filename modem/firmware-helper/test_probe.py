import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
REFUSAL_PREFIX="#!/bin/sh\n# Offline-only specimen: refuse before any staging or hardware access.\nprintf '%s\\n' 'Unarmed collector specimen; run offline fixtures only.' >&2\nexit 126\n"
SPECIMEN_GUARD='guard() {\n printf "%s\\n" "No native baseline guard is supplied in this specimen." >&2\n return 126\n}'
FIXTURE_GUARD='guard() {\n [ "$(cat /proc/sys/kernel/random/boot_id)" = 00000000-0000-0000-0000-000000000000 ]\n [ "$(cat /sys/bus/msm_subsys/devices/subsys0/state)" = ONLINE ]\n [ "$(cat /sys/bus/msm_subsys/devices/subsys0/crash_count)" = 0 ]\n [ "$(uci -q get wayne-modem.main.allow_boot)" = 0 ]\n [ "$(pidof rmtfs)" = 999999 ]\n [ "$(tr \'\\000\' \' \' </proc/999999/cmdline)" = \'/usr/bin/rmtfs -r -P -o /tmp/wayne-rmtfs -v \' ]\n [ "$(readlink /proc/999999/fd/3)" = /dev/uio0 ]\n for f in enable_ramdumps enable_mini_ramdumps; do\n  [ "$(cat /sys/module/subsystem_restart/parameters/$f)" = 0 ]\n done\n}'
class ProbeLifecycleTest(unittest.TestCase):
 def run_probe(self,case='normal',broken_pipe=False,terminate=False):
  with tempfile.TemporaryDirectory(prefix='tftp-lifecycle-') as name:
   root=Path(name);stage=root/'stage';stage.mkdir();state=root/'state';state.mkdir();tools=root/'tools';tools.mkdir()
   def executable(path,text):path.write_text(text);path.chmod(0o700)
   (state/'boot').write_text('00000000-0000-0000-0000-000000000000\n')
   (state/'modem').write_text('ONLINE\n');(state/'crash').write_text('0\n')
   (state/'gates').mkdir()
   for field in ('enable_ramdumps','enable_mini_ramdumps'):(state/'gates'/field).write_text('0\n')
   (state/'rmtfs/fd').mkdir(parents=True)
   args=b'/usr/bin/rmtfs\0-r\0-P\0-o\0/tmp/wayne-rmtfs\0-v\0'
   if case=='wrong-flags':args=b'/usr/bin/rmtfs\0'
   (state/'rmtfs/cmdline').write_bytes(args)
   (state/'rmtfs/fd/3').symlink_to('/dev/uio0')
   firmware=root/'firmware.mbn';firmware.write_bytes(b'nonempty synthetic firmware for lifecycle only')
   shutil.copyfile(HERE/'build/host/lifecycle-daemon',stage/'tqftpserv-ro');(stage/'tqftpserv-ro').chmod(0o700)
   shutil.copyfile(HERE/'build/host/server-fixture',stage/'server-fixture');(stage/'server-fixture').chmod(0o700)
   shutil.copyfile(HERE/'verify-profiles.awk',stage/'verify-profiles.awk')
   executable(tools/'bb','#!/bin/sh\n[ "$1" = timeout ] || exit 99\nshift\nif [ -n "${TRACE_TEST_TIMEOUT:-}" ]; then exec "$TRACE_TEST_TIMEOUT" timeout "$@"; fi\nexec /usr/bin/timeout "$@"\n')
   executable(tools/'lookup',r'''#!/bin/sh
echo 'Service Version Instance Node Port'
if [ "$1" = 4096 ]; then
 if [ "$LIFE_CASE" = preexisting ]; then echo '4096 1 0 1 55'; exit 0; fi
 if [ -s "$LIFE_STAGE/server.pid" ]; then
  read -r pid < "$LIFE_STAGE/server.pid"
  if kill -0 "$pid" 2>/dev/null; then
   [ "$LIFE_CASE" != bad-lookup ] || exit 6
   if [ "$LIFE_CASE" = wrong-publication ]; then echo '4096 2 0 1 56'; else
    key=1
    while [ "$key" -le 10 ];do echo "4096 $key 0 1 $((55+key))";key=$((key+1));done
   fi
  fi
 fi
fi
''')
   executable(tools/'uci','#!/bin/sh\necho 0\n')
   executable(tools/'pidof','#!/bin/sh\n[ "$1" = rmtfs ] && echo 999999\n')
   executable(tools/'dmesg','#!/bin/sh\necho "[1.00] icnss: synthetic lifecycle event"\n')
   executable(tools/'sleep',r'''#!/bin/sh
if [ "$LIFE_CASE" = crash ] && [ "$1" = 5 ]; then echo 1 > "$LIFE_STATE/crash"; fi
if [ "$LIFE_CASE" = deadline ]; then exec /bin/sleep 0.12; fi
exec /bin/sleep 0.02
''')
   if case in ('preexisting-result','symlink-result'):
    foreign=root/'foreign';foreign.write_text('foreign retain\n')
    if case=='symlink-result':(root/'stage.result').symlink_to(foreign)
    else:(root/'stage.result').write_text('foreign retain\n')
   text=(HERE/'collector-specimen.sh').read_text()
   assert text.startswith(REFUSAL_PREFIX) and text.count(SPECIMEN_GUARD)==1
   text=text[len(REFUSAL_PREFIX):].replace(SPECIMEN_GUARD,FIXTURE_GUARD,1)
   replacements={'/tmp/wayne-tftp-stock-profiles':str(stage),'/bin/busybox-static':str(tools/'bb'),
     '/usr/lib/wayne/radio/qrtr-lookup':str(tools/'lookup'),'/proc/sys/kernel/random/boot_id':str(state/'boot'),
     '/sys/bus/msm_subsys/devices/subsys0/state':str(state/'modem'),'/sys/bus/msm_subsys/devices/subsys0/crash_count':str(state/'crash'),
     '/proc/999999':str(state/'rmtfs'),'/sys/module/subsystem_restart/parameters':str(state/'gates'),
     '/lib/firmware/WLANMDSP.MBN':str(firmware),'/sys/class/ieee80211/phy*':str(root/'phy/phy*'),
     'f77e315414f47a421c6020800a9f54d29f68971998b938243bd5f5f337549f50':hashlib.sha256(firmware.read_bytes()).hexdigest()}
   for old,new in replacements.items():text=text.replace(old,new)
   if case=='deadline':text=text.replace('timeout -k 1 75','timeout -k 1 1')
   script=root/'probe-fixture.sh';script.write_text(text)
   shell=os.environ.get('TRACE_TEST_SHELL','/bin/sh');prefix=[shell,'ash'] if Path(shell).name=='busybox' else [shell]
   paths=[str(tools)]
   if os.environ.get('TRACE_TEST_APPLETS'):paths.append(os.environ['TRACE_TEST_APPLETS'])
   paths.append(os.defpath)
   env=dict(os.environ,LIFE_CASE=case,LIFE_STAGE=str(stage),LIFE_STATE=str(state),LIFE_STARTED=str(root/'started'),PATH=':'.join(paths))
   command=[*prefix,str(script)]
   with (root/'stderr').open('w+') as error:
    if broken_pipe or terminate:
     child=subprocess.Popen(command,env=env,text=True,stdout=subprocess.PIPE,stderr=error)
     assert child.stdout is not None
     lines=[]
     while True:
      line=child.stdout.readline()
      if not line:break
      lines.append(line)
      if line.startswith('server_pid='):break
     if terminate:
      child.terminate();child.wait(timeout=6)
      lines.append(child.stdout.read())
     child.stdout.close();status=child.wait(timeout=6);output=''.join(lines)
    else:
     child=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,stderr=error,timeout=6)
     status,output=child.returncode,child.stdout
    error.seek(0);errors=error.read()
   pidfile=root/'started'
   pid=int(pidfile.read_text()) if pidfile.exists() else None
   if pid is not None:
    try:os.kill(pid,0)
    except ProcessLookupError:pass
    else:self.fail('owned fake daemon survived cleanup')
   self.assertFalse(stage.exists(),'staging survived cleanup')
   journal=root/'stage.result'
   evidence=journal.read_text() if journal.exists() else None
   return status,output,errors,pid,evidence
 def test_normal_capture_and_cleanup(self):
  status,out,err,pid,evidence=self.run_probe();self.assertEqual(status,0,out+err)
  self.assertIn('tftp_probe=complete',out);self.assertEqual(len(re.findall(r'^sample=',out,re.M)),12)
 def test_existing_service_refuses_without_launch(self):
  status,out,err,pid,evidence=self.run_probe('preexisting');self.assertNotEqual(status,0);self.assertIsNone(pid)
 def test_startup_failure_is_not_complete(self):
  status,out,err,pid,evidence=self.run_probe('fail-start');self.assertNotEqual(status,0);self.assertNotIn('tftp_probe=complete',out)
 def test_failed_publication_lookup_cleans_daemon(self):
  status,out,err,pid,evidence=self.run_probe('bad-lookup');self.assertNotEqual(status,0);self.assertNotIn('tftp_probe=complete',out)
 def test_crash_baseline_change_aborts(self):
  status,out,err,pid,evidence=self.run_probe('crash');self.assertNotEqual(status,0);self.assertNotIn('tftp_probe=complete',out)
 def test_expired_server_cannot_give_complete_capture(self):
  status,out,err,pid,evidence=self.run_probe('deadline');self.assertNotEqual(status,0,out+err);self.assertNotIn('tftp_probe=complete',out)
 def test_closed_stdout_pipe_still_cleans(self):
  status,out,err,pid,evidence=self.run_probe(broken_pipe=True);self.assertNotEqual(status,0);self.assertIsNotNone(pid)
 def test_wrong_backing_flags_refuse_before_start(self):
  status,out,err,pid,evidence=self.run_probe('wrong-flags');self.assertNotEqual(status,0);self.assertIsNone(pid)
 def test_interrupted_capture_retains_private_summary(self):
  status,out,err,pid,evidence=self.run_probe(broken_pipe=True)
  self.assertNotEqual(status,0);self.assertIsNotNone(evidence)
  assert evidence is not None
  self.assertIn('tftp_read_opens=1',evidence);self.assertIn('probe_cleanup=complete',evidence)
  self.assertNotIn('private-identifier',evidence)
 def test_existing_journal_is_never_overwritten(self):
  status,out,err,pid,evidence=self.run_probe('preexisting-result')
  self.assertNotEqual(status,0);self.assertIsNone(pid);self.assertEqual(evidence,'foreign retain\n')
 def test_symlink_journal_is_never_followed(self):
  status,out,err,pid,evidence=self.run_probe('symlink-result')
  self.assertNotEqual(status,0);self.assertIsNone(pid);self.assertEqual(evidence,'foreign retain\n')
 def test_term_signal_cleans_and_retains_evidence(self):
  status,out,err,pid,evidence=self.run_probe(terminate=True)
  self.assertNotEqual(status,0);self.assertIsNotNone(pid);self.assertIsNotNone(evidence)
  assert evidence is not None
  self.assertIn('probe_cleanup=complete',evidence);self.assertIn('tftp_read_opens=1',evidence)
  self.assertNotIn('tftp_probe=complete',evidence)
 def test_startup_failure_retains_error_class_and_exit(self):
  status,out,err,pid,evidence=self.run_probe('fail-start')
  self.assertNotEqual(status,0);assert evidence is not None
  self.assertIn('tftp_socket_open_errors=1',evidence);self.assertIn('server_exit_status=2',evidence)
 def test_unexpected_publication_tuple_is_preserved(self):
  status,out,err,pid,evidence=self.run_probe('wrong-publication')
  self.assertNotEqual(status,0);assert evidence is not None
  self.assertIn('observed_service=4096 version=2 instance=0 node=1 port=56',evidence)
 def test_public_specimen_refuses_before_touching_staging(self):
  with tempfile.TemporaryDirectory(prefix='collector-unarmed-') as name:
   root=Path(name);stage=root/'stage';stage.mkdir();sentinel=stage/'keep';sentinel.write_text('unchanged')
   text=(HERE/'collector-specimen.sh').read_text().replace('/tmp/wayne-tftp-stock-profiles',str(stage))
   script=root/'unarmed.sh';script.write_text(text)
   shell=os.environ.get('TRACE_TEST_SHELL','/bin/sh');prefix=[shell,'ash'] if Path(shell).name=='busybox' else [shell]
   result=subprocess.run([*prefix,str(script)],capture_output=True,text=True,timeout=5)
   self.assertEqual(result.returncode,126,result.stdout+result.stderr)
   self.assertEqual(sentinel.read_text(),'unchanged');self.assertNotIn('firmware_service=published',result.stdout)
if __name__=='__main__':unittest.main(verbosity=2)
