#!/bin/sh
# Apply the capability compatibility patch to the source tree selected by the SDK.
set -eu
SDK=${1:?usage: patch-procd-sdk.sh SDK-DIR}
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SRC=$(find "$SDK/feeds" "$SDK/package" -path '*/procd*/jail/capabilities.c' -type f -print -quit 2>/dev/null || true)
[ -n "$SRC" ] || { echo 'procd jail/capabilities.c not found in SDK' >&2; exit 1; }
PATCH="$ROOT/patches/procd-ujail-kernel-cap-limit.patch"
if grep -q 'kernel does not support capability' "$SRC"; then
    grep -q 'PR_CAPBSET_READ(%d) failed' "$SRC"
    grep -q 'kernel does not support ambient capability' "$SRC"
    echo "already patched: $SRC"
    exit 0
fi
REL=${SRC#"$SDK/"}
PATCHDIR="$SDK/package/system/procd/patches"
mkdir -p "$PATCHDIR"
# Keep the patch in the standard recipe patch directory so SDK prepare/compile
# applies it deterministically to the pinned source revision.
cp "$PATCH" "$PATCHDIR/950-ujail-runtime-cap-last.patch"
# Verify apply against the exact checked-out source without modifying tracked source.
patch --dry-run -p1 -d "$SDK/feeds/base/system/procd" < "$PATCHDIR/950-ujail-runtime-cap-last.patch"
echo "verified SDK patch for $REL"
