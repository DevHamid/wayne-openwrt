#!/bin/sh
# Stage the verified compatibility patch in the SDK's source package patch directory.
set -eu
SDK=${1:?usage: patch-procd-sdk.sh SDK-DIR}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RECIPE="$SDK/package/feeds/base/procd/Makefile"
[ -f "$RECIPE" ] || { echo 'procd recipe missing from the SDK base feed' >&2; exit 1; }
grep -qx 'PKG_SOURCE_VERSION:=42d3937654508b04da64969f9d764ac2ec411904' "$RECIPE"
PATCHDIR="$(dirname "$RECIPE")/patches"
mkdir -p "$PATCHDIR"
# Bump package release so the corrected jailer cannot be confused with the
# stock binary already present in the base rootfs.
if grep -q '^PKG_RELEASE:=1$' "$RECIPE"; then
    sed -i 's/^PKG_RELEASE:=1$/PKG_RELEASE:=2/' "$RECIPE"
fi
grep -q '^PKG_RELEASE:=2$' "$RECIPE" || { echo 'unexpected procd package release' >&2; exit 1; }
cp "$ROOT/patches/procd-ujail-kernel-cap-limit.patch" "$PATCHDIR/950-ujail-kernel-cap-limit.patch"
# Verify recipe-visible patch path; SDK prepare will apply it to the pinned source.
test -s "$PATCHDIR/950-ujail-kernel-cap-limit.patch"
echo "staged $(basename "$PATCHDIR/950-ujail-kernel-cap-limit.patch") into $(dirname "$RECIPE")"
