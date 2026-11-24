#!/bin/sh
# LTE data-call bring-up via ModemManager (qcom-soc over QRTR) on wayne.
# Run ON the phone after the ModemManager ROM is up.
set -x
systemctl_status() { /etc/init.d/modemmanager status; }
# 1) wait for the modem to be enumerated by ModemManager
for i in $(seq 1 30); do
  L=$(mmcli -L 2>/dev/null)
  echo "$L"
  echo "$L" | grep -qE "Modem[^0-9]*[0-9]+" && break
  sleep 5
done
M=$(mmcli -L | grep -oE "/org/freedesktop/ModemManager1/Modem/[0-9]+" | head -1)
[ -n "$M" ] || { echo "NO MODEM"; exit 1; }
echo "modem path: $M"
mmcli -m "${M##*/}"
# 2) enable the modem
mmcli -m "${M##*/}" -e
# 3) create a bearer with a generic APN (attach APN from the SIM usually works: leave APN empty)
mmcli -m "${M##*/}" --create-bearer="apn=internet,ip-type=ipv4"
B=$(mmcli -m "${M##*/}" --list-bearers | grep -oE "/org/freedesktop/ModemManager1/Bearer/[0-9]+" | head -1)
echo "bearer: $B"
mmcli -b "${B##*/}" -c
mmcli -b "${B##*/}"
# 4) check the data interface
ip link | grep -E "rmnet|wwan|usb"
