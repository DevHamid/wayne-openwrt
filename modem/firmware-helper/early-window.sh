# Source with reviewed device hooks, or with test_early_window.py's fixtures.
# Hooks must propagate errors explicitly and bound blocking IO themselves.
tw_now() {
    IFS=' ' read -r tw_uptime tw_idle < /proc/uptime || return 1
    case ${tw_uptime%%.*} in ''|*[!0-9]*) return 1;; esac
    printf '%s\n' "${tw_uptime%%.*}"
}

tw_sleep() { sleep "$1"; }
tw_fail() { printf 'REFUSED: %s\n' "$1" >&2; return 1; }

trial_early_window() (
    # Leave room for the bounded 30s acquisition, 300s cadence and closeout.
    ttl=360
    min_remaining=350
    interval=10
    final_sample=30
    max_sample_time=5

    tw_prepare || { tw_fail preflight_failed; exit 1; }
    tw_check || { tw_fail scope_changed; exit 1; }
    tw_claim || { tw_fail window_already_claimed; exit 1; }
    trap 'status=$?; trap - 0; tw_cleanup || { tw_fail cleanup_failed; status=1; }; exit "$status"' 0
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM

    start=$(tw_now) || exit 1
    deadline=$((start + ttl))
    tw_launch "$ttl" || { tw_fail provider_start_failed; exit 1; }
    while ! tw_ready; do
        now=$(tw_now) || exit 1
        [ "$now" -lt "$((deadline - min_remaining))" ] || { tw_fail provider_not_ready; exit 1; }
        tw_sleep 1 || exit 1
    done

    tw_check || { tw_fail scope_changed; exit 1; }
    now=$(tw_now) || exit 1
    [ "$((deadline - now))" -ge "$min_remaining" ] || { tw_fail insufficient_provider_lifetime; exit 1; }
    tw_reserve || { tw_fail modem_start_already_reserved; exit 1; }
    tw_acquire || { tw_fail modem_start_outcome_uncertain_no_retry; exit 1; }

    first=$(tw_now) || exit 1
    seq=0
    while [ "$seq" -le "$final_sample" ]; do
        slot=$((first + seq * interval))
        now=$(tw_now) || exit 1
        if [ "$now" -lt "$slot" ]; then
            tw_sleep "$((slot - now))" || exit 1
            now=$(tw_now) || exit 1
        fi
        [ "$now" -lt "$((slot + max_sample_time))" ] && [ "$now" -lt "$deadline" ] || {
            tw_fail sample_deadline_missed; exit 1;
        }
        tw_sample "$seq" || { tw_fail snapshot_failed; exit 1; }
        now=$(tw_now) || exit 1
        [ "$now" -le "$((slot + max_sample_time))" ] && [ "$now" -lt "$deadline" ] || {
            tw_fail sample_deadline_missed; exit 1;
        }
        seq=$((seq + 1))
    done
    tw_finish || { tw_fail closeout_failed; exit 1; }
    now=$(tw_now) || exit 1
    [ "$now" -lt "$deadline" ] || { tw_fail closeout_deadline_missed; exit 1; }
)
