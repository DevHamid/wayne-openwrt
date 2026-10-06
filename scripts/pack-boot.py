#!/usr/bin/env python3
"""Pack one boot image from donor header args, keeping cmdline as one argument."""
import hashlib
import pathlib
import shlex
import subprocess
import sys

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

if len(sys.argv) != 6:
    sys.exit("usage: pack-boot.py MKBOOT_DIR DONOR_IMG KERNEL RAMDISK OUTPUT")
mkboot, donor, kernel, ramdisk, output = map(pathlib.Path, sys.argv[1:6])

r = subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                    "--boot_img", str(donor), "--format", "mkbootimg"],
                   capture_output=True, text=True, check=True)
toks = shlex.split(r.stdout)
clean, skip = [], False
for t in toks:
    if skip:
        skip = False
        continue
    if t in ("--kernel", "--ramdisk"):
        skip = True
        continue
    clean.append(t)

cmdline = clean[clean.index("--cmdline") + 1]
assert " " in cmdline, "cmdline looks fragmented"
assert cmdline.startswith("androidboot.hardware=qcom"), "unexpected cmdline"

subprocess.run([sys.executable, str(mkboot / "mkbootimg.py"), *clean,
                "--kernel", str(kernel), "--ramdisk", str(ramdisk),
                "--output", str(output)], check=True)

verify = output.parent / "verify-tmp"
subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                "--boot_img", str(output), "--out", str(verify)], check=True)
assert sha(verify / "kernel") == sha(kernel), "KERNEL MISMATCH"
assert sha(verify / "ramdisk") == sha(ramdisk), "RAMDISK MISMATCH"
print(f"PASS {output}: kernel+ramdisk byte-identical, cmdline preserved ({len(cmdline)} chars)")
