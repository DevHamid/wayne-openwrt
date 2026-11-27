#!/usr/bin/env python3
"""Assemble 24.10 userspace with the proven vendor kernel's matching modules."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tarfile
import urllib.request
import zlib

VERSION = '24.10.4'
ROOTFS_URL = ('https://downloads.immortalwrt.org/releases/24.10.4/targets/armsr/armv8/'
              'immortalwrt-24.10.4-armsr-armv8-rootfs.tar.gz')
ROOTFS_SHA256 = '16e1cd7c5dfb4b944119024843612b39afc1e6980383c6114a5966cca1b77fc5'
BASE = 'https://downloads.immortalwrt.org/releases/24.10.4/packages/aarch64_generic/base/'
# ImmortalWrt 24.10 is the MANDATORY baseline for this project (operator
# directive, 2026-11-24). Never assemble or ship a 21.02-era rootfs; the CI
# gate asserts the assembled rootfs reports rootfs == '24.10.4' in
# etc/wayne-build.json. Downgrades are a build failure by design.
REQUIRED_ROOTFS = '24.10.4'
# Package repositories searched when injecting extra userspace. modemmanager
# and friends live in the community `packages` feed, the LuCI protocol handler
# in `luci`; only `ppp` comes from `base`.
PKG_REPOS = {
    'base': BASE,
    'packages': 'https://downloads.immortalwrt.org/releases/24.10.4/packages/aarch64_generic/packages/',
    'luci': 'https://downloads.immortalwrt.org/releases/24.10.4/packages/aarch64_generic/luci/',
}
assert VERSION == REQUIRED_ROOTFS, (
    f'ImmortalWrt {REQUIRED_ROOTFS} is the mandatory baseline; refusing to assemble {VERSION}. '
    'Do not downgrade to 21.02 — update REQUIRED_ROOTFS only with an explicit operator decision.')


def fetch(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def newc(data):
    pos = 0
    while pos + 110 <= len(data):
        h = data[pos:pos + 110]
        if h[:6] not in (b'070701', b'070702'):
            raise ValueError(f'Invalid newc header at {pos}')
        v = [int(h[j:j + 8], 16) for j in range(6, 110, 8)]
        pos += 110
        name = data[pos:pos + v[11] - 1].decode().removeprefix('./')
        pos = (pos + v[11] + 3) & ~3
        payload = data[pos:pos + v[6]]
        pos = (pos + v[6] + 3) & ~3
        if name == 'TRAILER!!!':
            return
        if name.startswith('/') or '..' in Path(name).parts:
            raise ValueError(f'Unsafe archive path {name}')
        yield name, v[1], payload
    raise ValueError('CPIO has no trailer')


def boot_parts(image):
    if image[:8] != b'ANDROID!':
        raise ValueError('Not Android boot image')
    ks, rs, page = (struct.unpack_from('<I', image, n)[0] for n in (8, 16, 36))
    if page < 512 or page & (page - 1):
        raise ValueError('Invalid boot page size')
    rd = page + ((ks + page - 1) // page) * page
    return image[page:page + ks], image[rd:rd + rs]


def write_entry(root, name, mode, data):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if stat.S_ISDIR(mode):
        p.mkdir(exist_ok=True)
    elif stat.S_ISREG(mode):
        p.write_bytes(data)
        p.chmod(stat.S_IMODE(mode))
    elif stat.S_ISLNK(mode):
        target = data.decode()
        if p.is_symlink() or p.exists():
            p.unlink()
        p.symlink_to(target)
    else:
        raise ValueError(f'Unexpected special file {name}')


def package_fields(text):
    for paragraph in text.strip().split('\n\n'):
        fields = dict(l.split(': ', 1) for l in paragraph.splitlines()
                      if ': ' in l and not l.startswith(' '))
        if fields.get('Package'):
            yield fields


def install_wifi(root):
    status = root / 'usr/lib/opkg/status'
    old = list(package_fields(status.read_text()))
    installed = {p['Package']: p for p in old}
    index = {p['Package']: p for p in package_fields(gzip.decompress(fetch(BASE + 'Packages.gz')).decode())}
    requested = ['iw', 'iwinfo', 'wpad-basic-mbedtls', 'wifi-scripts', 'wireless-regdb']
    added, visiting = {}, set()

    def install(name):
        if name in installed or name in added:
            return
        if name in visiting:
            raise ValueError(f'Dependency cycle {name}')
        if name.startswith('kmod-') or name == 'kernel':
            raise ValueError(f'Refusing foreign kernel dependency {name}')
        visiting.add(name)
        info = index[name]
        for dep in info.get('Depends', '').split(','):
            if not dep.strip():
                continue
            # Stop if a new alternative dependency appears; never guess a provider.
            if '|' in dep:
                raise ValueError(f'Unsupported alternative {dep}')
            dep_name = dep.strip().split()[0]
            install(dep_name)
            exact = re.search(r'\(=\s*([^ )]+)\)', dep)
            actual = (installed.get(dep_name) or added[dep_name])['Version']
            if exact and exact.group(1) != actual:
                raise ValueError(f'Version mismatch {dep_name}: {actual} != {exact.group(1)}')
        payload = fetch(BASE + info['Filename'])
        if digest(payload) != info['SHA256sum']:
            raise ValueError(f'Package checksum failed: {name}')
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:*') as ipk:
            m = next(m for m in ipk.getmembers() if m.name.removeprefix('./').startswith('data.tar.'))
            member_file = ipk.extractfile(m)
            if member_file is None:
                raise ValueError(f'Invalid data member in {name}')
            data = member_file.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
            archive.extractall(root, filter='tar')
        added[name] = dict(info, Status='install ok installed')
        info_dir = root / 'usr/lib/opkg/info'
        (info_dir / (name + '.list')).write_text('\n'.join('/' + m.name.removeprefix('./') for m in tarfile.open(fileobj=io.BytesIO(data)).getmembers()) + '\n')
        visiting.remove(name)

    for name in requested:
        install(name)
    # Drop metadata for the removed generic kernel modules: they cannot load
    # into the vendor kernel. This is an overlay assembly, not an opkg upgrade.
    keep = [p for p in old if p['Package'] != 'kernel' and not p['Package'].startswith('kmod-')]
    status.write_text('\n\n'.join('\n'.join(f'{k}: {v}' for k, v in p.items()) for p in keep + list(added.values())) + '\n\n')
    for name in installed:
        if name == 'kernel' or name.startswith('kmod-'):
            for path in (root / 'usr/lib/opkg/info').glob(name + '.*'):
                path.unlink()
    return [{k: p[k] for k in ('Package', 'Version', 'Filename', 'SHA256sum')} for p in added.values()]


def install_modem(root):
    """Install ModemManager + LuCI glue so the built-in sdm660 modem is
    controllable from OpenWrt. ModemManager's `qcom-soc` plugin speaks QMI
    over QRTR and runs the IPA 'DPM Open Port' sequence that binds the
    hardware TX/RX endpoints — the step the bare WDS requests were missing.
    Packages live across the base/packages/luci feeds, so the index is merged.
    """
    status = root / 'usr/lib/opkg/status'
    old = list(package_fields(status.read_text()))
    installed = {p['Package']: p for p in old}
    index = {}
    for base in PKG_REPOS.values():
        text = gzip.decompress(fetch(base + 'Packages.gz')).decode()
        for p in package_fields(text):
            index.setdefault(p['Package'], dict(p, _base=base))
    requested = ['modemmanager', 'luci-proto-modemmanager', 'qmi-utils']
    added, visiting = {}, set()

    def install(name):
        if name in installed or name in added:
            return
        if name in visiting:
            raise ValueError(f'Dependency cycle {name}')
        if name.startswith('kmod-') or name == 'kernel':
            raise ValueError(f'Refusing foreign kernel dependency {name}')
        if name not in index:
            raise ValueError(f'Package not found in any feed: {name}')
        visiting.add(name)
        info = index[name]
        base = info['_base']
        for dep in info.get('Depends', '').split(','):
            if not dep.strip():
                continue
            if '|' in dep:
                raise ValueError(f'Unsupported alternative {dep}')
            dep_name = dep.strip().split()[0]
            install(dep_name)
            exact = re.search(r'\(=\s*([^ )]+)\)', dep)
            actual = (installed.get(dep_name) or added[dep_name])['Version']
            if exact and exact.group(1) != actual:
                raise ValueError(f'Version mismatch {dep_name}: {actual} != {exact.group(1)}')
        payload = fetch(base + info['Filename'])
        if digest(payload) != info['SHA256sum']:
            raise ValueError(f'Package checksum failed: {name}')
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:*') as ipk:
            m = next(m for m in ipk.getmembers() if m.name.removeprefix('./').startswith('data.tar.'))
            member_file = ipk.extractfile(m)
            if member_file is None:
                raise ValueError(f'Invalid data member in {name}')
            data = member_file.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
            archive.extractall(root, filter='tar')
        added[name] = dict(info, Status='install ok installed')
        info_dir = root / 'usr/lib/opkg/info'
        (info_dir / (name + '.list')).write_text('\n'.join('/' + m.name.removeprefix('./') for m in tarfile.open(fileobj=io.BytesIO(data)).getmembers()) + '\n')
        visiting.remove(name)

    for name in requested:
        install(name)
    keep = [p for p in old if p['Package'] != 'kernel' and not p['Package'].startswith('kmod-')]
    status.write_text('\n\n'.join('\n'.join(f'{k}: {v}' for k, v in p.items()) for p in keep + list(added.values())) + '\n\n')
    return [{k: p[k] for k in ('Package', 'Version', 'Filename', 'SHA256sum')} for p in added.values()]


def copy(repo, root, source, target, executable=True):
    path = root / target
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / source, path)
    path.chmod(0o755 if executable else 0o644)


def configure_console(root):
    inittab = root / 'etc/inittab'
    rows = [r for r in inittab.read_text().splitlines() if not r.startswith('ttyGS0:')]
    inittab.write_text('\n'.join(rows + ['ttyGS0::askfirst:/usr/libexec/login.sh']) + '\n')


def validate_console(data):
    expected = b'ttyGS0::askfirst:/usr/libexec/login.sh'
    if not data.endswith(b'\n') or data.splitlines().count(expected) != 1 or b'login.sh\\n' in data:
        raise ValueError('ttyGS0 login record malformed: require one LF-terminated executable path')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-run', required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    original = next(args.source.rglob('openwrt-initramfs.cpio.gz'))
    kernel = next(args.source.rglob('Image.gz-dtb')).read_bytes()
    plain = zlib.decompressobj(31).decompress(kernel)
    match = re.search(rb'Linux version ([^ ]+) [^\0]+', plain)
    if match is None:
        raise ValueError('Kernel banner missing')
    banner = match.group(0).decode()
    kv = banner.split()[2]
    base = fetch(ROOTFS_URL)
    if digest(base) != ROOTFS_SHA256:
        raise ValueError('Rootfs checksum failed')
    with tarfile.open(fileobj=io.BytesIO(base), mode='r:gz') as archive:
        archive.extractall(root, filter='tar')
    shutil.rmtree(root / 'lib/modules', ignore_errors=True)
    # Reuse modules and static daemon from the SAME compiled-kernel artifact.
    for name, mode, data in newc(gzip.decompress(original.read_bytes())):
        if name.startswith(f'lib/modules/{kv}/') or name == f'lib/modules/{kv}' or name in ('usr/bin/rmtfs', 'bin/busybox-static'):
            write_entry(root, name, mode, data)
    modules = root / 'lib/modules' / kv
    ko = modules / 'kernel/drivers/soc/qcom/modem-boot.ko'
    if not ko.is_file():
        raise ValueError('Matching modem-boot.ko absent')
    for path in sorted(modules.rglob('*.ko')):
        flat = modules / path.name
        if path != flat:
            if flat.exists() or flat.is_symlink():
                raise ValueError(f'Flat module collision: {flat}')
            flat.symlink_to(path.relative_to(modules))
    # One native LF record, verified below. Never append literal backslash-n.
    configure_console(root)
    validate_console((root / 'etc/inittab').read_bytes())
    for source, target in [
        ('overlay-openwrt/init', 'init'),
        ('overlay-common/usb-gadget.sh', 'usb-gadget.sh'),
        # Persistent layout: init.d/usb-gadget sources this path on the ROM
        # (the root-level copy above is RAM/bootstrap-only and is stripped
        # from the ROM tar).
        ('overlay-common/usb-gadget.sh', 'usr/lib/wayne/usb-gadget.sh'),
        ('overlay-openwrt/usb-gadget.init', 'etc/init.d/usb-gadget'),
        ('overlay-openwrt/usr/sbin/wayne-ota', 'usr/sbin/wayne-ota'),
        ('scripts/screen.sh', 'root/screen.sh'),
        ('overlay-openwrt/etc/init.d/burnin-guard', 'etc/init.d/burnin-guard'),
        # The modem's diag task starves (dog_hb "Task starvation: diag" ->
        # ERR_FATAL) when nothing on the AP holds /dev/diag open. Stock
        # Android keeps qcrild on it all boot; this init service does the
        # same job on OpenWrt. Must be in every ROM.
        ('overlay-openwrt/etc/init.d/diag-reader', 'etc/init.d/diag-reader'),
        # wayne-diagd: /dev/diag drain that performs the DIAG ioctl msg-mask
        # handshake. A bare `cat` worked on the adios kernel, but the v2
        # kernel's diagchar driver returns EINVAL on a raw read until the
        # masks are set up (diag_copy_to_user_msg_mask err -22), so the drain
        # must speak the handshake. Built in CI (build-diagd.sh) and staged
        # into build/diagd-out/wayne-diagd before assemble runs. OPTIONAL: the
        # standalone test-rootfs job does not run build-diagd.sh, so if the
        # binary is absent we skip it and the diag-reader init falls back to
        # `cat` (best-effort drain) rather than failing the whole assemble.
        *([('build/diagd-out/wayne-diagd', 'usr/lib/wayne/wayne-diagd')]
          if (repo / 'build/diagd-out/wayne-diagd').exists() else []),
        ('modem/rmtfs', 'etc/init.d/rmtfs'),
        ('scripts/modem-boot-trigger.init', 'etc/init.d/modem-boot-trigger'),
        ('overlay-openwrt/etc/uci-defaults/90-usb0-lan', 'etc/uci-defaults/90-usb0-lan'),
        # Radio stack: the modem cannot come up (or stay up) without these
        # user-space services, and the WLAN loader depends on them too.
        ('modem/radio-bin/pd-mapper', 'usr/lib/wayne/radio/pd-mapper'),
        ('modem/radio-bin/qrtr-ns', 'usr/lib/wayne/radio/qrtr-ns'),
        ('modem/radio-bin/locator-query', 'usr/lib/wayne/radio/locator-query'),
        ('modem/radio-bin/qrtr-lookup', 'usr/lib/wayne/radio/qrtr-lookup'),
        ('modem/radio-bin/tqftpserv', 'usr/bin/tqftpserv'),
        ('overlay-openwrt/etc/init.d/pd-mapper', 'etc/init.d/pd-mapper'),
        ('overlay-openwrt/etc/init.d/tqftpserv', 'etc/init.d/tqftpserv'),
        ('overlay-openwrt/etc/init.d/qrtr-ns', 'etc/init.d/qrtr-ns'),
        ('overlay-openwrt/etc/init.d/wayne-wlan-fw', 'etc/init.d/wayne-wlan-fw'),
        ('overlay-openwrt/etc/init.d/wayne-wlan', 'etc/init.d/wayne-wlan'),
        ('overlay-openwrt/usr/lib/wayne/wlan-load.sh', 'usr/lib/wayne/wlan-load.sh'),
        ('scripts/wifi-diag.sh', 'root/wifi-diag.sh'),
    ]:
        copy(repo, root, source, target)
    (root / 'bin/busybox-static').chmod(0o755)
    # PD maps + modem firmware: PIL probes these by name from /lib/firmware.
    for m in ('MODEMR.JSN', 'MODEMUW.JSN'):
        copy(repo, root, 'modem/pd-maps/' + m, 'usr/share/wayne/pd-maps/' + m)
    fw = root / 'lib/firmware'
    fw.mkdir(parents=True, exist_ok=True)
    for src in sorted((repo / 'modem-firmware').iterdir()):
        if src.is_file():
            shutil.copyfile(src, fw / src.name)
    # PIL probes lowercase names on a case-sensitive rootfs; add lowercase
    # copies of the modem boot chain exactly like the 21.02 ROM does.
    for up in ('MBA.MBN', 'MODEM.MDT'):
        if (fw / up).is_file():
            shutil.copyfile(fw / up, fw / up.lower())
    # Service order must match each init script's own START= value: procd runs
    # /etc/rc.d/S<NN><name> in NN order, so a wrong NN silently changes ordering.
    # dbus MUST come up before modemmanager (MM speaks to the system bus), and
    # diag-reader must start BEFORE modem-boot-trigger (97) so /dev/diag is
    # already being drained when the modem comes online.
    for name, order in [('qrtr-ns', 11), ('dbus', 60), ('modemmanager', 70),
                        ('usb-gadget', 95), ('rmtfs', 95), ('wayne-wlan-fw', 95),
                        ('pd-mapper', 96), ('tqftpserv', 96),
                        ('modem-boot-trigger', 97), ('wayne-wlan', 99),
                        ('burnin-guard', 99), ('diag-reader', 25)]:
        link = root / f'etc/rc.d/S{order}{name}'
        link.unlink(missing_ok=True)
        link.symlink_to('../init.d/' + name)
    # The IPA use-after-free that reboot-looped the device is fixed in this
    # kernel (f997eb3), so the modem may auto-boot on the main ROM again.
    (root / 'etc/config/wayne-modem').write_text("config modem 'main'\n\toption allow_boot '1'\n")
    # A RAM-debug image must not automount internal Android filesystems rw.
    # The modem service alone mounts its firmware volume ro when needed.
    (root / 'etc/uci-defaults/11-anonmount').unlink(missing_ok=True)
    (root / 'etc/config/fstab').write_text("config global\n\toption anon_mount '0'\n\toption auto_mount '0'\n\toption anon_swap '0'\n\toption auto_swap '0'\n")
    # Do not configure an open AP or generate placeholder calibration/MAC data.
    subprocess.run(['sh', str(repo / 'scripts/stage-wifi-fw.sh'), str(repo / 'modem-firmware'), str(root)], check=True)
    packages = install_wifi(root)
    packages += install_modem(root)
    for svc in ('wpad',):
        link = root / f'etc/rc.d/S19{svc}'
        if not link.exists() and not link.is_symlink():
            link.symlink_to('../init.d/' + svc)
    provenance = {
        'rootfs': VERSION, 'rootfs_url': ROOTFS_URL, 'rootfs_sha256': ROOTFS_SHA256,
        'source_run': args.source_run, 'kernel_banner': banner,
        'kernel_sha256': digest(kernel), 'modem_module_sha256': digest(ko.read_bytes()),
        'repository_commit': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'packages_added': packages,        'modem_powerup_default': 'enabled: IPA QMI use-after-free fixed (kernel f997eb3)',
        'limits': ['Hardware boot/radio/screen-off still require device verification', 'No EFS/calibration writes permitted'],
    }
    (root / 'etc/wayne-build.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    main()
