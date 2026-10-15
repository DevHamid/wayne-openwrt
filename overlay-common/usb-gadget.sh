#!/bin/sh
# usb-gadget.sh -- bring up the wayne composite USB gadget (acm + rndis).
#
# WHY THIS FILE EXISTS (M5 finding, 2026-10-15):
#   CONFIG_USB_G_SERIAL was removed from the kernel fragment. The legacy
#   g_serial gadget used to grab the single UDC (a800000.dwc3) automatically at
#   boot, which made ANY configfs gadget fail with "Resource busy" -- and the
#   runtime workaround (unbind/rebind the dwc3 platform device) PANICS this
#   vendor kernel, taking the phone down. So there is now exactly ONE gadget,
#   built here from configfs, giving BOTH:
#     acm.usb0   -> /dev/ttyGS0   (serial console -> PC /dev/ttyACM0)
#     rndis.usb0 -> usb0          (USB ethernet  -> SSH)
#
# Sourced by the /init scripts (they call usb_gadget_up). Returns 0 if
# /dev/ttyGS0 appeared.

usb_gadget_up() {
    G=/sys/kernel/config/usb_gadget/g1
    mkdir -p /sys/kernel/config
    mount -t configfs none /sys/kernel/config 2>/dev/null
    [ -d /sys/kernel/config/usb_gadget ] || { echo "usb-gadget: no configfs"; return 1; }

    mkdir -p "$G"
    echo 0x1d6b > "$G/idVendor"  2>/dev/null
    echo 0x0104 > "$G/idProduct" 2>/dev/null
    mkdir -p "$G/strings/0x409"
    echo wayne       > "$G/strings/0x409/serialnumber"
    echo DevHamid    > "$G/strings/0x409/manufacturer"
    echo WayneOpenWrt > "$G/strings/0x409/product"
    mkdir -p "$G/configs/c.1/strings/0x409"
    echo acmrndis > "$G/configs/c.1/strings/0x409/configuration"
    mkdir -p "$G/functions/acm.usb0" "$G/functions/rndis.usb0"
    ln -sf "$G/functions/acm.usb0"   "$G/configs/c.1/"
    ln -sf "$G/functions/rndis.usb0" "$G/configs/c.1/"

    # Already bound (e.g. /init built it, procd re-runs the service)? Just wait.
    if [ -s "$G/UDC" ]; then
        n=0
        while [ ! -e /dev/ttyGS0 ] && [ $n -lt 15 ]; do sleep 1; n=$((n+1)); done
        [ -e /dev/ttyGS0 ]
        return $?
    fi

    UDC=$(ls /sys/class/udc/ 2>/dev/null | head -1)
    [ -n "$UDC" ] || { echo "usb-gadget: no UDC"; return 1; }
    echo "$UDC" > "$G/UDC" 2>/dev/null || { echo "usb-gadget: bind $UDC failed"; return 1; }

    n=0
    while [ ! -e /dev/ttyGS0 ] && [ $n -lt 15 ]; do sleep 1; n=$((n+1)); done
    [ -e /dev/ttyGS0 ]
}
