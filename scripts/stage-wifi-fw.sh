#!/bin/sh
# scripts/stage-wifi-fw.sh -- stage WCN3990 (qcacld/icnss) wifi firmware into
# the 23.05 rootfs at the exact paths the driver probes.
#
# Driver expectations (vendor 4.19 qcacld-3.0):
#   * base BDF   -> /lib/firmware/wlan/qca_cld/bdwlan30.bin
#   * board BDF  -> /lib/firmware/wlan/qca_cld/bdwlan30.bXX (lowercase hex)
#   * fw blob    -> loaded by icnss/PIL via QMI from WLANMDSP.MBN
#   * mac blob   -> /lib/firmware/wlan/qca_cld/ (WLAN_MAC_FILE="wlan/qca_cld/")
#
# The repo's modem-firmware/ ships WLANMDSP.MBN + BDWLAN.* (uppercase).
# We copy the MBN and every BDF, and also plant lowercase bdwlan* symlinks so
# the driver's name probe succeeds regardless of the reported board ID.
#
# Usage: stage-wifi-fw.sh <path-to-modem-firmware-dir> <rootfs-dir>

set -e
SRC="${1:?src modem-firmware dir}"
ROOTFS="${2:?dest rootfs dir}"

FW="$ROOTFS/lib/firmware/wlan/qca_cld"
mkdir -p "$FW"

# --- 1. The WCN3990 firmware blob (loaded via icnss/PIL QMI). ---
if [ -f "$SRC/WLANMDSP.MBN" ]; then
    cp "$SRC/WLANMDSP.MBN" "$FW/wlanmdsp.mbn"
    echo "staged wlanmdsp.mbn ($(wc -c < "$FW/wlanmdsp.mbn") bytes)"
else
    echo "WARN: no WLANMDSP.MBN in $SRC"
fi

# --- 2. Every board data (cDF) variant we have. ---
count=0
for f in "$SRC"/BDWLAN.*; do
    [ -f "$f" ] || continue
    base=$(basename "$f")          # e.g. BDWLAN.B0A
    cp "$f" "$FW/$base"
    # driver wants lowercase bdwlan30.bXX; make a lowercase alias too
    lower=$(echo "$base" | tr 'A-Z' 'a-z')   # bdwlan.b0a
    # bdwlan.b0a -> keep name, also make bdwlan30.b0a alias (30-series if)
    ln -sf "$base" "$FW/$lower"
    ln -sf "$base" "$FW/bdwlan30.${lower#bdwlan.}"
    count=$((count+1))
done
echo "staged $count BDF variants"

# Do not synthesize a MAC/calibration file. A real device-provided value or
# the driver's native fallback is required; an empty file is not calibration.
if [ -f "$FW/wlan_mac.bin" ] && [ ! -s "$FW/wlan_mac.bin" ]; then
    rm "$FW/wlan_mac.bin"
fi
[ -s "$FW/wlanmdsp.mbn" ] || { echo 'FATAL: WLANMDSP missing'; exit 1; }
[ -s "$FW/bdwlan30.bin" ] || { echo 'FATAL: base BDF missing'; exit 1; }

echo "wifi fw staged at $FW:"
ls -la "$FW"
