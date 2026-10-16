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
#   sh screen.sh on                # unblank + restore saved brightness
#   sh screen.sh set 1200          # set backlight 0..4095
#   sh screen.sh offdelay 90       # turn off once, after 90s  (detached)
#   sh screen.sh toggle 90         # alternate off/on every 90s (burn-in guard)
#   sh screen.sh stop              # kill any running offdelay/toggle
#
# Detached-safe: `sh screen.sh offdelay 90 >/dev/null 2>&1 &`

FB=/sys/class/graphics/fb0
BL=/sys/class/leds/lcd-backlight/brightness
MAXF=/sys/class/leds/lcd-backlight/max_brightness
STATE=/root/.screen.bright
PIDF=/root/.screen.pid

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
    [ -f "$PIDF" ] && kill "$(cat $PIDF)" 2>/dev/null
    rm -f "$PIDF"
}

case "$1" in
status)
    echo "fb0/blank  : $(cat $FB/blank 2>/dev/null)"
    echo "brightness : $(cat $BL 2>/dev/null) / $(max)"
    echo "saved      : $(cat $STATE 2>/dev/null)"
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then
        echo "daemon     : running (pid $(cat $PIDF))"
    else
        echo "daemon     : stopped"
    fi
    ;;
off)
    do_off; echo "screen off"
    ;;
on)
    do_on; echo "screen on (brightness=$(cat $STATE 2>/dev/null))"
    ;;
set)
    [ -n "$2" ] && echo "$2" > "$BL" 2>/dev/null && echo "brightness=$2"
    ;;
offdelay)
    N=${2:-90}
    kill_prev
    (
        trap '' HUP INT TERM
        echo $$ > "$PIDF"
        sleep "$N"
        do_off
        echo "$(date '+%H:%M:%S') screen off after ${N}s" >> /root/screen.log
        rm -f "$PIDF"
    ) >/dev/null 2>&1 &
    echo "offdelay started (${N}s, pid $!)"
    ;;
toggle)
    N=${2:-90}
    kill_prev
    (
        trap '' HUP INT TERM
        echo $$ > "$PIDF"
        on=1
        while :; do
            sleep "$N"
            if [ "$on" = 1 ]; then do_off; on=0
            else do_on; on=1; fi
        done
    ) >/dev/null 2>&1 &
    echo "toggle started (every ${N}s, pid $!)"
    ;;
stop)
    kill_prev; do_on; echo "daemon stopped, screen on"
    ;;
*)
    echo "usage: $0 {status|off|on|set <0-4095>|offdelay [s]|toggle [s]|stop}"
    ;;
esac
