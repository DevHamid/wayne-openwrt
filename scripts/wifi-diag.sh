#!/bin/sh
# /root/wifi-diag.sh -- wifi bring-up diagnostic. Prints the exact state of
# every layer that must work for the WCN3990 AP to come up on this vendor
# 4.19 tree. Run this when `wifi up` doesn't produce an AP.
#
# Layers, in order:
#   1. icnss/PIL QMI driver bound?   (dmesg / sysfs)
#   2. WLANMDSP.MBN visible + loaded? (fw files + remoteproc/PIL state)
#   3. qcacld driver probe?            (ieee80211 phy present)
#   4. mac80211 radio up?              (iw dev)
#   5. hostapd config + status.        (config + procd)
echo "===== wifi-diag (wanne WCN3990 bring-up) ====="

echo "--- [1] icnss / PIL / WLAN driver bind ---"
ls /sys/bus/platform/drivers/ 2>/dev/null | grep -iE 'icnss|qca|wlan|pil|cc' || echo "  (no icnss/cc driver dir)"
dmesg 2>/dev/null | grep -iE 'icnss|pil|wlan|wcnss|qca' | tail -40 || true

echo "--- [2] wlan firmware files on disk (expected /lib/firmware/wlan/qca_cld/) ---"
ls -la /lib/firmware/wlan/qca_cld/ 2>/dev/null || echo "  MISSING: /lib/firmware/wlan/qca_cld/ (stage WLANMDSP.MBN / bdwlan*)"
find /lib/firmware -maxdepth 3 -iname '*wlan*' -o -iname '*bdwlan*' 2>/dev/null | head -20

echo "--- [3] phy present? ---"
ls /sys/class/ieee80211/ 2>/dev/null || echo "  NO PHY: qcacld did not probe (see [1])"
for p in /sys/class/ieee80211/*/; do
    [ -d "$p" ] && echo "  phy: $(basename "$p")"
done

echo "--- [4] iw / mac80211 interfaces ---"
which iw >/dev/null 2>&1 && iw dev 2>&1 || echo "  iw not installed"

echo "--- [5] hostapd status ---"
pgrep -a hostapd || echo "  hostapd not running"
uci -q show wireless 2>/dev/null | head -40 || echo "  no wireless config"

echo "=================================================="
