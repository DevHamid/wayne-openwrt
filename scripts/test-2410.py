#!/usr/bin/env python3
"""Regression checks using the broken released console and fake device paths."""
import gzip
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assembly', BASE / 'scripts/assemble-2410.py')
assert spec is not None and spec.loader is not None
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


class ConsoleTests(unittest.TestCase):
    def test_literal_backslash_n_rejected(self):
        with self.assertRaises(ValueError):
            assembly.validate_console(b'ttyGS0::askfirst:/usr/libexec/login.sh\\n')

    def test_duplicate_console_rejected(self):
        with self.assertRaises(ValueError):
            assembly.validate_console(b'ttyGS0::askfirst:/usr/libexec/login.sh\n' * 2)

    def test_native_lf_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'etc').mkdir()
            path = root / 'etc/inittab'
            path.write_bytes(b'::sysinit:/etc/init.d/rcS S boot\nttyGS0::askfirst:/usr/libexec/login.sh\\n')
            assembly.configure_console(root)
            first = path.read_bytes()
            assembly.configure_console(root)
            self.assertEqual(first, path.read_bytes())
            assembly.validate_console(first)
            self.assertTrue(first.startswith(b'::sysinit:/etc/init.d/rcS S boot\n'))


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_fails_closed_before_switch_root(self):
        init = (BASE / 'overlay-system/init').read_text()
        self.assertIn('bootstrap_fatal()', init)
        self.assertIn('bootstrap_fatal "system partition not found', init)
        self.assertIn('bootstrap_fatal "mount $MNT failed', init)
        self.assertIn('bootstrap_fatal "$MNT has no /sbin/init', init)
        self.assertIn('bootstrap_fatal "switch_root returned', init)
        self.assertIn('switch_root "$MNT" /sbin/init', init)
        self.assertNotIn('exec switch_root "$MNT" /sbin/init', init)

    def test_bootstrap_bundles_gadget_helper(self):
        workflow = (BASE / '.github/workflows/build.yml').read_text()
        self.assertIn(
            'cp overlay-common/usb-gadget.sh build/bootstrap/usb-gadget.sh',
            workflow,
        )

    def test_rom_rootfs_bundles_usb_gadget_helper_for_service(self):
        workflow = (BASE / '.github/workflows/build.yml').read_text()
        self.assertIn(
            'install -D -m 0755 overlay-common/usb-gadget.sh "$ROOTFS/usr/lib/wayne/usb-gadget.sh"',
            workflow,
        )
        self.assertIn(
            "tar -tzf build/rom/system/rootfs.tar.gz | grep -Fxq './usr/lib/wayne/usb-gadget.sh'",
            workflow,
        )

    def test_bootstrap_starts_usb_gadget_without_blocking_system_lookup(self):
        init = (BASE / 'overlay-system/init').read_text()
        start = init.index('USB gadget setup started')
        locate = init.index('locating system partition')
        self.assertLess(start, locate)
        gadget = init[init.index('if [ -r /usb-gadget.sh ]'):locate]
        self.assertRegex(gadget, r'\) >/dev/null 2>&1 &')


class ModemServiceTests(unittest.TestCase):
    def test_existing_automount_image_layout_and_readonly_procd(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fw = root / 'firmware/image'
            fw.mkdir(parents=True)
            for name in ('mba.mbn', 'modem.mdt', 'modem.b00', 'modem.b0a'):
                (fw / name).write_bytes(b'real-firmware-fixture')
            (root / 'proc').mkdir()
            (root / 'proc/mounts').write_text(f'{root}/dev/modem {fw.parent} vfat rw 0 0\n')
            (root / 'dev').mkdir()
            for name in ('modem', 'modemst1', 'modemst2', 'fsg', 'fsc', 'uio0'):
                (root / 'dev' / name).touch()
            service = (BASE / 'modem/rmtfs').read_text()
            # Isolate absolute paths; the service can only see this fixture.
            service = service.replace('/tmp/wayne-rmtfs', str(root / 'backing'))
            service = service.replace('/proc/mounts', str(root / 'proc/mounts'))
            service = service.replace('/lib/firmware', str(root / 'lib/firmware'))
            service = service.replace('/dev/', str(root / 'dev') + '/')
            path = root / 'service.sh'
            path.write_text(service)
            harness = '''
. "$1"
find_partition() { printf '%s/%s\\n' "$FIXTURE/dev" "$1"; }
find_uio() { printf '%s/dev/uio0\\n' "$FIXTURE"; }
mount() { echo 'UNEXPECTED MOUNT' >&2; return 92; }
log() { :; }
procd_open_instance() { :; }
procd_close_instance() { :; }
procd_set_param() { printf '%s\\n' "$*" >> "$FIXTURE/procd-calls"; }
RMTFS_BIN="$FIXTURE/daemon"
printf '#!/bin/sh\\nexit 0\\n' > "$RMTFS_BIN"
chmod +x "$RMTFS_BIN"
start_service
'''
            import os
            env = dict(os.environ, FIXTURE=str(root))
            result = subprocess.run(['sh', '-c', harness, 'test', str(path)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = (root / 'procd-calls').read_text()
            self.assertIn(f'command {root}/daemon -r -P -o {root}/backing -v', calls)
            for name in ('modemst1', 'modemst2', 'fsg', 'fsc'):
                self.assertEqual((root / 'backing' / name).readlink(), root / 'dev' / name)
            for name in ('mba.mbn', 'modem.mdt', 'modem.b00', 'modem.b0a'):
                self.assertEqual((root / 'lib/firmware' / name).readlink(), fw / name)
            self.assertNotIn('UNEXPECTED MOUNT', result.stderr)


if __name__ == '__main__':
    unittest.main()
