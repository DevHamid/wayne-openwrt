#!/usr/bin/env python3
"""Exercise the built mapper against firmware maps without opening QRTR."""
import json
import lzma
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import struct
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BINARY = Path(os.environ.get('PD_MAPPER_TEST_BINARY', HERE / 'build/mapper-fixture'))
FIRMWARE = Path(os.environ.get('PD_MAPPER_FIRMWARE', HERE.parents[2] / 'modem-firmware'))
PREFIX = shlex.split(os.environ.get('PD_MAPPER_RUNNER', ''))


class MapperTests(unittest.TestCase):
    def invoke(self, directory, *args):
        result = subprocess.run([*PREFIX, str(BINARY), '-n', '-d', str(directory), *args],
                                capture_output=True, text=True, timeout=3)
        self.assertNotIn('AddressSanitizer', result.stderr)
        self.assertNotIn('runtime error:', result.stderr)
        return result

    def test_authentic_uppercase_wlan_map_without_remoteproc(self):
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            for file in ('MODEMUW.JSN', 'MODEMR.JSN'):
                shutil.copyfile(FIRMWARE / file, path / file)
            result = self.invoke(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('map service=wlan/fw domain=msm/modem/wlan_pd instance=180\n', result.stdout)
            self.assertIn('maps_validated=4\n', result.stdout)

    def test_compressed_uppercase_map_supported(self):
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            (path / 'MODEMUW.JSN.XZ').write_bytes(lzma.compress((FIRMWARE / 'MODEMUW.JSN').read_bytes()))
            result = self.invoke(path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('maps_validated=3\n', result.stdout)

    def test_empty_missing_and_invalid_maps_refused(self):
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            self.assertNotEqual(self.invoke(path).returncode, 0)
            self.assertNotEqual(self.invoke(path / 'missing').returncode, 0)
            for data in ('{}', '{"sr_domain":null}', 'not-json', ''):
                with self.subTest(data=data):
                    (path / 'bad.JSN').write_text(data)
                    result = self.invoke(path)
                    self.assertGreater(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, '')

    def test_invalid_schema_bounds_refused(self):
        template = json.loads((FIRMWARE / 'MODEMUW.JSN').read_text())
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            for field, value in [('qmi_instance_id', 4294967296), ('subdomain', 'x' * 300),
                                 ('soc', 'bad\nvalue')]:
                with self.subTest(field=field):
                    data = json.loads(json.dumps(template))
                    data['sr_domain'][field] = value
                    (path / 'bad.JSN').write_text(json.dumps(data))
                    result = self.invoke(path)
                    self.assertGreater(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, '')

    def test_partial_map_set_is_not_reported_as_valid(self):
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            shutil.copyfile(FIRMWARE / 'MODEMUW.JSN', path / 'good.JSN')
            (path / 'bad.JSN').write_text('{}')
            result = self.invoke(path)
            self.assertGreater(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')

    def test_matching_symlink_or_directory_refused(self):
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            (path / 'map.JSN').symlink_to(FIRMWARE / 'MODEMUW.JSN')
            self.assertGreater(self.invoke(path).returncode, 0)
            (path / 'map.JSN').unlink()
            (path / 'map.JSN').mkdir()
            self.assertGreater(self.invoke(path).returncode, 0)

    def test_invalid_arguments_refused(self):
        for args in (['-n'], ['--invalid'], ['-n', '-d'], ['-n', '-d', '/tmp', 'unexpected']):
            with self.subTest(args=args):
                result = subprocess.run([*PREFIX, str(BINARY), *args], capture_output=True, text=True, timeout=3)
                self.assertGreater(result.returncode, 0)
                self.assertNotIn('AddressSanitizer', result.stderr)
                self.assertNotIn('runtime error:', result.stderr)

    def test_kernel_wlan_lookup_wire_response_and_locator_instance(self):
        fixture = Path(os.environ.get('PD_MAPPER_FIXTURE', HERE / 'build/mapper-fixture'))
        with tempfile.TemporaryDirectory(prefix='pdmapper-') as name:
            path = Path(name)
            shutil.copyfile(FIRMWARE / 'MODEMUW.JSN', path / 'MODEMUW.JSN')
            for service, expected in [('wlan/fw', 1), ('unknown/service', 0)]:
                result = subprocess.run([*PREFIX, str(fixture), '--wire', name, service],
                                        capture_output=True, text=True, timeout=3)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, '')
                records = dict(line.split('=', 1) for line in result.stdout.splitlines())
                advertisement = bytes.fromhex(records['advertisement'])
                command, service_id, packed, _, _ = struct.unpack('<IIIII', advertisement)
                self.assertEqual((command, service_id, packed & 255, packed >> 8), (4, 64, 1, 1))
                wire = bytes.fromhex(records['wire_response'])
                flags, txn, msg, length = struct.unpack_from('<BHHH', wire)
                self.assertEqual((flags, txn, msg, length), (2, 0x1234, 0x21, len(wire) - 7))
                tlvs = {}
                offset = 7
                while offset < len(wire):
                    tag, size = struct.unpack_from('<BH', wire, offset)
                    self.assertNotIn(tag, tlvs)
                    offset += 3
                    tlvs[tag] = wire[offset:offset + size]
                    self.assertEqual(len(tlvs[tag]), size)
                    offset += size
                self.assertEqual(offset, len(wire))
                self.assertEqual(tlvs[2], b'\x00\x00\x00\x00')
                self.assertEqual(struct.unpack('<H', tlvs[0x10])[0], expected)
                if expected:
                    data = tlvs[0x12]
                    self.assertEqual(data[0], 1)
                    size = data[1]
                    self.assertEqual(data[2:2 + size], b'msm/modem/wlan_pd')
                    self.assertEqual(struct.unpack_from('<IBI', data, 2 + size), (180, 0, 0))
                    self.assertEqual(len(data), 2 + size + 9)
                else:
                    self.assertNotIn(0x12, tlvs)


if __name__ == '__main__':
    unittest.main(verbosity=2)
