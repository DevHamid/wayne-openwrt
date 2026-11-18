#!/usr/bin/env python3
"""Fail if a packed 24.10 image omits required Wayne debug components."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat

spec = importlib.util.spec_from_file_location('assembly', Path(__file__).with_name('assemble-2410.py'))
assert spec is not None and spec.loader is not None
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def check(image_path, source_kernel, expected_ujail=None):
    kernel, ramdisk = assembly.boot_parts(image_path.read_bytes())
    assert kernel == source_kernel.read_bytes(), 'Kernel payload changed'
    assert image_path.stat().st_size < 32 * 1024 * 1024, 'Debug boot image exceeds conservative 32 MiB limit'
    files = {name: (mode, data) for name, mode, data in assembly.newc(gzip.decompress(ramdisk))}
    required = [
        'init', 'sbin/init', 'sbin/procd', 'usr/libexec/login.sh', 'bin/busybox-static',
        'usr/bin/rmtfs', 'etc/init.d/rmtfs', 'etc/init.d/modem-boot-trigger',
        'root/screen.sh', 'etc/init.d/burnin-guard', 'etc/config/wayne-modem',
        'usr/sbin/iw', 'usr/bin/iwinfo', 'usr/sbin/wpad', 'etc/init.d/wpad',
        'sbin/wifi', 'lib/wifi/mac80211.uc', 'usr/share/hostap/wifi-detect.uc', 'etc/wayne-build.json',
        'lib/firmware/wlan/qca_cld/wlanmdsp.mbn',
        'lib/firmware/wlan/qca_cld/bdwlan30.bin',
    ]
    # wifi-scripts uses a directory; gate it by a payload beneath it as well.
    for name in required:
        assert name in files, f'Missing {name}'
    tab = files['etc/inittab'][1]
    assembly.validate_console(tab)
    assert files['usr/libexec/login.sh'][0] & 0o111, 'Login script is not executable'
    assert b'USE_PROCD=1' in files['etc/init.d/rmtfs'][1]
    assert b'start_service()' in files['etc/init.d/rmtfs'][1]
    assert b' -r -P ' in files['etc/init.d/rmtfs'][1], 'Read-only backing lost'
    assert b"option allow_boot '0'" in files['etc/config/wayne-modem'][1]
    assert 'etc/uci-defaults/11-anonmount' not in files, 'Internal RW automount default remains enabled'
    assert b"option anon_mount '0'" in files['etc/config/fstab'][1]
    for svc, number in [('rmtfs', 95), ('usb-gadget', 95), ('modem-boot-trigger', 97), ('burnin-guard', 99), ('wpad', 19)]:
        mode, target = files[f'etc/rc.d/S{number}{svc}']
        assert stat.S_ISLNK(mode) and target == ('../init.d/' + svc).encode(), f'Bad service link {svc}'
    provenance = json.loads(files['etc/wayne-build.json'][1])
    assert provenance['rootfs'] == '24.10.4'
    assert provenance['kernel_sha256'] == hashlib.sha256(kernel).hexdigest()
    if expected_ujail is not None:
        mode, binary = files['sbin/ujail']
        assert stat.S_ISREG(mode) and mode & 0o111, 'Packed ujail is not executable'
        assert provenance['ujail']['package_sha256'] == hashlib.sha256(expected_ujail.read_bytes()).hexdigest()
        assert provenance['ujail']['binary_sha256'] == hashlib.sha256(binary).hexdigest()
        assert b'kernel does not support capability %d; skipping' in binary, 'Patched ujail missing from image'
        required.append('sbin/ujail')
    kv = provenance['kernel_banner'].split()[2]
    mod = f'lib/modules/{kv}/kernel/drivers/soc/qcom/modem-boot.ko'
    assert mod in files, 'Matching modem module absent'
    assert b'vermagic=' + kv.encode() + b' ' in files[mod][1], 'Module/kernel version mismatch'
    assert provenance['modem_module_sha256'] == hashlib.sha256(files[mod][1]).hexdigest()
    assert stat.S_ISLNK(files[f'lib/modules/{kv}/modem-boot.ko'][0]), 'Flat loader alias missing'
    for name in ('backlight', 'qcom-spmi-wled'):
        assert f'lib/modules/{kv}/kernel/drivers/video/backlight/{name}.ko' in files, f'Missing {name} module'
    assert b'ensure_backlight' in files['root/screen.sh'][1]
    assert b'procd burnin-guard' in files['root/screen.sh'][1]
    foreign = [n for n in files if n.startswith('lib/modules/') and len(n.split('/')) > 2 and n.split('/')[2] != kv]
    assert not foreign, f'Foreign module trees: {foreign[:3]}'
    for name, (mode, data) in files.items():
        if name.endswith('wlan_mac.bin'):
            assert data, 'Empty placeholder WLAN MAC file shipped'
    print(json.dumps({'check': 'PASS', 'image': image_path.name, 'bytes': image_path.stat().st_size,
                      'kernel_unchanged': True, 'components': required,
                      'sha256': hashlib.sha256(image_path.read_bytes()).hexdigest()}, indent=2))
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--expected-ujail', type=Path)
    args = parser.parse_args()
    check(args.image, args.kernel, args.expected_ujail)
