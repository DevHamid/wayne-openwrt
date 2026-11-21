#!/usr/bin/env python3
"""Build/test userspace PDR diagnostic only; never opens a real QRTR socket."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--arm64-cc', required=True)
a = p.parse_args()
wraps = '-Wl,' + ','.join('--wrap='+s for s in ('socket','connect','setsockopt','close','send','recv','recvfrom','kill','readlink'))
checks = []
for variant, cc, flags in [('host','cc',['-O2']), ('sanitizers','cc',['-O1','-g','-fsanitize=address,undefined']), ('arm64',a.arm64_cc,['-O2','-static'])]:
    out = HERE/'build'/variant
    out.mkdir(parents=True, exist_ok=True)
    for src, binary in [('pdr_restart.c','pdr_restart'), ('pdr_fixture.c','pdr-fixture')]:
        cmd = [cc, '-std=gnu11','-Wall','-Wextra','-Werror',*flags,src]
        if binary == 'pdr-fixture': cmd.append(wraps)
        cmd += ['-o',str(out/binary)]
        r = subprocess.run(cmd,cwd=HERE,capture_output=True,text=True)
        (out/(binary+'-build.log')).write_text(r.stdout+r.stderr)
        if r.returncode: sys.exit(r.stdout+r.stderr)
    if variant == 'arm64': continue
    env = dict(os.environ, PDR_FIXTURE=str(out/'pdr-fixture'), PDR_BINARY=str(out/'pdr_restart'), ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    cmd = ['python3','-m','unittest','test_pdr_listener','test_root_state','-v']
    if variant == 'host': cmd.insert(4,'test_pdr')
    r = subprocess.run(cmd,cwd=HERE,env=env,capture_output=True,text=True)
    (out/'pdr-tests.log').write_text(r.stdout+r.stderr)
    print(variant, r.stdout+r.stderr, flush=True)
    if r.returncode: sys.exit(r.returncode)
    checks.append({'variant':variant,'exit_code':r.returncode})
files = ['pdr_restart.c','pdr_fixture.c','test_pdr.py','test_pdr_listener.py','test_root_state.py','build_pdr.py','build/arm64/pdr_restart','build/arm64/pdr-fixture']
record = {'scope':'offline userspace build and wrapped host transport fixtures; ARM64 not yet executed', 'checks':checks, 'sha256':{s:hashlib.sha256((HERE/s).read_bytes()).hexdigest() for s in files}}
(HERE/'build/PDR-CHECKS.json').write_text(json.dumps(record,indent=2)+'\n')
print('PDR userspace builds and host/sanitizer fixtures PASS; target fixture execution still required.')
