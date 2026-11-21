#!/usr/bin/env python3
"""Build userspace helpers and run offline fixtures; never contacts a device."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cc', default='cc')
parser.add_argument('--qrtr-source', type=Path, default=HERE / 'vendor/qrtr')
parser.add_argument('--arm64-cc')
parser.add_argument('--qemu')
args = parser.parse_args()
if bool(args.arm64_cc) != bool(args.qemu):
    parser.error('--arm64-cc and --qemu must be supplied together')
q = args.qrtr_source.resolve()
dependencies = json.loads((HERE / 'vendor/QRTR-INPUTS.json').read_text())
for name, expected in dependencies['files'].items():
    if hashlib.sha256((q / name).read_bytes()).hexdigest() != expected:
        raise SystemExit('QRTR dependency hash mismatch: ' + name)
if dependencies['archive_comparison_mismatches']:
    raise SystemExit('Dependency snapshot differs from its pinned upstream archive')

variants = [('host', args.cc, ['-O2']),
            ('sanitizers', args.cc, ['-O1', '-g', '-fsanitize=address,undefined',
                                    '-fno-omit-frame-pointer'])]
if args.arm64_cc:
    variants.append(('arm64', args.arm64_cc, ['-O2', '-static']))
wraps = ['calloc', 'socket', 'bind', 'connect', 'setsockopt', 'getsockname',
         'close', 'send', 'sendto', 'select', 'recvfrom']
link = '-Wl,' + ','.join('--wrap=' + name for name in wraps)
checks = []

def run(command, label, env=None):
    command = [str(value) for value in command]
    result = subprocess.run(command, cwd=HERE, env=env, capture_output=True,
                            text=True, timeout=90)
    (HERE / 'build' / (label + '.log')).write_text(result.stdout + result.stderr)
    checks.append({'label': label, 'command': shlex.join(command),
                   'status': result.returncode,
                   'timestamp': datetime.now(timezone.utc).isoformat()})
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)

(HERE / 'build').mkdir(exist_ok=True)
for variant, cc, flags in variants:
    out = HERE / 'build' / variant
    out.mkdir(exist_ok=True)
    base = [cc, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', *flags, '-Isource',
            '-I' + str(q / 'lib'), '-I' + str(q / 'include')]
    run([*base, 'policy_fixture.c', 'source/translate.c', '-o', out / 'policy-fixture'],
        variant + '-build-policy')
    common = ['source/translate.c', 'source/qrtr-compat.c', q / 'lib/logging.c']
    run([*base, 'server_fixture.c', *common, link, '-o', out / 'server-fixture'],
        variant + '-build-server')
    run([*base, 'source/tqftpserv.c', *common, '-o', out / 'tqftpserv-ro'],
        variant + '-build-daemon')
    run([*base, 'publish_fixture.c', 'source/qrtr-compat.c', q / 'lib/logging.c',
         '-Wl,--wrap=getsockname,--wrap=sendto', '-o', out / 'publish-fixture'],
        variant + '-build-publisher')
    # Only the unmodified reference code gets these diagnostic exceptions.
    reference = ['-Wno-sign-compare']
    major = int(subprocess.check_output([cc, '-dumpversion'], text=True).split('.')[0])
    if major >= 14:
        reference.append('-Wno-calloc-transposed-args')
    run([*base, *reference, '-ffunction-sections', '-fdata-sections',
         '-DNS_SOURCE="' + str(q / 'src/ns.c') + '"', 'namespace_fixture.c',
         q / 'src/map.c', q / 'src/hash.c', q / 'lib/logging.c',
         '-Wl,--gc-sections,--wrap=socket,--wrap=bind,--wrap=sendto',
         '-o', out / 'namespace-fixture'], variant + '-build-namespace')
    binaries = {key: str(out / name) for key, name in [
        ('POLICY_FIXTURE', 'policy-fixture'), ('SERVER_FIXTURE', 'server-fixture'),
        ('PUBLISH_FIXTURE', 'publish-fixture'), ('NAMESPACE_FIXTURE', 'namespace-fixture')]}
    if variant == 'arm64':
        for key, binary in list(binaries.items()):
            wrapper = out / (Path(binary).name + '-qemu')
            wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(args.qemu) + ' ' +
                               shlex.quote(binary) + ' "$@"\n')
            wrapper.chmod(0o700)
            binaries[key] = str(wrapper)
    env = dict(os.environ, **binaries)
    if variant == 'sanitizers':
        env['ASAN_OPTIONS'] = 'detect_leaks=1:abort_on_error=1'
        env['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    run(['python3', '-m', 'unittest', 'test_readonly', 'test_server',
         'test_publish', 'test_namespace', '-v'], variant + '-tests', env)
    print(variant + ': offline protocol/publication/namespace checks PASS', flush=True)

record = {'scope': 'offline userspace fixtures; no native activation',
          'checks': checks, 'variants': [item[0] for item in variants]}
(HERE / 'build/CHECKS.json').write_text(json.dumps(record, indent=2) + '\n')
