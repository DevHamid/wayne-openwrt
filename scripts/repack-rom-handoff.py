#!/usr/bin/env python3
"""Repack the split-ROM bootstrap, preserving the exact CI kernel and rootfs."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '772e6bbd0a0d9800b865e39a65ae4801489c2ec6dce73c00035125112dbbdd90'
spec = importlib.util.spec_from_file_location('assembly', BASE / 'scripts/assemble-2410.py')
assert spec is not None and spec.loader is not None
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source, output):
    archive = source / 'build/wayne-openwrt-rom.zip'
    assert digest(archive.read_bytes()) == SOURCE_SHA256, 'Unexpected source ROM ZIP'
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, 'Corrupt source ZIP'
        old_boot = z.read('boot/boot.img')
    kernel, ramdisk = assembly.boot_parts(old_boot)
    entries = list(assembly.newc(gzip.decompress(ramdisk)))
    for name, mode, data in entries:
        assert stat.S_ISDIR(mode) or stat.S_ISREG(mode) or stat.S_ISLNK(mode)
        assembly.write_entry(output / 'bootstrap', name, mode, data)
    init = (BASE / 'overlay-system/init').read_bytes()
    assert b'\nexec switch_root "$MNT" /sbin/init' in init
    assert b'[ -x "$MNT/sbin/init" ]' in init
    (output / 'bootstrap/init').write_bytes(init)
    (output / 'bootstrap/init').chmod(0o755)
    (output / 'kernel').write_bytes(kernel)
    (output / 'source-boot.img').write_bytes(old_boot)
    print('Prepared pinned bootstrap; kernel and rootfs will be reused unchanged')


def finish(source, output):
    ramdisk = output / 'bootstrap-initramfs.cpio.gz'
    subprocess.run([
        sys.executable, str(BASE / 'scripts/pack-boot.py'), 'mkboot',
        str(output / 'source-boot.img'), str(output / 'kernel'), str(ramdisk),
        str(output / 'rom-boot.img'),
    ], check=True)
    boot = (output / 'rom-boot.img').read_bytes()
    kernel, packed_ramdisk = assembly.boot_parts(boot)
    assert len(boot) < 32 * 1024 * 1024
    assert kernel == (output / 'kernel').read_bytes()
    assert packed_ramdisk == ramdisk.read_bytes()
    packed = {n: (m, d) for n, m, d in assembly.newc(gzip.decompress(packed_ramdisk))}
    assert packed['init'][1] == (BASE / 'overlay-system/init').read_bytes()
    assert packed['usb-gadget.sh'][1] == (BASE / 'overlay-common/usb-gadget.sh').read_bytes()
    original = source / 'build/wayne-openwrt-rom.zip'
    target = output / 'wayne-openwrt-rom.zip'
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(target, 'w') as dst:
        for entry in src.infolist():
            payload = boot if entry.filename == 'boot/boot.img' else src.read(entry)
            dst.writestr(entry, payload)
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(target) as dst:
        assert dst.testzip() is None
        assert src.namelist() == dst.namelist()
        for name in src.namelist():
            if name != 'boot/boot.img':
                assert src.read(name) == dst.read(name), 'Unexpected change: ' + name
        rootfs = dst.read('system/rootfs.tar.gz')
    report = {
        'check': 'PASS', 'source_run': '44445539855',
        'source_zip_sha256': SOURCE_SHA256,
        'kernel_unchanged': True, 'rootfs_unchanged': True,
        'recovery_scripts_unchanged': True,
        'rootfs_sha256': digest(rootfs), 'boot_bytes': len(boot),
        'bootstrap_init_sha256': digest(packed['init'][1]),
        'zip_sha256': digest(target.read_bytes()),
        'limits': ['No device boot test; userdata persistence unfinished'],
    }
    (output / 'VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'finish'])
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else finish)(args.source, args.output)
