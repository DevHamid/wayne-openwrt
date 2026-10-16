#!/bin/sh
# M6 role-switch probe with AUTO-ROLLBACK (wayne / Mi 6X, vendor kernel 4.19)
#
# WHY: switching dwc3 to HOST tears down the configfs gadget => SSH *and* the
#      ttyGS0 serial console both die. Blind test, so we install a background
#      safety net that forces PERIPHERAL back after ROLLBACK_S seconds and
#      rebinds the gadget, giving us console/SSH again to read the log.
#
# HARD RULES:
#   - gadget teardown      :  echo "" > $UDC              (SAFE, normal operation)
#   - NEVER unbind dwc3 platform driver:
#        echo a800000.dwc3 > /sys/bus/platform/drivers/dwc3/unbind   <-- PANIC. NEVER.
#
# USAGE (always background, always detached from the tty):
#   sh /root/m6.sh status                     # read-only, safe
#   sh /root/m6.sh host  >/dev/null 2>&1 &    # guarded probe, auto-rollback 60s
#   sh /root/m6.sh peripheral >/dev/null 2>&1 &   # manual return (if ever stuck)
#
# RESULTS: /root/m6.log   (on p64, survives reboot)

trap '' HUP INT TERM

MODE=/sys/devices/platform/soc/a800000.ssusb/mode
SUSB=/sys/devices/platform/soc/a800000.ssusb
UDC=/sys/kernel/config/usb_gadget/g1/UDC
LOG=/root/m6.log
ROLLBACK_S=60

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
sync_log() { sync; }

case "$1" in
status)
    echo "mode          : $(cat $MODE 2>/dev/null)"
    echo "UDC           : $(cat $UDC 2>/dev/null)"
    echo "usb_data_enab : $(cat $SUSB/usb_data_enabled 2>/dev/null)"
    echo "speed         : $(cat $SUSB/speed 2>/dev/null)"
    for e in /sys/class/extcon/extcon*; do
        echo "extcon $(cat $e/name 2>/dev/null) = $(cat $e/state 2>/dev/null | tr '\n' ' ')"
    done
    echo "usb devices   : $(ls /sys/bus/usb/devices/ 2>/dev/null | tr '\n' ' ')"
    echo "--- last log ---"; tail -25 "$LOG" 2>/dev/null
    ;;

host)
    log "=== M6 host probe START (auto-rollback in ${ROLLBACK_S}s) ==="
    log "pre : mode=$(cat $MODE) udc=$(cat $UDC) data=$(cat $SUSB/usb_data_enabled)"

    # ---- SAFETY NET: no matter what, return to peripheral + rebind gadget ----
    (
        trap '' HUP INT TERM
        sleep "$ROLLBACK_S"
        echo ""           > "$UDC"  2>/dev/null
        echo peripheral   > "$MODE" 2>/dev/null
        sleep 2
        echo a800000.dwc3 > "$UDC"  2>/dev/null
        sync
        echo "[rollback] mode=$(cat $MODE) udc=$(cat $UDC)" >> "$LOG"
        sync
    ) &
    NET=$!

    # ---- clean teardown, then flip role ----
    echo ""     > "$UDC"
    sleep 1
    log "udc after teardown: [$(cat $UDC)]"
    echo host   > "$MODE" 2>>"$LOG"
    sleep 4

    log "post: mode=$(cat $MODE 2>/dev/null) data=$(cat $SUSB/usb_data_enabled 2>/dev/null)"
    log "-- usb bus devices --"
    ls -l /sys/bus/usb/devices/ >> "$LOG" 2>&1
    log "-- device products --"
    for d in /sys/bus/usb/devices/*/product; do
        [ -e "$d" ] && log "  $(dirname $d | xargs basename): $(cat $d)"
    done
    log "-- dmesg tail --"
    dmesg | tail -45 >> "$LOG" 2>&1
    sync

    log "waiting ${ROLLBACK_S}s for rollback (console/SSH return after it)"
    wait $NET
    log "=== M6 host probe END ==="
    sync
    ;;

peripheral|device)
    log "manual return to peripheral"
    echo ""           > "$UDC"  2>/dev/null
    echo peripheral   > "$MODE" 2>/dev/null
    sleep 2
    echo a800000.dwc3 > "$UDC"  2>/dev/null
    sync
    log "now: mode=$(cat $MODE) udc=$(cat $UDC)"
    ;;

*)
    echo "usage: $0 {status|host|peripheral}"
    ;;
esac
