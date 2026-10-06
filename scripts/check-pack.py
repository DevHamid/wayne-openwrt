#!/usr/bin/env python3
"""Real donor-image regression test. Does not boot or flash any device."""
import pathlib
import subprocess
import sys
import tempfile

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
    print("PASS: kernel + ramdisk byte-identical; image bytes:", output.stat().st_size)
