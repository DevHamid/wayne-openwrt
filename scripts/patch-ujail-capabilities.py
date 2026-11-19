#!/usr/bin/env python3
"""Validate a procd ujail capability probe and clamp unsupported kernel caps."""
import re
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text()
# PR_CAPBSET_READ: 0 means unsupported/absent; -1/EINVAL means the kernel
# does not recognize this capability number. Both mean never DROP it.
old = '''\t\tfor (cap = 0; cap <= CAP_LAST_CAP; cap++) {
\t\t\tif (!prctl(PR_CAPBSET_READ, cap, 0, 0, 0)) {
\t\t\t\t/* can't raise */
\t\t\t\tif (ocicapset.bounding & (1LLU << cap))
\t\t\t\t\tERROR("capability %s (%d) is not in bounding set\\n", capabilities_names[cap], cap);

\t\t\t\tcontinue;
\t\t\t}
'''
new = '''\t\tfor (cap = 0; cap <= CAP_LAST_CAP; cap++) {
\t\t\terrno = 0;
\t\t\tint in_bounding = prctl(PR_CAPBSET_READ, cap, 0, 0, 0);
\t\t\tif (in_bounding < 0 && errno == EINVAL) {
\t\t\t\tDEBUG("kernel does not support capability %d; skipping\\n", cap);
\t\t\t\tcontinue;
\t\t\t}
\t\t\tif (in_bounding == 0) {
\t\t\t\t/* absent from bounding set: keep failure semantics */
\t\t\t\tif (ocicapset.bounding & (1LLU << cap))
\t\t\t\t\tERROR("capability %s (%d) is not in bounding set\\n", capabilities_names[cap], cap);
\t\t\t\tcontinue;
\t\t\t}
'''
count=source.count(old)
assert count == 1, f'expected unique bounding-set block, got {count}'
source=source.replace(old,new)
# Ambient capability queries likewise return EINVAL for a number newer
# than the running kernel understands. Skip unsupported ambient indices.
old2='''\t\tfor (cap = 0; cap <= CAP_LAST_CAP; cap++) {
\t\t\tis_set = prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_IS_SET, cap, 0, 0);
\t\t\tif ( (ocicapset.ambient & (1LLU << cap)) == 0) {
'''
new2='''\t\tfor (cap = 0; cap <= CAP_LAST_CAP; cap++) {
\t\t\terrno = 0;
\t\t\tis_set = prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_IS_SET, cap, 0, 0);
\t\t\tif (is_set < 0 && errno == EINVAL) {
\t\t\t\tDEBUG("kernel does not support ambient capability %d; skipping\\n", cap);
\t\t\t\tcontinue;
\t\t\t}
\t\t\tif (is_set < 0) {
\t\t\t\tERROR("PR_CAP_AMBIENT_IS_SET(%d) failed: %m\\n", cap);
\t\t\t\treturn errno;
\t\t\t}
\t\t\tif ( (ocicapset.ambient & (1LLU << cap)) == 0) {
'''
count=source.count(old2)
assert count == 1, f'expected unique ambient block, got {count}'
source=source.replace(old2,new2)
assert 'kernel does not support capability %d; skipping' in source
assert 'kernel does not support ambient capability %d; skipping' in source
Path(sys.argv[2]).write_text(source)
print('patched capability probing; confinement masks unchanged; EINVAL unsupported-cap paths skip safely')
