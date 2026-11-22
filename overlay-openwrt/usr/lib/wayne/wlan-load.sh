#!/bin/sh
# /usr/lib/wayne/wlan-load.sh -- bring the WCN3990 (qcacld) WLAN stack up
# AFTER the modem/WPSS is online. Runs once, supervised by init.d/wayne-wlan.
#
# WHY A LATE MODULE LOAD IS REQUIRED
# ----------------------------------
# The WLAN domain is a subdomain of the MODEM (wlan_pd): Wi-Fi rides the modem's
# QRTR/QMI transport and has no radio channel of its own. So the sequence is:
#   modem PD online  -> WLFW QMI service (id 69) registers on the QRTR bus
#                    -> icnss (built-in) gets the server-arrival, reaches
#                       ICNSS_FW_READY, then calls its registered driver probe
#                    -> qcacld must be REGISTERED by then to be probed.
#
# icnss is =y and pends "FW is not ready yet" until the WLFW service arrives.
# qcacld is built as a MODULE (CONFIG_QCA_CLD_WLAN=m on debug/wayne-wlan-sfr-v2)
# so it can be loaded here, late -- a built-in wlan driver would have run its
# one-shot probe at kernel init, before the modem existed, and could never be
# re-probed. Nothing in the base rootfs loads wlan.ko, so without this step
# there is no PHY and no AP.
#
# SAFETY: read-only. Loads/unloads only wlan.ko and reads sysfs/dmesg. It never
# writes a partition, EFS or calibration data.
LOG=/root/wlan-load.log
WAIT_MODEM=45     # s to wait for the modem PD to reach ONLINE
WAIT_FW=60        # s to wait for icnss to report FW-ready after the modem is up
MAX_ATTEMPTS=3    # qcacld probe can return -EPROBE_DEFER if it races FW-ready

say() { echo "$(date '+%H:%M:%S') $*"; }
phy_present() { [ -n "$(ls /sys/class/ieee80211 2>/dev/null)" ]; }
fw_ready() { dmesg 2>/dev/null | grep -qE 'WLAN FW is ready|stage=FW_READY'; }
modem_up() {
    for s in /sys/bus/msm_subsys/devices/*/state; do
        [ -r "$s" ] || continue
        case "$(cat "$s" 2>/dev/null)" in *ONLINE*|*RUNNING*) return 0 ;; esac
    done
    # Fall back to the modem-boot trigger's own device node when there is no
    # msm_subsys entry on this tree.
    [ -e /sys/class/modem-boot/modem0/boot ] && return 0
    return 1
}
modload() {
    modprobe wlan 2>/dev/null && return 0
    ko=$(find /lib/modules -name 'wlan.ko' 2>/dev/null | head -1)
    [ -n "$ko" ] && insmod "$ko" 2>&1
}

{
    say "=== wayne-wlan load start ==="
    if phy_present; then
        say "PHY already present: $(ls /sys/class/ieee80211)"; exit 0
    fi
    if ! find /lib/modules -name 'wlan.ko' 2>/dev/null | grep -q .; then
        say "wlan.ko not shipped in /lib/modules -- this kernel has qcacld =y or"
        say "the module was not installed. Nothing to load; exiting."
        exit 0
    fi

    i=0; while [ "$i" -lt "$WAIT_MODEM" ] && ! modem_up; do sleep 1; i=$((i+1)); done
    say "modem_up: $([ "$i" -lt "$WAIT_MODEM" ] && echo yes || echo no) (${i}s)"

    j=0; while [ "$j" -lt "$WAIT_FW" ] && ! fw_ready; do sleep 1; j=$((j+1)); done
    say "icnss_fw_ready: $(fw_ready && echo yes || echo no) (${j}s)"

    n=0
    while [ "$n" -lt "$MAX_ATTEMPTS" ]; do
        say "modprobe wlan (attempt $((n+1)))"
        modload
        sleep 3
        phy_present && break
        say "no PHY yet; unloading wlan for a clean retry"
        rmmod wlan 2>/dev/null
        sleep 1
        n=$((n+1))
    done

    if phy_present; then
        say "RESULT phy=$(ls /sys/class/ieee80211)"
    else
        say "RESULT phy=none (see dmesg tail below; run /root/wifi-diag.sh)"
    fi
    say "--- dmesg tail (qrtr/icnss/wlfw/wlan) ---"
    dmesg 2>/dev/null | grep -aiE 'qrtr|icnss|wlfw|qcacld|wlan' | tail -60
    say "=== wayne-wlan load end ==="
} >>"$LOG" 2>&1
