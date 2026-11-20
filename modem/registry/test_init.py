#!/usr/bin/env python3
"""Exercise candidate init/readiness logic without procd or any real QRTR socket."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class RegistryInitTest(unittest.TestCase):
    def run_service(self, role='mapper', pending=0, bad_maps=False, wrong_tuple=False,
                    query_fail=False, dead=False, missing_binary=False):
        source = HERE / ('wayne-pd-mapper.init' if role == 'mapper' else 'wayne-qrtr.init')
        self.assertTrue(source.is_file(), 'early registry service not implemented')
        with tempfile.TemporaryDirectory(prefix='wayne-init-') as name:
            root = Path(name)
            binary = root / 'runtime bin'
            binary.mkdir()
            maps = root / 'maps'
            maps.mkdir()
            tools = root / 'tools'
            tools.mkdir()
            for file in ('registry-service.sh', 'registry-ready.sh'):
                shutil.copyfile(HERE / file, binary / file)
                (binary / file).chmod(0o700)

            def write(path, value):
                path.write_text(value)
                path.chmod(0o700)

            write(root / 'timeout-helper', '#!/bin/sh\n[ "$1" = timeout ] || exit 99\nshift\nexec /usr/bin/timeout "$@"\n')
            write(binary / 'qrtr-ns', '#!/bin/sh\nexit 0\n')
            write(binary / 'pd-mapper', '#!/bin/sh\n[ "$1" = -n ] && [ "$FAKE_BAD_MAPS" != yes ]\n')
            write(binary / 'qrtr-lookup', '''#!/bin/sh
n=0
[ ! -e "$FIXTURE/lookups" ] || n=$(/bin/cat "$FIXTURE/lookups")
n=$((n+1)); echo "$n" > "$FIXTURE/lookups"
echo 'Service Version Instance Node Port'
if [ "$n" -gt "$FAKE_PENDING" ]; then
    if [ "$FAKE_WRONG_TUPLE" = yes ]; then echo '64 1 0 1 88 Locator'; else echo '64 1 1 1 88 Locator'; fi
fi
''')
            write(binary / 'locator-query', '''#!/bin/sh
[ "$1" = 88 ] || exit 99
n=0
[ ! -e "$FIXTURE/queries" ] || n=$(/bin/cat "$FIXTURE/queries")
echo "$((n+1))" > "$FIXTURE/queries"
[ "$FAKE_QUERY_FAIL" != yes ]
''')
            if missing_binary:
                (binary / ('pd-mapper' if role == 'mapper' else 'qrtr-ns')).unlink()
            write(tools / 'logger', '#!/bin/sh\nexit 0\n')
            write(tools / 'sleep', '#!/bin/sh\nexit 0\n')
            script = root / 'run.sh'
            script.write_text('''procd_open_instance() { echo "instance:$1" >> "$FIXTURE/params"; }
procd_set_param() { printf '%s\\n' "$@" >> "$FIXTURE/params"; }
procd_close_instance() { :; }
procd_running() { [ "$FAKE_DEAD" != yes ]; }
procd_kill() { printf '%s %s\\n' "$1" "$2" >> "$FIXTURE/killed"; }
initscript=$1
basescript=
. "$initscript"
start_service
rc=$?
[ "$rc" = 0 ] || exit "$rc"
service_started
''')
            shell = os.environ.get('TRACE_TEST_SHELL', '/bin/sh')
            prefix = [shell, 'ash'] if Path(shell).name == 'busybox' else [shell]
            paths = [str(tools)]
            if os.environ.get('TRACE_TEST_APPLETS'):
                paths.append(os.environ['TRACE_TEST_APPLETS'])
            paths.append(os.defpath)
            env = dict(os.environ, FIXTURE=name, WAYNE_RADIO_BIN_DIR=str(binary),
                       WAYNE_RADIO_MAP_DIR=str(maps), WAYNE_RADIO_TIMEOUT=str(root / 'timeout-helper'),
                       FAKE_PENDING=str(pending), FAKE_BAD_MAPS='yes' if bad_maps else 'no',
                       FAKE_WRONG_TUPLE='yes' if wrong_tuple else 'no',
                       FAKE_QUERY_FAIL='yes' if query_fail else 'no', FAKE_DEAD='yes' if dead else 'no',
                       PATH=':'.join(paths))
            result = subprocess.run([*prefix, str(script), str(source)], capture_output=True,
                                    text=True, env=env, timeout=6)
            params = (root / 'params').read_text().splitlines() if (root / 'params').exists() else []
            queries = int((root / 'queries').read_text()) if (root / 'queries').exists() else 0
            lookups = int((root / 'lookups').read_text()) if (root / 'lookups').exists() else 0
            killed = (root / 'killed').read_text() if (root / 'killed').exists() else ''
            return result, params, queries, lookups, killed, str(binary), str(maps)

    def test_mapper_waits_for_discovery_then_queries_once(self):
        result, params, queries, lookups, killed, binary, maps = self.run_service(pending=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((queries, lookups), (1, 3))
        self.assertEqual(params[:5], ['instance:main', 'command', binary + '/pd-mapper', '-d', maps])
        self.assertNotIn('respawn', params)
        self.assertEqual(killed, '')

    def test_nameserver_needs_no_modem_or_rmtfs_endpoint(self):
        result, params, queries, lookups, killed, binary, _ = self.run_service(role='nameserver', pending=99)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((queries, lookups), (0, 1))
        self.assertEqual(params[:4], ['instance:main', 'command', binary + '/qrtr-ns', '-f'])
        self.assertEqual(killed, '')

    def test_query_failure_is_not_retried_and_stops_only_own_instance(self):
        result, _, queries, lookups, killed, _, _ = self.run_service(query_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((queries, lookups), (1, 1))
        self.assertEqual(killed, 'wayne-pd-mapper.init main\n')

    def test_bad_maps_or_missing_binary_register_no_instance(self):
        for bad_maps, missing_binary in ((True, False), (False, True)):
            result, params, queries, lookups, _, _, _ = self.run_service(
                bad_maps=bad_maps, missing_binary=missing_binary)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((params, queries, lookups), ([], 0, 0))

    def test_wrong_tuple_is_refused_without_registry_query(self):
        result, _, queries, lookups, killed, _, _ = self.run_service(wrong_tuple=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((queries, lookups), (0, 1))
        self.assertTrue(killed)

    def test_absent_publication_has_a_bounded_wait(self):
        result, _, queries, lookups, killed, _, _ = self.run_service(pending=99)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((queries, lookups), (0, 5))
        self.assertTrue(killed)

    def test_dead_procd_instance_is_not_ready(self):
        result, _, queries, lookups, killed, _, _ = self.run_service(dead=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((queries, lookups), (0, 0))
        self.assertTrue(killed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
