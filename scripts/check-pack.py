#!/usr/bin/env python3
"""Real donor-image regression test. Does not boot or flash any device."""
import pathlib
import shlex
import subprocess
import sys
import tempfile


def _cmdline(mkboot, img):
    args = subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                           "--boot_img", str(img), "--format", "mkbootimg"],
                          capture_output=True, text=True, check=True).stdout
    toks = shlex.split(args)
    return toks[toks.index("--cmdline") + 1]

packer = pathlib.Path(__file__).with_name("pack-boot.py")
assert packer.is_file(), "Missing safe argument-list packer"
assert len(sys.argv) == 5, "Usage: check-pack.py MKBOOT_DIR DONOR KERNEL RAMDISK"
mkboot, donor, kernel, ramdisk = map(lambda s: pathlib.Path(s).resolve(), sys.argv[1:])
with tempfile.TemporaryDirectory(dir=donor.parent, prefix="pack-check-") as tmp:
    tmp = pathlib.Path(tmp)
    output = tmp / "test.img"
    subprocess.run([sys.executable, str(packer), str(mkboot), str(donor),
                    str(kernel), str(ramdisk), str(output)], check=True)
    assert output.read_bytes()[:8] == b"ANDROID!", "Bad boot image magic"
    subprocess.run([sys.executable, str(mkboot / "unpack_bootimg.py"),
                    "--boot_img", str(output), "--out", str(tmp / "verify")],
                   check=True, stdout=subprocess.DEVNULL)
    for name, source in (("kernel", kernel), ("ramdisk", ramdisk)):
        assert (tmp / "verify" / name).read_bytes() == source.read_bytes(), name + " mismatch"
    assert output.stat().st_size < 64 * 1024 * 1024, "Exceeds assumed 64 MiB boot ceiling"
    # THE guard that matters: no root=/dm= may reach the kernel. An appended
    # root= is what made the v0.9 installer reboot the phone.
    want, got = _cmdline(mkboot, donor), _cmdline(mkboot, output)
    assert "root=" not in got, "packed cmdline contains root= : %s" % got
    assert want == got, "cmdline changed:\n  donor : %s\n  packed: %s" % (want, got)
    print("PASS: kernel + ramdisk byte-identical; cmdline == donor (%d chars, no root=); image %d bytes"
          % (len(got), output.stat().st_size))
