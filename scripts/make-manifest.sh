#!/bin/sh
# Emit the OTA manifest consumed by /usr/sbin/wayne-ota on the device.
#
# usage: make-manifest.sh <version> <tag> <boot.img> <rootfs.tar.gz>
# URLs are built from the release tag; hashes from the local files.
set -eu
[ $# -eq 4 ] || { echo "usage: $0 <version> <tag> <boot.img> <rootfs.tar.gz>" >&2; exit 2; }
VERSION=$1; TAG=$2; BOOT=$3; ROOT=$4
# An empty tag yields a manifest with empty URLs: offline-only (install from a
# manifest + payload pushed over USB with file:// or a bare path).
BASE=""
if [ -n "$TAG" ]; then
  BASE="https://github.com/DevHamid/wayne-openwrt/releases/download/$TAG"
fi
[ -f "$BOOT" ] || { echo "missing $BOOT" >&2; exit 1; }
[ -f "$ROOT" ] || { echo "missing $ROOT" >&2; exit 1; }
BOOT_URL=""; ROOT_URL=""
if [ -n "$BASE" ]; then
  BOOT_URL="$BASE/rom-boot.img"
  ROOT_URL="$BASE/rootfs.tar.gz"
fi
cat <<EOF
version=$VERSION
boot_url=$BOOT_URL
boot_sha256=$(sha256sum "$BOOT" | cut -d' ' -f1)
rootfs_url=$ROOT_URL
rootfs_sha256=$(sha256sum "$ROOT" | cut -d' ' -f1)
EOF
