#!/bin/sh
# /root/wifi-diag.sh -- WCN3990 / qcacld bring-up diagnostic for the wayne
# (Mi 6X, SDM660) vendor 4.19 tree.
#
# WHY THIS EXISTS
# ---------------
# The WLAN domain is a SUBDOMAIN OF THE MODEM (wlan_pd). Wi-Fi has no channel
# of its own: it rides the same QRTR/QMI transport the modem uses. So Wi-Fi
# cannot come up unless, IN ORDER:
#
#   (A) the modem is UP and the QRTR transport works
#   (B) the in-kernel QRTR service registry delivers the WLFW service (id 69)
#   (C) icnss (built-in) sees the WLFW service arrive, sets ICNSS_FW_READY,
#       then calls the qcacld driver's probe registrant
#   (D) qcacld (wlan.ko) is LOADED and registers with icnss
#   (E) qcacld probes -> a wiphy appears in /sys/class/ieee80211
#   (F) hostapd/wpad brings the AP up
#
# icnss is =y (built-in) and pends "FW is not ready yet" until (B) happens, so
# a boot without the registry silently dead-ends at (B) -- no PHY, no error.
# And even with the registry, wlan.ko must be modprobe'd after icnss is up;
# nothing in the base rootfs does that. This script prints each layer so the
# break point is unambiguous.
echo "===== wifi-diag (wayne WCN3990 bring-up) ====="

echo "--- [A] modem QRTR transport ---"
echo -n "  modem state: "; cat /sys/bus/msm_subsys/devices/subsys0/state 2>/dev/null || echo "(no msm_subsys node)"
ls /dev/qrtr* 2>/dev/null || echo "  no /dev/qrtr* (the ns socket may not be open yet)"
dmesg 2>/dev/null | grep -aiE 'qcom_smd_qrtr|qrtr' | tail -8 || true

echo "--- [B] QRTR service registry + WLFW service arrival ---"
echo -n "  registry present? "; \
  { grep -aq 'qrtr_svc_record' /proc/kallsyms 2>/dev/null && echo yes || echo "NO (kernel lacks the in-kernel service registry)"; }
echo -n "  WLFW service (id 69) announced? "; \
  { dmesg 2>/dev/null | grep -aqiE 'WLFW server arrive|wlfw.*arrive' && echo yes || echo "NOT seen in dmesg"; }
dmesg 2>/dev/null | grep -aiE 'WLFW server arrive|qmi.*WLFW' | tail -10 || true

echo "--- [C] icnss state (built-in; waits for WLFW) ---"
ls -d /sys/bus/platform/drivers/icnss* 2>/dev/null || echo "  (no icnss driver dir)"
dmesg 2>/dev/null | grep -aiE 'ICNSS-TRACE|icnss|WLAN FW is ready|FW is not ready|Platform driver probed|Driver probe failed' | tail -25 || true

echo "--- [D] qcacld module (wlan.ko) loaded? ---"
if lsmod 2>/dev/null | grep -q '^wlan '; then
    echo "  wlan.ko: LOADED"; lsmod | grep -E '^wlan |^cfg80211|^mac80211|^compat'
else
    echo "  wlan.ko: NOT LOADED"
    ko=$(find /lib/modules -name 'wlan.ko' 2>/dev/null | head -1)
    if [ -n "$ko" ]; then
        echo "  shipped at: $ko  (run: modprobe wlan)"
    else
        echo "  NOT shipped in /lib/modules (kernel built qcacld =y, or not at all)"
    fi
    dmesg 2>/dev/null | grep -aiE 'wlan_hdd_state|wlan major|qcacld' | tail -10 || true
fi

echo "--- [E] wiphy / PHY ---"
if [ -d /sys/class/ieee80211 ] && [ -n "$(ls -A /sys/class/ieee80211 2>/dev/null)" ]; then
    for p in /sys/class/ieee80211/*/; do [ -d "$p" ] && echo "  PHY: $(basename "$p")"; done
else
    echo "  NO PHY (see B/C/D above for the first broken layer)"
fi

echo "--- [F] userspace (iw / hostapd) ---"
which iw >/dev/null 2>&1 && iw dev 2>&1 || echo "  iw not installed"
pgrep -a hostapd || pgrep -a wpad || echo "  hostapd/wpad not running"
uci -q show wireless 2>/dev/null | head -40 || echo "  no wireless config"
echo -n "  net ifaces (wlan*): "; ls /sys/class/net 2>/dev/null | grep -E '^wlan|^wlp' || echo "none"

echo "--- wlan firmware files (expected /lib/firmware/wlan/qca_cld/) ---"
ls -la /lib/firmware/wlan/qca_cld/ 2>/dev/null || echo "  MISSING: /lib/firmware/wlan/qca_cld/"
find /lib/firmware -maxdepth 3 \( -iname '*wlan*' -o -iname '*bdwlan*' \) 2>/dev/null | head -20

echo "=================================================="
echo "READ TOP-DOWN -- the first layer that is not ok is the blocker:"
echo "  B 'NO registry'        -> build with kernel_ref=debug/wayne-wlan-sfr-v2"
echo "  D 'NOT LOADED'         -> the wlan loader has not run; modprobe wlan"
echo "  C 'FW is not ready yet'-> WLFW service (id 69) never arrived on QRTR"
echo "  E no PHY, A-D ok       -> qcacld probed but firmware/BDF mismatch"
