#!/bin/sh
# Functional test for the bootstrap's staged-OTA block.
#
# It extracts the OTA section from overlay-system/init, runs it against fake
# directories (no block devices, no boot partition), and asserts:
#   1. a valid staged update replaces the tree and clears wayne-ota
#   2. a checksum mismatch aborts with the OLD tree still intact
#   3. an archive missing /sbin/init aborts with the OLD tree still intact
set -eu
cd "$(dirname "$0")/.."

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FAIL=0
ok()   { echo "ok   - $*"; }
bad()  { echo "FAIL - $*"; FAIL=1; }

# Extract the OTA block: from the section marker up to the /sbin/init check.
awk '/--- 3b\. Staged OTA install/{p=1} /^\[ -x "\$MNT\/sbin\/init" \]/{p=0} p' \
    overlay-system/init > "$WORK/ota-block.sh"
[ -s "$WORK/ota-block.sh" ] || { echo "FAIL - could not extract OTA block"; exit 1; }
# /dev/console is root-only on the build host; the block only logs to it.
sed -i "s#/dev/console#$WORK/console.log#g" "$WORK/ota-block.sh"

make_rootfs() {   # $1 = dir, $2 = marker text
    mkdir -p "$1/sbin" "$1/etc" "$1/lib" "$1/usr/bin"
    printf '#!/bin/sh\n' > "$1/sbin/init"; chmod +x "$1/sbin/init"
    printf '{"rootfs":"%s"}\n' "$2" > "$1/etc/wayne-build.json"
    : > "$1/lib/ld-musl-aarch64.so.1"
    printf '%s\n' "$2" > "$1/usr/bin/marker"
}

stage() {  # $1 = mnt dir, $2 = tarball, $3 = correct sha or "bad"
    mkdir -p "$1/wayne-ota"
    cp "$2" "$1/wayne-ota/rootfs.tar.gz"
    sha=$( [ "$3" = bad ] && echo deadbeef || sha256sum "$2" | cut -d' ' -f1 )
    printf 'version=test\nrootfs_sha256=%s\nboot_sha256=x\n' "$sha" \
        > "$1/wayne-ota/install.flag"
    : > "$1/wayne-ota/boot.prev"
}

run_block() { # $1 = mnt dir ; runs the block with MNT bound, no reboot
    MNT="$1" sh -c '
        set -eu
        bootstrap_fatal() { echo "FATAL: $*" >&2; exit 3; }
        . "$1"
    ' _ "$WORK/ota-block.sh" 2>"$WORK/err"
}

# --- case 1: valid update -------------------------------------------------
NEW="$WORK/new"; make_rootfs "$NEW" "new-version"
tar -czf "$WORK/new.tar.gz" -C "$NEW" .
M1="$WORK/mnt1"; make_rootfs "$M1" "old-version"
stage "$M1" "$WORK/new.tar.gz" good
if run_block "$M1"; then
    [ "$(cat "$M1/usr/bin/marker")" = "new-version" ] && ok "valid update installed" \
        || bad "valid update did not replace tree"
    [ ! -e "$M1/wayne-ota" ] && ok "staging dir removed" || bad "staging dir left behind"
else
    bad "valid update aborted: $(cat "$WORK/err")"
fi

# --- case 2: checksum mismatch --------------------------------------------
M2="$WORK/mnt2"; make_rootfs "$M2" "old-version"
stage "$M2" "$WORK/new.tar.gz" bad
if run_block "$M2"; then
    bad "corrupt checksum was accepted"
else
    grep -q 'checksum mismatch' "$WORK/err" && ok "checksum mismatch rejected" \
        || bad "wrong error for checksum case: $(cat "$WORK/err")"
    [ "$(cat "$M2/usr/bin/marker")" = "old-version" ] && ok "old tree intact after checksum failure" \
        || bad "old tree damaged after checksum failure"
fi

# --- case 3: archive without /sbin/init -----------------------------------
BAD="$WORK/bad"; mkdir -p "$BAD/etc"; echo '{}' > "$BAD/etc/wayne-build.json"
tar -czf "$WORK/bad.tar.gz" -C "$BAD" .
M3="$WORK/mnt3"; make_rootfs "$M3" "old-version"
stage "$M3" "$WORK/bad.tar.gz" good
if run_block "$M3"; then
    bad "archive without /sbin/init accepted"
else
    grep -q 'missing ./sbin/init' "$WORK/err" && ok "incomplete archive rejected" \
        || bad "wrong error for incomplete archive: $(cat "$WORK/err")"
    [ "$(cat "$M3/usr/bin/marker")" = "old-version" ] && ok "old tree intact after incomplete archive" \
        || bad "old tree damaged after incomplete archive"
fi

[ "$FAIL" = 0 ] && { echo "PASS: staged OTA block"; exit 0; }
echo "FAILURES PRESENT"; exit 1
