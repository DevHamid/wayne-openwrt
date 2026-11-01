#!/bin/sh
# wayne-diag.sh -- full subsystem snapshot, one shot, one paste.
# busybox ash safe. Writes /tmp/wayne-diag/report.txt and prints it.
D=/tmp/wayne-diag
mkdir -p "$D"

{
echo "########## 1. BUILD ##########"
uname -a
cat /proc/version 2>/dev/null
echo "--- cmdline ---"
cat /proc/cmdline
echo "--- uptime ---"
cat /proc/uptime

echo
echo "########## 2. KERNEL CONFIG (subsystem symbols) ##########"
zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_(ICNSS|CNSS|QCA_CLD|WCNSS|QMI|PIL|SUBSYSTEM|RMTFS|SERVICE_LOC|SCM|SMEM|SMP2P|DEBUG_FS|CFG80211|MAC80211|REMOTEPROC|ATH|RPMSG|GLINK)' | sort

echo
echo "########## 3. DMESG -- SUBSYSTEM BRING-UP ##########"
dmesg 2>/dev/null | grep -iE 'icnss|cnss|wlan|pld|qmi|servreg|servloc|pdr|rmtfs|smem|smp2p| scm |pil-|subsys|modem| mss |wcnss|adsp|cdsp|turing|venus|remoteproc|hyp|tz |panic|oops|BUG:|call trace'

echo
echo "########## 4. DMESG -- FIRST 60 LINES (context) ##########"
dmesg 2>/dev/null | head -60

echo
echo "########## 5. PLATFORM DRIVER BINDINGS ##########"
for d in pil-q6v5-mss icnss icnss2 cnss2 rmtfs_mem msm_sharedmem qcom,scm; do
  printf '%-18s ' "$d"
  if [ -d "/sys/bus/platform/drivers/$d" ]; then
    echo "PRESENT: $(ls /sys/bus/platform/drivers/$d/ 2>/dev/null | tr '\n' ' ')"
  else
    echo "(absent)"
  fi
done

echo
echo "########## 6. REMOTEPROC / SUBSYS CLASSES ##########"
echo "--- remoteproc ---"
ls -la /sys/class/remoteproc/ 2>&1
for f in /sys/class/remoteproc/remoteproc*/name; do
  [ -f "$f" ] && echo "  $f = $(cat "$f" 2>/dev/null)"
done
echo "--- subsys ---"
ls /sys/class/subsys/ 2>&1

echo
echo "########## 7. DEVICE TREE ##########"
echo "--- soc/ subsystem nodes ---"
ls /proc/device-tree/soc/ 2>/dev/null | grep -iE 'modem|mss|wlan|wcnss|smem|rmtfs|smp2p|scm|pil|q6'
echo "--- icnss@18800000 props ---"
ls /proc/device-tree/soc/icnss@18800000/ 2>/dev/null | tr '\n' ' '; echo
echo "--- mss@4080000 props ---"
ls /proc/device-tree/soc/qcom,mss@4080000/ 2>/dev/null | tr '\n' ' '; echo
echo "--- reserved-memory ---"
ls /proc/device-tree/reserved-memory/ 2>/dev/null | tr '\n' ' '; echo
echo "--- icnss compatible ---"
cat /proc/device-tree/soc/icnss@18800000/compatible 2>/dev/null; echo
echo "--- mss compatible ---"
cat /proc/device-tree/soc/qcom,mss@4080000/compatible 2>/dev/null; echo

echo
echo "########## 8. FIRMWARE ON DISK ##########"
ls -la /lib/firmware/ 2>/dev/null
echo "--- wlan/wcnss matches ---"
find /lib/firmware /vendor/firmware -iname '*wlan*' -o -iname '*bdwlan*' -o -iname '*wcnss*' 2>/dev/null

echo
echo "########## 9. NETWORK / CFG80211 STATE ##########"
ip -d link 2>/dev/null || ip link 2>/dev/null
echo "--- ieee80211 phys ---"
ls -la /sys/class/ieee80211/ 2>&1
echo "--- net interfaces ---"
ls /sys/class/net/ 2>/dev/null | tr '\n' ' '; echo

echo
echo "########## 10. SIZE ##########"
echo "full dmesg lines: $(dmesg 2>/dev/null | wc -l)"
} > "$D/report.txt" 2>&1

echo "written: $D/report.txt ($(wc -l < "$D/report.txt") lines)"
echo "=================================================="
cat "$D/report.txt"
