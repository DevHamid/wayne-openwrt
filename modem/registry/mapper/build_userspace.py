#!/usr/bin/env python3
"""Build only the userspace mapper and its socket-intercepting fixture."""
import argparse
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--qrtr-source', type=Path, required=True)
parser.add_argument('--lzma-include', type=Path)
parser.add_argument('--lzma-library', default='-llzma')
parser.add_argument('--cc', default='cc')
parser.add_argument('--out', type=Path, default=HERE / 'build')
parser.add_argument('--static', action='store_true')
parser.add_argument('--sanitize', action='store_true')
args = parser.parse_args()
qrtr = args.qrtr_source.resolve()
source = HERE / 'source'
args.out.mkdir(parents=True, exist_ok=True)
flags = ['-std=gnu11', '-O1' if args.sanitize else '-O2', '-g', '-Wall',
         '-I' + str(qrtr / 'include'), '-I' + str(qrtr / 'lib')]
if args.lzma_include:
    flags.append('-I' + str(args.lzma_include.resolve()))
if args.static:
    flags.append('-static')
if args.sanitize:
    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
common = [str(source / name) for name in ('assoc.c', 'json.c', 'servreg_loc.c', 'lzma_decomp.c')]
common += [str(qrtr / 'lib' / name) for name in ('qrtr.c', 'qmi.c', 'logging.c')]
for target, main, links in (
    ('pd-mapper', source / 'pd-mapper.c', []),
    ('mapper-fixture', HERE / 'mapper_fixture.c', ['-Wl,--wrap=socket,--wrap=getsockname,--wrap=sendto']),
):
    command = [args.cc, *flags, str(main), *common, *links, args.lzma_library,
               '-lpthread', '-o', str(args.out / target)]
    subprocess.run(command, check=True)
    print('built', args.out / target)
