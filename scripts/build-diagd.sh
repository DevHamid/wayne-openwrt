#!/bin/bash
# build-diagd.sh — cross-compile a static aarch64 `wayne-diagd` for the
# OpenWrt (musl) rootfs. Same toolchain recipe as build-rmtfs.sh.
#
# wayne-diagd holds /dev/diag open and drains it so the modem's diag task
# does not starve (the original ~90 s ERR_FATAL "USB bug"). Unlike a bare
# `cat`, it performs the DIAG ioctl msg-mask handshake, which the v2
# (LKGeek) kernel's diagchar driver requires before it will copy DIAG data
# to userspace (otherwise: "diag_copy_to_user_msg_mask ... err: -22").
#
# Output: $OUT_DIR/wayne-diagd   (static aarch64 binary, no runtime deps)
#
# Usage: build-diagd.sh [OUT_DIR]   (default: ./build/diagd-out)

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:-$REPO/build/diagd-out}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

DL(){ wget -q -O "$1" "$2" || curl -fsSL -o "$1" "$2"; }

echo "[*] fetching musl aarch64 cross toolchain"
TC="$WORK/toolchain"
mkdir -p "$TC"
DL "$WORK/tc.tar.xz" \
	https://github.com/userdocs/qbt-musl-cross-make/releases/download/2646/x86_64-aarch64-linux-musl.tar.xz
tar -C "$TC" -xJf "$WORK/tc.tar.xz"
CC="$TC/aarch64-linux-musl/bin/aarch64-linux-musl-gcc"
"$CC" --version | head -1

mkdir -p "$OUT_DIR"

echo "[*] building wayne-diagd (static)"
# -Wall so a handshake-struct typo fails the build rather than shipping a
# daemon that silently cannot talk to the diag driver.
"$CC" -O2 -static -Wall -o "$OUT_DIR/wayne-diagd" \
	"$REPO/tools/wayne-diagd.c" \
	-D_GNU_SOURCE

echo "[*] done"
ls -l "$OUT_DIR/wayne-diagd"
file "$OUT_DIR/wayne-diagd" 2>/dev/null || true