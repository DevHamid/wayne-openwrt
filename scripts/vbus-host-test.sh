#!/bin/sh
# vbus-host-test -- with policy_engine pd_vbus_ctrl=1, flip to HOST and watch
# whether VBUS comes up and an OTG device finally enumerates.
#
# CONTEXT (2026-10-16): host mode works (xHCI bus1+bus2) but a real device on
# an OTG hub never enumerates. Root cause: the port does not source 5V.
#   extcon3 (qpnp-smb2): USB=0 USB-HOST=0   -> charger never told "we are host"
#   regulator.75 smb2-vbus: disabled        -> 5V boost off
#   power_supply/usb BOOST_CURRENT=0
# regulator.75/state is 0444 (NOT writable from userspace, root or not).
# The one writable lever is the PD policy engine gate:
#   /sys/module/policy_engine/parameters/pd_vbus_ctrl  (rw, 0->1 accepted)
# Hypothesis: pd_vbus_ctrl=1 hands VBUS control to the PD stack, so the dwc3
# host role swap can raise smb2-vbus. This script tests exactly that.
#
# HARD RULE: run DETACHED, NEVER touch the USB cable while it runs (host mode
# kills both SSH and ttyGS0 -- they are the same gadget).
#   sh /root/vbus-host-test.sh >/dev/null 2>&1 &
# Log -> /root/vbus.log   (read after ~2.5 min, cable untouched)

MODE=/sys/devices/platform/soc/a800000.ssusb/mode
UDC=/sys/kernel/config/usb_gadget/g1/UDC
PE=/sys/module/policy_engine/parameters/pd_vbus_ctrl
REG=/sys/class/regulator/regulator.75/state
LOG=/root/vbus.log
HOLD=${HOLD_S:-120}

trap '' HUP INT TERM
log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

dump_state() {
    log "extcon3=$(cat /sys/class/extcon/extcon3/state 2>/dev/null | tr '\n' ' ')"
    log "extcon4=$(cat /sys/class/extcon/extcon4/state 2>/dev/null | tr '\n' ' ')"
    log "reg75=$(cat $REG 2>/dev/null) $(grep -h 'BOOST\|TYPEC_MODE\|TYPEC_POWER' /sys/class/power_supply/usb/uevent 2>/dev/null | tr '\n' ' ')"
    log "typec_ctrl=$(cat /sys/class/power_supply/usb/uevent 2>/dev/null | grep TYPEC_MODE)"
    log "usb_devs=$(ls /sys/bus/usb/devices/ 2>/dev/null | tr '\n' ' ')"
}

: > "$LOG"
log "=== vbus-host-test START ($(date)) ==="
log "pd_vbus_ctrl pre=$(cat $PE 2>/dev/null)"
echo 1 > "$PE" 2>>"$LOG" && log "pd_vbus_ctrl -> $(cat $PE 2>/dev/null)"
log "pre: mode=$(cat $MODE 2>/dev/null) udc=$(cat $UDC 2>/dev/null)"
dump_state

# ---- independent watchdog: unconditional rollback even if the body hangs ----
(
    trap '' HUP INT TERM
    sleep $((HOLD + 20))
    echo ""           > "$UDC"  2>/dev/null
    echo peripheral   > "$MODE" 2>/dev/null
    sleep 2
    echo a800000.dwc3 > "$UDC"  2>/dev/null
    log "[watchdog] rollback mode=$(cat $MODE 2>/dev/null) udc=$(cat $UDC 2>/dev/null)"
    sync
) >/dev/null 2>&1 &

echo "" > "$UDC" 2>/dev/null; sleep 1
echo host > "$MODE" 2>>"$LOG"
sleep 4
log "-- host up --"; dump_state

i=0
while [ $i -lt "$HOLD" ]; do
    sleep 5; i=$((i + 5))
    dump_state
    for d in /sys/bus/usb/devices/*/product; do
        [ -e "$d" ] || continue
        key="$(dirname "$d" | xargs basename):$(cat "$d" 2>/dev/null)"
        grep -qF "seen: $key" "$LOG" 2>/dev/null || log "seen: $key"
    done
done

log "-- dmesg tail --"
dmesg 2>/dev/null | tail -30 >> "$LOG" 2>&1

echo ""           > "$UDC"  2>/dev/null
echo peripheral   > "$MODE" 2>/dev/null
sleep 2
echo a800000.dwc3 > "$UDC"  2>/dev/null
log "=== vbus-host-test END mode=$(cat $MODE 2>/dev/null) udc=$(cat $UDC 2>/dev/null) ==="
sync
