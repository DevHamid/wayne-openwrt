#!/bin/sh
# Stage the verified compatibility patch in the SDK's source package patch directory.
set -eu
SDK=${1:?usage: patch-procd-sdk.sh SDK-DIR}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RECIPE=$(find "$SDK/feeds" "$SDK/package" -path '*/system/procd/Makefile' -type f -print -quit 2>/dev/null || true)
[ -n "$RECIPE" ] || { echo 'procd package recipe not found in SDK feeds/package' >&2; exit 1; }
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
