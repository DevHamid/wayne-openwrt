#!/bin/sh
# Emit the OTA manifest consumed by /usr/sbin/wayne-ota on the device.
#
# usage: make-manifest.sh <version> <tag> <boot.img> <rootfs.tar.gz>
# URLs are built from the release tag; hashes from the local files.
set -eu
[ $# -eq 4 ] || { echo "usage: $0 <version> <tag> <boot.img> <rootfs.tar.gz>" >&2; exit 2; }
VERSION=$1; TAG=$2; BOOT=$3; ROOT=$4
BASE="https://github.com/DevHamid/wayne-openwrt/releases/download/$TAG"
[ -f "$BOOT" ] || { echo "missing $BOOT" >&2; exit 1; }
[ -f "$ROOT" ] || { echo "missing $ROOT" >&2; exit 1; }
cat <<EOF
version=$VERSION
boot_url=$BASE/rom-boot.img
boot_sha256=$(sha256sum "$BOOT" | cut -d' ' -f1)
rootfs_url=$BASE/rootfs.tar.gz
rootfs_sha256=$(sha256sum "$ROOT" | cut -d' ' -f1)
EOF
