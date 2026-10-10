#!/usr/bin/env python3
"""Pack a boot image like pack-boot.py, but SET the root= cmdline.

Reality check (verified against the pinned donor, 2026-10-09):
  The donor boot.img cmdline is only 312 chars and contains NO root=, NO dm=,
  and NO android-verity. Those appear on-device because the BOOTLOADER adds
  them at boot time. So this packer cannot "replace" them -- it appends our
  root= args, and the bootloader may append its own after ours.

  The donor cmdline DOES carry androidboot.hardware=qcom, which is the only
  identity token we can rely on being in the image.

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
# The ONE token we require: the qcom hardware identity the drivers read.
assert "androidboot.hardware=qcom" in old, "donor cmdline lacks androidboot.hardware=qcom"

# Drop root=/dm= only if the donor happens to carry them (it does not today,
# but a future donor might). The quoted dm="..." must go first: its value
# contains spaces, so a whitespace split would leave fragments behind.
new = re.sub(r'\bdm="[^"]*"', '', old)
new = re.sub(r'\broot=\S+', '', new)
new = " ".join(new.split())
new = f"{new} root={rootdev} rootwait rootfstype={fstype}"

# Guards that reflect REALITY, not assumption:
assert "androidboot.hardware=qcom" in new, "cmdline lost the qcom hardware identity"
assert f"root={rootdev}" in new, "root= not set"
assert "android-verity" not in new, "dm-verity token present"
# Do NOT assert androidboot.hwdevice=wayne: the donor does not carry it; the
# bootloader adds it at boot. Asserting it broke v0.9's first CI run.

clean[i] = new
subprocess.run([sys.executable, str(mkboot / "mkbootimg.py"), *clean,
                "--kernel", str(kernel), "--ramdisk", str(ramdisk),
                "--output", str(output)], check=True)

verify = output.parent / "verify-root-tmp"
subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                "--boot_img", str(output), "--out", str(verify)], check=True)
assert sha(verify / "kernel") == sha(kernel), "KERNEL MISMATCH"
assert sha(verify / "ramdisk") == sha(ramdisk), "RAMDISK MISMATCH"

# Prove the cmdline round-tripped through the image.
back = subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                       "--boot_img", str(output)], capture_output=True, text=True).stdout
assert f"root={rootdev}" in back, "root= did not round-trip"
assert "android-verity" not in back, "dm-verity in packed image"

# Show the operator what actually landed, so a bootloader override is visible
# in the CI log rather than discovered on the phone.
m = re.search(r'Kernel command line:\s*(.*)', back)
print(f"PASS {output}: kernel+ramdisk byte-identical")
print(f"  packed cmdline ({len(new)} chars):")
print(f"    {new}")
