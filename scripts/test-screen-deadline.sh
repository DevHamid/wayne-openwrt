#!/bin/sh
# test-screen-deadline.sh -- regression test for the burn-in guard's cross-reboot
# idle deadline in scripts/screen.sh.
#
# WHY: the guard used to sleep BOOT_IDLE (90 s) from scratch on every boot. On a
# device that reboots before the deadline (modem SSR -> kernel panic -> reboot
# every ~70 s) the sleep is never reached, so the panel stayed lit forever. That
# is the "screen always turns on" bug. The guard must now count the time the
# panel has ALREADY been lit, persisted in /root/.screen.on_since, so successive
# boots converge on the deadline instead of restarting it.
#
# Runs entirely against a fake sysfs tree in $TMPDIR. Touches no real device.
#
# USAGE: sh scripts/test-screen-deadline.sh   (from the repo root)

set -u
FAIL=0
here=$(cd "$(dirname "$0")" && pwd)
src="$here/screen.sh"
[ -f "$src" ] || { echo "FAIL: cannot find $src"; exit 1; }

R=$(mktemp -d "${TMPDIR:-/tmp}/screen-deadline.XXXXXX")
trap 'rm -rf "$R"' EXIT INT TERM

mkdir -p "$R/root" "$R/tmp" \
         "$R/sys/class/graphics/fb0" \
         "$R/sys/class/backlight/backlight" \
         "$R/sys/class/leds/lcd-backlight"

# Redirect every absolute path the helper uses into the sandbox.
sed -e "s#/sys/class#$R/sys/class#g" \
    -e "s#/root/#$R/root/#g" \
    -e "s#/tmp/#$R/tmp/#g" "$src" > "$R/screen.sh"

BL="$R/sys/class/backlight/backlight/brightness"
echo 4095 > "$R/sys/class/backlight/backlight/max_brightness"
echo 4095 > "$R/sys/class/leds/lcd-backlight/max_brightness"
echo 2000 > "$R/sys/class/leds/lcd-backlight/brightness"
echo 0    > "$R/sys/class/graphics/fb0/blank"

reset_state() {
    echo 4095 > "$BL"
    rm -f "$R/root/.screen.bright" "$R/root/.screen.pid" "$R/root/screen.log"
}

check() { # name expected actual
    if [ "$2" = "$3" ]; then
        echo "  ok   $1 -> $3"
    else
        echo "  FAIL $1 -> got '$3', want '$2'"
        FAIL=$((FAIL + 1))
    fi
}

# --- Case 1: fresh boot (no marker) must wait the full idle period ------------
echo "case 1: fresh boot waits the full BOOT_IDLE"
reset_state
rm -f "$R/root/.screen.on_since"
timeout 10 sh "$R/screen.sh" guardfg 2 1 >/dev/null 2>&1
check "brightness blanked" 0 "$(cat "$BL")"
# guardfg is the procd (foreground) twin: it reports through screen.log.
check "no pre-lit time counted" "lit 0s, blank in 2s" \
      "$(grep -o 'lit [0-9]*s, blank in [0-9]*s' "$R/root/screen.log" 2>/dev/null | head -1)"

# --- Case 2: reboot after 70 s lit, idle 90 s -> only 20 s must remain --------
echo "case 2: reboot with 70s already lit shortens the wait to 20s"
reset_state
echo $(( $(date +%s) - 70 )) > "$R/root/.screen.on_since"
out=$(timeout 2 sh -c "sh '$R/screen.sh' guard 90 1" 2>&1)
sleep 1
check "wait computed" "off in 20s [70s already lit]" \
      "$(printf '%s' "$out" | grep -o 'off in [0-9]*s \[[0-9]*s already lit\]' | head -1)"

# --- Case 3: lit longer than the idle period -> blank immediately ------------
echo "case 3: lit past the deadline blanks immediately"
reset_state
echo $(( $(date +%s) - 500 )) > "$R/root/.screen.on_since"
out=$(timeout 2 sh -c "sh '$R/screen.sh' guard 90 1" 2>&1)
sleep 1
check "clamped to 0s wait" "off in 0s [90s already lit]" \
      "$(printf '%s' "$out" | grep -o 'off in [0-9]*s \[[0-9]*s already lit\]' | head -1)"
check "panel blanked" 0 "$(cat "$BL")"

# --- Case 4: `on` restarts the countdown ------------------------------------
echo "case 4: screen.sh on resets the deadline"
echo $(( $(date +%s) - 500 )) > "$R/root/.screen.on_since"
sh "$R/screen.sh" on >/dev/null 2>&1
since=$(cat "$R/root/.screen.on_since" 2>/dev/null)
now=$(date +%s)
if [ -n "$since" ] && [ $((now - since)) -lt 5 ]; then
    echo "  ok   marker refreshed -> $((now - since))s ago"
else
    echo "  FAIL marker not refreshed (since='$since')"
    FAIL=$((FAIL + 1))
fi

echo
if [ "$FAIL" -eq 0 ]; then
    echo "PASS: screen deadline behaves correctly across reboots"
    exit 0
fi
echo "FAILED: $FAIL check(s)"
exit 1
