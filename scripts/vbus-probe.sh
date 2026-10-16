#!/bin/sh
# vbus-probe v2 -- OTG 5V (smb2-vbus) investigation, HARDENED.
#
# v1 lesson (2026-10-16): a host-mode dump can HANG on a sysfs read (the port
# is electrically dead to the PC and dwc3 is mid-transition). When it hung it
# never reached its own rollback line -> UDC left empty -> BOTH ssh and ttyGS0
# die (same gadget). Only a reboot restores it. So v2:
#   * starts an INDEPENDENT watchdog that forces peripheral at T+25s no matter
#     what the main body does -- if main hangs, the phone still comes back;
#   * drops `find /sys` (the likely hang) -- only explicit nodes are read;
#   * every sysfs read/write is wrapped in `timeout` when busybox has it.
#
# Run DETACHED.  NEVER touch the USB cable while this runs.
#   sh /root/vbus-probe.sh >/dev/null 2>&1 &
# Log -> /root/vbus.log   (read after ~40s, cable untouched)

MODE=/sys/devices/platform/soc/a800000.ssusb/mode
UDC=/sys/kernel/config/usb_gadget/g1/UDC
REG=/sys/class/regulator/regulator.75/state
LOG=/root/vbus.log
UDC_NAME=a800000.dwc3

trap '' HUP INT TERM

have_timeout() { command -v timeout >/dev/null 2>&1; }

# rd FILE -- bounded read
rd() { if have_timeout; then timeout 3 cat "$1" 2>/dev/null; else cat "$1" 2>/dev/null; fi; }

restore() {
    [ -w "$UDC" ] && echo "" > "$UDC" 2>/dev/null
    sleep 1
    [ -w "$MODE" ] && echo peripheral > "$MODE" 2>/dev/null
    sleep 2
    [ -w "$UDC" ] && echo "$UDC_NAME" > "$UDC" 2>/dev/null
}

# ---- independent watchdog: fires at T+25s even if main hangs ----
(
    trap '' HUP INT TERM
    sleep 25
    echo "[watchdog] T+25 firing, forcing peripheral" >> "$LOG"
    restore
    echo "[watchdog] restore done mode=$(rd $MODE) udc=$(rd $UDC)" >> "$LOG"
    sync
) >/dev/null 2>&1 &

{
    echo "===== vbus-probe v2 start $(date) pid=$$ ====="
    echo "pre: mode=$(rd $MODE) udc=$(rd $UDC)"

    echo "" > "$UDC" 2>/dev/null; sleep 1
    echo host > "$MODE" 2>/dev/null
    echo "flipped host, waiting 9s for xHCI..."
    sleep 9

    echo "== EXTCON (state + name) =="
    for e in /sys/class/extcon/extcon0 /sys/class/extcon/extcon1 /sys/class/extcon/extcon2 /sys/class/extcon/extcon3 /sys/class/extcon/extcon4; do
        [ -d "$e" ] || continue
        echo "-- $e name=$(rd $e/name)"
        cat "$e/state" 2>/dev/null
    done

    echo "== TARGET REG (regulator.75 smb2-vbus) =="
    echo "name=$(rd /sys/class/regulator/regulator.75/name)"
    echo "state=$(rd $REG)"
    echo "dir:"; ls /sys/class/regulator/regulator.75/ 2>/dev/null

    echo "== POWER_SUPPLY =="
    ls /sys/class/power_supply/ 2>/dev/null
    for p in /sys/class/power_supply/*; do
        [ -d "$p" ] || continue
        echo "-- $(basename $p)"
        grep -iE 'otg|boost|vbus|online|type|role|present|usb' "$p/uevent" 2>/dev/null
    done

    echo "== WRITE regulator.75 state=1 (force 5V) =="
    err=$( (echo 1 > "$REG") 2>&1 ); rc=$?
    echo "rc=$rc err=$err"
    echo "state now=$(rd $REG)"
    sleep 4

    echo "== USBDEV after write =="
    ls /sys/bus/usb/devices/ 2>/dev/null
    for d in /sys/bus/usb/devices/*/product; do
        [ -f "$d" ] && echo "$d: $(rd $d)"
    done

    echo "== dmesg tail =="
    dmesg 2>/dev/null | tail -25

    echo "== EXTCON after =="
    for e in /sys/class/extcon/extcon0 /sys/class/extcon/extcon1 /sys/class/extcon/extcon2 /sys/class/extcon/extcon3 /sys/class/extcon/extcon4; do
        [ -d "$e" ] || continue
        echo "-- $e"; cat "$e/state" 2>/dev/null
    done

    echo "== main restore =="
    echo 0 > "$REG" 2>/dev/null
    restore
    echo "== vbus-probe v2 end $(date) mode=$(rd $MODE) udc=$(rd $UDC) =="
    sync
} >> "$LOG" 2>&1
