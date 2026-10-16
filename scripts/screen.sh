#!/bin/sh
# screen.sh -- panel blank + backlight control for wayne (Mi 6X, ImmortalWrt 21.02)
#
# WHY: during bring-up the panel sits lit on the MI/fastboot logo for hours and
#      can burn in. The vendor kernel already has the full display stack
#      (CONFIG_FB_MSM_MDSS, CONFIG_BACKLIGHT_QCOM_SPMI_WLED); only userspace is
#      needed:
#        /sys/class/graphics/fb0/blank                 0=on 1=blank 4=powerdown
#        /sys/class/leds/lcd-backlight/brightness      0..max_brightness(4095)
#      fb1/fb2 are MDSS writeback outputs -- NOT the panel. Use fb0.
#
# USAGE:
#   sh screen.sh status            # read-only
#   sh screen.sh off               # blank panel (fb0=4) + backlight 0
#   sh screen.sh on                # unblank + restore saved brightness (VETOES guard)
#   sh screen.sh set 1200          # set backlight 0..4095
#   sh screen.sh offdelay 90       # turn off once, after 90s  (detached)
#   sh screen.sh toggle 90         # alternate off/on every 90s (burn-in guard)
#   sh screen.sh guard 90 20       # off after 90s, then RE-ASSERT off every 20s (detached)
#   sh screen.sh guardfg 90 20     # same but FOREGROUND (for procd supervision)
#   sh screen.sh stop              # kill any running daemon and turn the screen on
#
# OVERRIDE (why `on` sticks now): the guard re-asserts OFF every R seconds, so a
# plain one-shot `on` would be undone on the next tick. `on` therefore drops a
# VETO FLAG (/tmp/.screen.on) that the guard loop honours: while it exists the
# guard keeps the screen ON instead of off. `off` / `guard` clear the flag.
# /tmp is tmpfs, so a reboot clears it and the boot guard blanks again.
#
# Detached-safe: `sh screen.sh guard 90 20 >/dev/null 2>&1 &`

FB=/sys/class/graphics/fb0
BL=/sys/class/leds/lcd-backlight/brightness
MAXF=/sys/class/leds/lcd-backlight/max_brightness
STATE=/root/.screen.bright
PIDF=/root/.screen.pid
VETO=/tmp/.screen.on

max() { cat "$MAXF" 2>/dev/null || echo 4095; }

save_bright() {
    [ -f "$STATE" ] && return
    b=$(cat "$BL" 2>/dev/null)
    [ -n "$b" ] || b=$(max)
    echo "$b" > "$STATE"
}

do_off() {
    save_bright
    echo 0 > "$BL" 2>/dev/null
    echo 4 > "$FB/blank" 2>/dev/null || echo 1 > "$FB/blank" 2>/dev/null
}

do_on() {
    echo 0 > "$FB/blank" 2>/dev/null
    if [ -f "$STATE" ]; then cat "$STATE" > "$BL" 2>/dev/null
    else echo "$(max)" > "$BL" 2>/dev/null; fi
}

kill_prev() {
    # The offdelay/toggle/guard daemons trap HUP/INT/TERM (so they survive the
    # SSH/serial session closing). A plain `kill` = SIGTERM = IGNORED -> the
    # daemon would keep re-blanking right after `on`. Use SIGKILL (untrappable),
    # and only if the pid is really our script (guard against pid reuse).
    [ -f "$PIDF" ] || return 0
    p=$(cat "$PIDF" 2>/dev/null)
    if [ -n "$p" ] && [ -r "/proc/$p/cmdline" ] \
       && grep -qa screen.sh "/proc/$p/cmdline" 2>/dev/null; then
        kill -9 "$p" 2>/dev/null
    fi
    rm -f "$PIDF"
}

case "$1" in
status)
    echo "fb0/blank  : $(cat $FB/blank 2>/dev/null)"
    echo "brightness : $(cat $BL 2>/dev/null) / $(max)"
    echo "saved      : $(cat $STATE 2>/dev/null)"
    [ -f "$VETO" ] && echo "override   : ON (guard will keep it lit)" \
                   || echo "override   : off (guard blanks the panel)"
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then
        echo "daemon     : running (pid $(cat $PIDF))"
    else
        echo "daemon     : stopped"
    fi
    ;;
off)
    rm -f "$VETO"; do_off; echo "screen off"
    ;;
on)
    # Veto the guard FIRST, then kill any detached daemon, then light up.
    # (kill_prev is harmless if the guard runs under procd -- that instance is
    #  not tracked in the pidfile; the veto flag is what makes `on` stick.)
    touch "$VETO"; kill_prev; do_on
    echo "screen on (brightness=$(cat $STATE 2>/dev/null))"
    ;;
set)
    kill_prev; [ -n "$2" ] && echo "$2" > "$BL" 2>/dev/null && echo "brightness=$2"
    ;;
offdelay)
    N=${2:-90}
    kill_prev; rm -f "$VETO"
    (
        trap '' HUP INT TERM
        sleep "$N"
        [ -f "$VETO" ] || do_off
        echo "$(date '+%H:%M:%S') screen off after ${N}s" >> /root/screen.log
    ) >/dev/null 2>&1 &
    echo $! > "$PIDF"
    echo "offdelay started (${N}s, pid $!)"
    ;;
toggle)
    N=${2:-90}
    kill_prev; rm -f "$VETO"
    (
        trap '' HUP INT TERM
        on=1
        while :; do
            sleep "$N"
            if [ -f "$VETO" ]; then on=0; do_on
            elif [ "$on" = 1 ]; then do_off; on=0
            else do_on; on=1; fi
        done
    ) >/dev/null 2>&1 &
    echo $! > "$PIDF"
    echo "toggle started (every ${N}s, pid $!)"
    ;;
guard)
    # DETACHED boot guard. See guardfg for the procd (foreground) twin.
    N=${2:-90}; R=${3:-20}
    kill_prev; rm -f "$VETO"
    (
        trap '' HUP INT TERM
        echo "$(date '+%H:%M:%S') guard armed (off in ${N}s, re-assert ${R}s)" >> /root/screen.log
        sleep "$N"
        while :; do
            [ -f "$VETO" ] && do_on || do_off
            sleep "$R"
        done
    ) >/dev/null 2>&1 &
    echo $! > "$PIDF"
    echo "guard started (off in ${N}s, re-assert every ${R}s, pid $!)"
    ;;
guardfg)
    # FOREGROUND twin of `guard`, run by procd (burnin-guard init script).
    # procd keeps it alive and restarts it if it dies -- far more reliable than
    # backgrounding a child from an init script, which procd reaps on return.
    # The VETO flag lets `screen.sh on` win without fighting a respawned guard.
    N=${2:-90}; R=${3:-20}
    kill_prev; rm -f "$VETO"
    echo "$(date '+%H:%M:%S') guardfg armed (off in ${N}s, re-assert ${R}s)" >> /root/screen.log
    sleep "$N"
    while :; do
        [ -f "$VETO" ] && do_on || do_off
        sleep "$R"
    done
    ;;
stop)
    rm -f "$VETO"; kill_prev; do_on; echo "daemon stopped, screen on"
    ;;
*)
    echo "usage: $0 {status|off|on|set <0-4095>|offdelay [s]|toggle [s]|guard [s] [r]|guardfg [s] [r]|stop}"
    ;;
esac
