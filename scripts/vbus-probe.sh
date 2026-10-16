#!/bin/sh
# vbus-probe: flip to host, try to force OTG 5V (smb2-vbus) on, capture all to /root/vbus.log
# Run DETACHED: the flip kills both SSH and ttyGS0.  sh /root/vbus-probe.sh >/dev/null 2>&1 &
MODE=/sys/devices/platform/soc/a800000.ssusb/mode
UDC=/sys/kernel/config/usb_gadget/g1/UDC
LOG=/root/vbus.log
trap '' HUP INT TERM
{
echo "== pre: mode=$(cat $MODE) udc=$(cat $UDC)"
echo "" > $UDC; sleep 1
echo host > $MODE; sleep 9
echo "== EXTCON =="; cat /sys/class/extcon/extcon*/state
echo "== EXTCON names =="; for e in /sys/class/extcon/extcon*; do echo "$e $(cat $e/name 2>/dev/null)"; done
echo "== REGS usb/vbus/otg/5v =="; for r in /sys/class/regulator/*; do n=$(cat $r/name 2>/dev/null); case "$n" in *vbus*|*otg*|*5v*|*usb*) echo "$r $n state=$(cat $r/state 2>/dev/null)";; esac; done
echo "== regulator.75 dir =="; ls /sys/class/regulator/regulator.75/ 2>/dev/null
echo "== POWER_SUPPLY =="; ls /sys/class/power_supply/; for p in /sys/class/power_supply/*; do echo "-- $(basename $p)"; grep -iE 'otg|boost|vbus|online|type|role|present|usb' $p/uevent 2>/dev/null; done
echo "== FIND otg/vbus nodes =="; find /sys -maxdepth 6 \( -name '*otg*' -o -name '*vbus*' \) 2>/dev/null | head -30
echo "== TRY regulator.75 write 1 =="
echo 1 > /sys/class/regulator/regulator.75/state 2>/tmp/e1; echo "state<-1 rc=$? err=$(cat /tmp/e1)"
sleep 4
echo "== dmesg after write =="; dmesg | tail -25
echo "== USBDEV after write =="; ls /sys/bus/usb/devices/; for d in /sys/bus/usb/devices/*/product; do echo "$d: $(cat $d 2>/dev/null)"; done
echo 0 > /sys/class/regulator/regulator.75/state 2>/dev/null
echo "== EXTCON after =="; cat /sys/class/extcon/extcon*/state
echo "" > $UDC; echo peripheral > $MODE; sleep 2; echo a800000.dwc3 > $UDC
echo "== rollback: mode=$(cat $MODE) udc=$(cat $UDC)"
sync
} > $LOG 2>&1
