#!/bin/sh
# m7.sh -- M7 Docker-on-4.19 feasibility probe (wayne / Mi 6X)
#
# WHY: M7 is "open probe, not a promise" (README roadmap). Answer it with
# ground truth from the running kernel instead of guessing from a defconfig.
#   CONFIG_MEMCG / CGROUP_* were ADDED to kernel-config-fragment (v0.9.10) but
#   a config line only proves compilation -- /proc and a real mount prove the
#   running kernel actually exposes the feature to dockerd/runc.
#
# USAGE (ONE line, serial-safe):
#   sh /root/m7.sh            # prints summary AND writes /root/m7.log
#
# Scope: READ-ONLY except temporary probe objects it removes again (veth pair,
# one bridge, one overlay mount, cgroup mounts). It never touches USB (dwc3),
# the display, or any partition.
#
# Verdict rules (mirrors what dockerd/runc actually require):
#   FATAL   : no memcg (dockerd: "kernel does not support memory limit
#             capabilities"), no overlayfs (no overlay2 storage driver),
#             no net/mnt/pid namespaces, no seccomp
#   DEGRADED: no freezer/pids/device controllers, no veth (no container net),
#             no br_netfilter (documented: LKGeek dropped it)
# The final line is the answer M7 needs: M7=YES / M7=DEGRADED / M7=NO.

LOG=/root/m7.log
: > "$LOG"
log() { echo "$*" >> "$LOG"; echo "$*"; }

fatal=0
degraded=0

log "=== M7 Docker probe $(date) ==="
log "kernel : $(uname -a)"

# --- 1. cgroup controllers the kernel reports -----------------------------
log "--- /proc/cgroups ---"
if [ -r /proc/cgroups ]; then
    cat /proc/cgroups >> "$LOG"
    cat /proc/cgroups
else
    log "MISSING /proc/cgroups (cgroup v1 core off)"
    fatal=$((fatal+1))
fi

for ctl in memory freezer pids devices; do
    if grep -q "^$ctl" /proc/cgroups 2>/dev/null; then
        log "PASS controller listed: $ctl"
    else
        log "FAIL controller not listed: $ctl"
        case "$ctl" in
            memory) fatal=$((fatal+1)) ;;
            *)      degraded=$((degraded+1)) ;;
        esac
    fi
done

# --- 2. memory cgroup: mount it and WRITE a limit (proof, not just listing)
mkdir -p /tmp/m7/mem
if mount -t cgroup -o memory none /tmp/m7/mem 2>>"$LOG"; then
    log "PASS memcg mounted at /tmp/m7/mem"
    if echo 67108864 > /tmp/m7/mem/memory.limit_in_bytes 2>>"$LOG"; then
        log "PASS memcg accepts a limit: $(cat /tmp/m7/mem/memory.limit_in_bytes)"
    else
        log "FAIL memcg will not accept memory.limit_in_bytes"
        fatal=$((fatal+1))
    fi
    umount /tmp/m7/mem 2>/dev/null
else
    log "FAIL cgroup memory mount failed"
    fatal=$((fatal+1))
fi

# --- 3. freezer + pids (dockerd pause/resume + pid limits) ----------------
for ctl in freezer pids; do
    mkdir -p "/tmp/m7/$ctl"
    if mount -t cgroup -o "$ctl" none "/tmp/m7/$ctl" 2>>"$LOG"; then
        log "PASS $ctl mounted"
        umount "/tmp/m7/$ctl" 2>/dev/null
    else
        log "FAIL $ctl mount failed"
        degraded=$((degraded+1))
    fi
done

# --- 4. device cgroup (dockerd blocks devices by default) -----------------
mkdir -p /tmp/m7/devices
if mount -t cgroup -o devices none /tmp/m7/devices 2>>"$LOG"; then
    log "PASS devices cgroup mounted"
    umount /tmp/m7/devices 2>/dev/null
else
    log "FAIL devices cgroup mount failed (docker run --device unavailable)"
    degraded=$((degraded+1))
fi

# --- 5. namespaces --------------------------------------------------------
log "--- namespaces ---"
log "ns: $(ls -1 /proc/self/ns/ 2>/dev/null | tr '\n' ' ')"
for ns in net mnt pid uts ipc; do
    if [ -e "/proc/self/ns/$ns" ]; then
        log "PASS namespace present: $ns"
    else
        log "FAIL namespace missing: $ns"
        fatal=$((fatal+1))
    fi
done
# A fresh net ns must actually open, not merely exist as a symlink.
if unshare -n true 2>>"$LOG"; then
    log "PASS unshare -n works (kernel creates a fresh net namespace)"
else
    log "FAIL unshare -n rejected"
    fatal=$((fatal+1))
fi

# --- 6. seccomp (runc default; absent => dockerd must run unconfined) -----
if grep -q '^Seccomp:[[:space:]]*[12]' /proc/self/status 2>/dev/null; then
    log "PASS seccomp available: $(grep '^Seccomp:' /proc/self/status)"
else
    log "WARN seccomp not usable: $(grep '^Seccomp:' /proc/self/status 2>/dev/null)"
    degraded=$((degraded+1))
fi

# --- 7. overlayfs: real mount + real file, on the real root filesystem ----
log "--- overlay2 test (root fs: $(awk '$2=="/"{print $3}' /proc/mounts | head -1)) ---"
mkdir -p /tmp/m7/ov/lower /tmp/m7/ov/upper /tmp/m7/ov/work /tmp/m7/ov/merged
echo "from-lower" > /tmp/m7/ov/lower/f
if mount -t overlay overlay -o lowerdir=/tmp/m7/ov/lower,upperdir=/tmp/m7/ov/upper,workdir=/tmp/m7/ov/work /tmp/m7/ov/merged 2>>"$LOG"; then
    log "PASS overlay mounted"
    if [ "$(cat /tmp/m7/ov/merged/f 2>/dev/null)" = "from-lower" ]; then
        log "PASS overlay lower read works"
    else
        log "FAIL overlay merged dir does not expose lower file"
        degraded=$((degraded+1))
    fi
    echo "written-upper" > /tmp/m7/ov/merged/g 2>>"$LOG"
    if [ -f /tmp/m7/ov/upper/g ]; then
        log "PASS overlay copy-up write works"
    else
        log "FAIL overlay copy-up write failed (overlay2 unusable here)"
        fatal=$((fatal+1))
    fi
    umount /tmp/m7/ov/merged 2>/dev/null
else
    log "FAIL overlay mount failed (overlay2 storage driver impossible)"
    fatal=$((fatal+1))
fi
rm -rf /tmp/m7/ov

# --- 8. veth (container networking) ---------------------------------------
if ip link add m7v0 type veth peer name m7v1 2>>"$LOG"; then
    log "PASS veth pair created"
    ip link del m7v0 2>/dev/null
else
    log "FAIL veth create failed (no container networking)"
    degraded=$((degraded+1))
fi

# --- 9. bridge (docker0) --------------------------------------------------
if ip link add m7br0 type bridge 2>>"$LOG"; then
    log "PASS bridge created"
    ip link del m7br0 2>/dev/null
else
    log "FAIL bridge create failed"
    degraded=$((degraded+1))
fi

# --- 10. NAT for docker0 -> wan egress ------------------------------------
if command -v iptables >/dev/null 2>&1; then
    log "iptables: $(iptables --version 2>&1 | head -1)"
    if iptables -t nat -A POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE 2>>"$LOG"; then
        log "PASS MASQUERADE rule accepted"
        iptables -t nat -D POSTROUTING -s 172.17.0.0/16 ! -o docker0 -j MASQUERADE 2>/dev/null
    else
        log "FAIL MASQUERADE rejected (docker0 egress would be dead)"
        degraded=$((degraded+1))
    fi
else
    log "WARN iptables binary absent (install via opkg; NAT then impossible)"
    degraded=$((degraded+1))
fi

# --- 11. resources dockerd will compete for -------------------------------
log "--- resources ---"
log "mem: $(free 2>/dev/null | tr '\n' '|')"
log "df : $(df -h / /tmp 2>/dev/null | tr '\n' '|')"
log "docker binary: $(command -v docker || echo ABSENT)"

# --- verdict --------------------------------------------------------------
log "=== RESULT: fatal=$fatal degraded=$degraded ==="
if [ "$fatal" -eq 0 ] && [ "$degraded" -eq 0 ]; then
    log "M7=YES -- kernel supports a full rootful Docker on 4.19"
elif [ "$fatal" -eq 0 ]; then
    log "M7=DEGRADED -- dockerd should start; see FAIL/WARN lines above"
else
    log "M7=NO -- hard blockers listed above; M8 falls back to procd+Hermes"
fi
log "full log: $LOG"
