#!/bin/sh
# build-rmtfs.sh — cross-compile a static aarch64 `rmtfs` + `libqrtr`
#                 for the OpenWrt (musl) rootfs.
#
# The OpenWrt build in CI is a rootfs-overlay, not a buildroot, so there
# is no `make package/...`. We use a musl cross toolchain directly and
# link everything static; the rmtfs binary then drops onto ANY aarch64
# OpenWrt rootfs (musl or glibc) with zero runtime dependencies.
#
# Uses:
#   - libqrtr (raw) : linux-msm/qrtr @ 29e36ae
#   - libudev-zero   : illiliti/libudev-zero (repo head)
#   - rmtfs          : linux-msm/rmtfs @ b30a3eb
#
# Outputs (into $OUT_DIR):
#   rmtfs            static aarch64 binary
#   libqrtr.a        static lib (for reference / other consumers)
#   libudev.a        static lib (for reference)
#   libqrtr.h        header
#   libudev.h        header
#
# Usage: build-rmtfs.sh [OUT_DIR]   (default: ./modem/out)

set -euo pipefail

OUT_DIR="${1:-$(dirname "$0")/../modem/out}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

DL(){ wget -q -O "$1" "$2" || curl -fsSL -o "$1" "$2"; }

echo "[*] fetching musl aarch64 cross toolchain"
TC="$WORK/toolchain"
mkdir -p "$TC"
DL "$WORK/tc.tgz" https://musl.cc/aarch64-linux-musl-cross.tgz
tar -C "$TC" -xzf "$WORK/tc.tgz"
CC="$TC/aarch64-linux-musl-cross/bin/aarch64-linux-musl-gcc"
AR="$TC/aarch64-linux-musl-cross/bin/aarch64-linux-musl-ar"

mkdir -p "$OUT_DIR"

echo "[*] fetching + building raw libqrtr"
QR="$WORK/qrtr"
mkdir -p "$QR"
DL "$WORK/qrtr.tgz" \
	https://codeload.github.com/linux-msm/qrtr/tar.gz/29e36ae164389580a0f8ea7a7fdb728140ae978d
tar -C "$QR" -xzf "$WORK/qrtr.tgz"
QR_SRC="$QR/qrtr-29e36ae164389580a0f8ea7a7fdb728140ae978d"
(cd "$WORK" && "$CC" -O2 -fPIC -c \
	"$QR_SRC/lib/logging.c" "$QR_SRC/lib/qmi.c" "$QR_SRC/lib/qrtr.c" \
	-I"$QR_SRC/include")
"$AR" rcs "$OUT_DIR/libqrtr.a" "$WORK"/logging.o "$WORK"/qmi.o "$WORK"/qrtr.o
cp "$QR_SRC/include/libqrtr.h" "$OUT_DIR/"

echo "[*] fetching + building libudev-zero"
UV="$WORK/udev"
mkdir -p "$UV"
DL "$WORK/udev.tgz" \
	https://codeload.github.com/illiliti/libudev-zero/tar.gz/refs/heads/master
tar -C "$UV" -xzf "$WORK/udev.tgz"
UV_SRC="$(find "$UV" -mindepth 1 -maxdepth 1 -type d | head -1)"
(cd "$UV_SRC" && env CC="$CC" AR="$AR" \
	CFLAGS="-O2" make libudev.a >/dev/null)
cp "$UV_SRC/libudev.a" "$OUT_DIR/"
cp "$UV_SRC/udev.h" "$OUT_DIR/libudev.h"

echo "[*] fetching + building rmtfs (static)"
RM="$WORK/rmtfs"
mkdir -p "$RM"
DL "$WORK/rmtfs.tgz" \
	https://codeload.github.com/linux-msm/rmtfs/tar.gz/b30a3eb38f9af283f18dbd3c7755653efc52c094
tar -C "$RM" -xzf "$WORK/rmtfs.tgz"
RM_SRC="$RM/rmtfs-b30a3eb38f9af283f18dbd3c7755653efc52c094"
"$CC" -O2 -static -Wall -o "$OUT_DIR/rmtfs" \
	"$RM_SRC/qmi_rmtfs.c" "$RM_SRC/rmtfs.c" "$RM_SRC/rproc.c" \
	"$RM_SRC/sharedmem.c" "$RM_SRC/storage.c" "$RM_SRC/util.c" \
	-I"$OUT_DIR" -L"$OUT_DIR" \
	-lqrtr -ludev -lpthread \
	-D_GNU_SOURCE -Wno-unused-function

echo "[*] done"
ls -l "$OUT_DIR/rmtfs" "$OUT_DIR/libqrtr.a" "$OUT_DIR/libudev.a"
