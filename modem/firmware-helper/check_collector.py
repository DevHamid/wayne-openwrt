#!/usr/bin/env python3
"""Run synthetic collector fixtures only; the public specimen is unarmed."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cc', default='cc')
parser.add_argument('--target-shell')
parser.add_argument('--target-applets', type=Path)
parser.add_argument('--target-timeout')
args = parser.parse_args()
target = (args.target_shell, args.target_applets, args.target_timeout)
if any(target) and not all(target):
    parser.error('supply all three --target-* options or none')
out = HERE / 'build'
(out / 'host').mkdir(parents=True, exist_ok=True)
base_env = dict(os.environ)
for key in ('TRACE_TEST_SHELL', 'TRACE_TEST_APPLETS', 'TRACE_TEST_TIMEOUT', 'PROFILE_TEST_AWK'):
    base_env.pop(key, None)
commands = [
    ('collector-build', [args.cc, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                         '-O2', 'lifecycle_daemon.c', '-o', 'build/host/lifecycle-daemon'], {}),
    ('collector-syntax', ['sh', '-n', 'collector-specimen.sh'], {}),
    ('collector-host', ['python3', '-m', 'unittest', 'test_probe', 'test_profiles', '-v'], {}),
]
if all(target):
    commands.append(('collector-target',
                     ['python3', '-m', 'unittest', 'test_probe', 'test_profiles', '-v'],
                     {'TRACE_TEST_SHELL': args.target_shell,
                      'TRACE_TEST_APPLETS': str(args.target_applets),
                      'TRACE_TEST_TIMEOUT': args.target_timeout,
                      'PROFILE_TEST_AWK': str(args.target_applets / 'awk')}))
checks = []
for label, command, extra in commands:
    result = subprocess.run(command, cwd=HERE, env=dict(base_env, **extra),
                            capture_output=True, text=True, timeout=45)
    (out / (label + '.log')).write_text(result.stdout + result.stderr)
    checks.append({'label': label, 'command': shlex.join(command),
                   'status': result.returncode, 'environment': extra,
                   'timestamp': datetime.now(timezone.utc).isoformat()})
    print(label, 'PASS' if result.returncode == 0 else 'FAIL', flush=True)
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
import test_probe
import test_profiles
record = {'scope': 'synthetic paths/fake daemon; specimen refusal stripped only inside fixtures',
          'lifecycle_cases': unittest.defaultTestLoader.loadTestsFromModule(test_probe).countTestCases(),
          'profile_cases': unittest.defaultTestLoader.loadTestsFromModule(test_profiles).countTestCases(),
          'target_checked': bool(args.target_shell), 'checks': checks}
(out / 'COLLECTOR-CHECKS.json').write_text(json.dumps(record, indent=2) + '\n')
