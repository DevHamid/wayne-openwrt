#!/bin/busybox-static sh
# Shared USB gadget builder (acm + rndis composite).
# Idempotent: safe to call from /init and procd service.
# Logs to /dev/kmsg AND /root/usb-gadget.log (persists on p64 rootfs).
LOG=/root/usb-gadget.log
mkdir -p /root 2>/dev/null
log() {
  echo "$(date 2>/dev/null) $*" >> "$LOG" 2>/dev/null || true
  echo "usb-gadget: $*" > /dev/kmsg 2>/dev/null || true
}

usb_gadget_up() {
    log "START"
    # 1) Ensure sysfs/configfs are up
    mountpoint -q /sys/kernel/config 2>/dev/null || mount -t configfs none /sys/kernel/config 2>/dev/null
    log "configfs mount=$(mountpoint -q /sys/kernel/config && echo ok || echo FAIL)"

    # 2) Load libcomposite (provides USB function drivers in configfs)
    modprobe libcomposite 2>/dev/null
    log "libcomposite=$(lsmod | grep -q libcomposite && echo loaded || echo no)"

    # 3) Wait for UDC to appear (cold boot can be slow)
    n=0; UDC=""
    while [ $n -lt 60 ] && [ -z "$UDC" ]; do
        UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
        [ -n "$UDC" ] && break
        sleep 1; n=$((n+1))
    done
    [ -n "$UDC" ] || { log "FAIL no UDC after 60s"; return 1; }
    log "UDC=$UDC"

    # 4) Already bound? (idempotent)
    G=/sys/kernel/config/usb_gadget/g1
    if [ -e "$G/UDC" ] && [ -s "$G/UDC" ]; then
        log "already bound to $(cat $G/UDC)"
        # wait for ttyGS0
        n=0
        while [ ! -e /dev/ttyGS0 ] && [ $n -lt 15 ]; do sleep 1; n=$((n+1)); done
        [ -e /dev/ttyGS0 ] && log "ttyGS0 ready" || log "ttyGS0 missing"
        return 0
    fi

    # 5) Build composite gadget
    mkdir -p "$G"
    echo 0x1d6b > "$G/idVendor"
    echo 0x0104 > "$G/idProduct"
    echo 0x0100 > "$G/bcdDevice"
    echo 0x0200 > "$G/bcdUSB"
    mkdir -p "$G/strings/0x409"
    echo "deadbeef001155" > "$G/strings/0x409/serialnumber"
    echo "Xiaomi" > "$G/strings/0x409/manufacturer"
    echo "Wayne M5" > "$G/strings/0x409/product"
    mkdir -p "$G/configs/c.1/strings/0x409"
    echo "Config 1: ACM+RNDIS" > "$G/configs/c.1/strings/0x409/configuration"
    echo 120 > "$G/configs/c.1/MaxPower"

    mkdir -p "$G/functions/acm.usb0"
    mkdir -p "$G/functions/rndis.usb0"
    # RNDIS MAC (host will see this)
    echo "02:1a:11:11:55:00" > "$G/functions/rndis.usb0/host_addr" 2>/dev/null
    echo "02:1a:11:11:55:01" > "$G/functions/rndis.usb0/dev_addr" 2>/dev/null

    ln -sf "$G/functions/acm.usb0" "$G/configs/c.1/"
    ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/"

    # 6) Bind
    if ! echo "$UDC" > "$G/UDC" 2>/dev/null; then
        log "FAIL bind $UDC (errno=$?); diagnostics:"
        log "  gadget dirs: $(ls /sys/kernel/config/usb_gadget/ 2>/dev/null | tr '\n' ' ')"
        log "  udc state: $(cat /sys/class/udc/$UDC/function 2>/dev/null || echo none) $(cat /sys/class/udc/$UDC/state 2>/dev/null)"
        log "  loaded usb mods: $(lsmod | grep -i 'usb\|rndis\|gadget' | tr '\n' ';')"
        return 1
    fi
    log "bound to $UDC"

    # 7) Wait for ttyGS0 (console) and usb0 (rndis)
    n=0
    while [ ! -e /dev/ttyGS0 ] && [ $n -lt 20 ]; do sleep 1; n=$((n+1)); done
    [ -e /dev/ttyGS0 ] && log "ttyGS0 ready" || log "ttyGS0 missing"
    n=0
    while [ ! -e /sys/class/net/usb0 ] && [ $n -lt 10 ]; do sleep 1; n=$((n+1)); done
    [ -e /sys/class/net/usb0 ] && log "usb0 ready" || log "usb0 missing"

    log "END ok"
    return 0
}

# Run only when executed, not sourced
case "$0" in
  *usb-gadget.sh) usb_gadget_up ;;
esac
