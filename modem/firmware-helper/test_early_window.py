import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
FIXTURE = r'''
set -eu
. "$1"
[ "$BASELINE" != yes ] || . /dev/stdin
printf '%s\n' 100 > "$CLOCK"
tw_now() { read -r t < "$CLOCK"; printf '%s\n' "$t"; }
tw_sleep() { printf '%s\n' "$(($(tw_now) + $1))" > "$CLOCK"; }
tw_prepare() { tw_sleep 220; echo prepared; }
tw_claim() { mkdir "$CLOCK.claimed"; }
tw_launch() { echo launched; }
tw_ready() { echo lookup; tw_sleep "$READY_COST"; [ "$READY" = yes ]; }
tw_check() { [ "$SCOPE" = yes ] || { [ "$SCOPE" = before_launch_only ] && [ ! -d "$CLOCK.claimed" ]; }; }
tw_reserve() { echo reserved; }
tw_acquire() { echo acquire; tw_sleep 30; [ "$ACQUIRE" = yes ]; }
tw_sample() {
    printf 'sample %s %s\n' "$1" "$(tw_now)"
    tw_sleep "$SAMPLE_COST"
    [ "$1" != "$FAIL_SAMPLE" ]
}
tw_finish() { echo finished; tw_sleep "$FINISH_COST"; }
tw_cleanup() { echo cleaned; [ "$CLEANUP" = yes ]; }
trial_early_window
'''

# Preserve the old >=55s refusal as a negative control for the launch order.
BASELINE = r'''
trial_early_window() {
    start=$(tw_now)
    tw_launch 360
    tw_prepare
    now=$(tw_now)
    [ "$((now-start))" -lt 55 ] || { tw_fail insufficient_provider_lifetime; return 1; }
    tw_acquire
}
'''


class EarlyWindow(unittest.TestCase):
    def invoke(self, *, baseline=False, **overrides):
        defaults = dict(READY_COST='2', READY='yes', SCOPE='yes', ACQUIRE='yes',
                        SAMPLE_COST='4', FAIL_SAMPLE='none', CLEANUP='yes', FINISH_COST='0')
        defaults.update(overrides)
        with tempfile.TemporaryDirectory() as tmp:
            clock = Path(tmp) / 'clock'
            if defaults.pop('ALREADY_CLAIMED', 'no') == 'yes':
                clock.with_suffix('.claimed').mkdir()
            shell = shlex.split(os.getenv('TRIAL_TEST_SHELL', 'sh'))
            result = subprocess.run(shell + ['-c', FIXTURE, 'fixture', str(HERE / 'early-window.sh')],
                                    input=BASELINE if baseline else '',
                                    env={**os.environ, **defaults, 'CLOCK': str(clock),
                                         'BASELINE': 'yes' if baseline else 'no'},
                                    capture_output=True, text=True, timeout=25)
        return result, result.stdout.splitlines()

    def test_previous_launch_order_reproduces_refusal_without_acquisition(self):
        result, lines = self.invoke(baseline=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('insufficient_provider_lifetime', result.stderr)
        self.assertEqual(lines, ['launched', 'prepared'])

    def test_preparation_cannot_spend_provider_lifetime_and_samples_do_not_drift(self):
        result, lines = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(lines[:5], ['prepared', 'launched', 'lookup', 'reserved', 'acquire'])
        samples = [(int(row.split()[1]), int(row.split()[2])) for row in lines if row.startswith('sample ')]
        self.assertEqual(samples, [(i, 352 + 10 * i) for i in range(31)])
        self.assertEqual(lines[-2:], ['finished', 'cleaned'])

    def test_insufficient_lifetime_refuses_before_reserving_start(self):
        result, lines = self.invoke(READY_COST='11')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('insufficient_provider_lifetime', result.stderr)
        self.assertNotIn('reserved', lines)
        self.assertNotIn('acquire', lines)
        self.assertEqual(lines[-1], 'cleaned')

    def test_missing_publication_never_acquires_and_still_cleans(self):
        result, lines = self.invoke(READY='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('provider_not_ready', result.stderr)
        self.assertNotIn('acquire', lines)
        self.assertEqual(lines[-1], 'cleaned')

    def test_changed_scope_never_claims_or_launches(self):
        result, lines = self.invoke(SCOPE='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lines, ['prepared'])

    def test_scope_is_rechecked_after_publication(self):
        result, lines = self.invoke(SCOPE='before_launch_only')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('scope_changed', result.stderr)
        self.assertEqual(lines, ['prepared', 'launched', 'lookup', 'cleaned'])

    def test_already_claimed_does_not_launch_or_clean_up_another_run(self):
        result, lines = self.invoke(ALREADY_CLAIMED='yes')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lines, ['prepared'])

    def test_uncertain_acquisition_is_never_retried(self):
        result, lines = self.invoke(ACQUIRE='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lines.count('acquire'), 1)
        self.assertEqual(lines[-1], 'cleaned')
        self.assertNotIn('finished', lines)

    def test_failed_sample_can_never_be_a_complete_capture(self):
        result, lines = self.invoke(FAIL_SAMPLE='2')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('finished', lines)
        self.assertEqual(lines[-1], 'cleaned')

    def test_deadline_miss_stops_rather_than_accepting_late_samples(self):
        result, lines = self.invoke(SAMPLE_COST='15')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sample_deadline_missed', result.stderr)
        self.assertNotIn('finished', lines)
        self.assertEqual(lines[-1], 'cleaned')

    def test_cleanup_failure_prevents_success(self):
        result, lines = self.invoke(CLEANUP='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lines[-2:], ['finished', 'cleaned'])


    def test_closeout_past_deadline_prevents_success(self):
        result, lines = self.invoke(FINISH_COST='25')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('closeout_deadline_missed', result.stderr)
        self.assertEqual(lines[-2:], ['finished', 'cleaned'])


if __name__ == '__main__':
    unittest.main()
