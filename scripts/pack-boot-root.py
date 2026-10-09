#!/usr/bin/env python3
"""Pack a boot image like pack-boot.py, but REPLACE the Android root= cmdline.

Keeps every androidboot.* / hardware arg the qcom drivers read; swaps the
Android dm-verity root for a real block device (persistent rootfs).

usage: pack-boot-root.py MKBOOT_DIR DONOR_IMG KERNEL RAMDISK OUTPUT ROOTDEV [FSTYPE]
"""
import hashlib, pathlib, re, shlex, subprocess, sys

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

if len(sys.argv) not in (7, 8):
    sys.exit("usage: pack-boot-root.py MKBOOT_DIR DONOR_IMG KERNEL RAMDISK OUTPUT ROOTDEV [FSTYPE]")
mkboot, donor, kernel, ramdisk, output, rootdev = map(pathlib.Path, sys.argv[1:7])
fstype = sys.argv[7] if len(sys.argv) == 8 else "ext4"

r = subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                    "--boot_img", str(donor), "--format", "mkbootimg"],
                   capture_output=True, text=True, check=True)
toks = shlex.split(r.stdout)
clean, skip = [], False
for t in toks:
    if skip: skip = False; continue
    if t in ("--kernel", "--ramdisk"): skip = True; continue
    clean.append(t)

i = clean.index("--cmdline") + 1
old = clean[i]
assert " " in old, "cmdline looks fragmented"
# Presence check, not prefix check: the bootloader may prepend args, so the
# stored cmdline need not start with androidboot.hardware=qcom.
for must in ("androidboot.hardware=qcom",):
    assert must in old, f"donor cmdline lacks {must}"

# Remove the quoted dm="..." FIRST (its value contains spaces, so a naive
# whitespace split leaves 'android-verity' and '/dev/mmcblk0p61"' behind).
new = re.sub(r'\bdm="[^"]*"', '', old)
new = re.sub(r'\broot=\S+', '', new)
new = " ".join(new.split())
new = f"{new} root={rootdev} rootwait rootfstype={fstype}"

# Hard guards on the result.
for must in ("androidboot.hardware=qcom", "androidboot.hwdevice=wayne"):
    assert must in new, f"cmdline lost {must}"
assert "android-verity" not in new, "dm-verity token survived"
assert f"root={rootdev}" in new, "root= not set"

clean[i] = new
subprocess.run([sys.executable, str(mkboot / "mkbootimg.py"), *clean,
                "--kernel", str(kernel), "--ramdisk", str(ramdisk),
                "--output", str(output)], check=True)

verify = output.parent / "verify-root-tmp"
subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                "--boot_img", str(output), "--out", str(verify)], check=True)
assert sha(verify / "kernel") == sha(kernel), "KERNEL MISMATCH"
assert sha(verify / "ramdisk") == sha(ramdisk), "RAMDISK MISMATCH"

back = subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                       "--boot_img", str(output)], capture_output=True, text=True).stdout
assert f"root={rootdev}" in back, "root= did not round-trip"
assert "android-verity" not in back, "dm-verity still in packed image"
print(f"PASS {output}: kernel+ramdisk byte-identical; cmdline root={rootdev} {fstype}; hw identity kept")
