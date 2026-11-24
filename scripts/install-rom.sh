#!/bin/sh
# wayne ROM upgrade — run ON the phone from the running OpenWrt.
# The running root IS /dev/mmcblk0p61 (system), so we cannot format it.
# Strategy: extract the new rootfs to tmpfs, apply over the live root with tar
# (overwrite-in-place), preserve /etc/config, then flash the new boot and reboot.
# Writes ONLY: boot (mmcblk0p58) + files under / (system partition).
# Never touches: userdata, modem firmware, persist/EFS, modemst1/2, fsc/fsg.
set -e

NEW=/tmp/newroot
echo "[1/7] extract new rootfs to tmpfs"
rm -rf "$NEW"; mkdir -p "$NEW"
tar -xzf /tmp/rootfs.tar.gz -C "$NEW"
test -e "$NEW/sbin/init" || { echo "FATAL: new rootfs missing /sbin/init"; exit 1; }
test -x "$NEW/usr/sbin/ModemManager" || { echo "FATAL: ModemManager missing"; exit 1; }
test -e "$NEW/etc/init.d/modemmanager" || { echo "FATAL: modemmanager init missing"; exit 1; }
test -e "$NEW/etc/init.d/diag-reader" || { echo "FATAL: diag-reader init missing"; exit 1; }
echo "      new rootfs OK (ModemManager + modemmanager + diag-reader present)"

echo "[2/7] back up current /etc/config"
rm -rf /tmp/config-backup; mkdir -p /tmp/config-backup
cp -a /etc/config/* /tmp/config-backup/ 2>/dev/null || true

echo "[3/7] apply new rootfs over the live root (tar overwrite)"
tar -xzf /tmp/rootfs.tar.gz -C /

echo "[4/7] restore network/usb config"
cp -a /tmp/config-backup/* /etc/config/ 2>/dev/null || true

echo "[5/7] flash boot (mmcblk0p58)"
dd if=/tmp/boot.img of=/dev/mmcblk0p58 bs=4k
sync

echo "[6/7] verify boot written"
sha256sum /dev/mmcblk0p58 | head -c 64; echo
sha256sum /tmp/boot.img   | head -c 64; echo

echo "[7/7] reboot into upgraded ROM"
sleep 2
reboot
