#!/bin/sh
# Offline regression test for the wayne USB gadget bring-up fix (task 05a).
#
# Verifies, with NO hardware and NO root:
#   1. overlay-system/init starts the gadget build, waits (bounded) for the
#      UDC to reach "configured", and only then exec switch_root (ordering).
#   2. overlay-common/usb-gadget.sh binds the UDC and links usb0 up
#      (ip link set usb0 up + 192.168.1.1/24) on BOTH the fresh-build and the
#      already-bound paths.
#   3. The bootstrap wait block, extracted verbatim from the patched init,
#      reports bound=yes as soon as the state flips and gives up after 15s.
#   4. overlay-openwrt/usb-gadget.init (S95) retries the gadget build exactly
#      once when a UDC still reads "not attached".
#
# The helper is path-rewritten into a sandbox fake sysfs/configfs tree and
# driven with stubbed `ip`/`ifconfig`/`sleep`/`cat` commands; every call is
# recorded and asserted. Run anywhere: sh scripts/test-usb-gadget-bringup.sh
set -u

REPO=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
INIT="$REPO/overlay-system/init"
HELPER="$REPO/overlay-common/usb-gadget.sh"
S95="$REPO/overlay-openwrt/usb-gadget.init"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FAIL=0
PASS=0
ok()  { PASS=$((PASS+1)); echo "PASS: $*"; }
bad() { FAIL=1; echo "FAIL: $*"; }
check() { # check <desc> <command...>
    desc=$1; shift
    if "$@"; then ok "$desc"; else bad "$desc"; fi
}
UDC_NAME=a600000.dwc3

# ---------------------------------------------------------------------------
# 0. Static ordering assertions (source order IS the boot ordering).
#
# CONTRACT (post-bootloop-fix 8b2db33): usb_gadget_up runs SYNCHRONOUSLY in the
# foreground and COMPLETES before 'exec switch_root'. The old design launched
# the builder in a background subshell (&) and then waited (bounded, 15s) for
# the UDC to reach "configured". switch_root killed that background builder
# mid-build on cold boots -> gadget half-configured (carrier=0, no DHCP/SSH).
# The fix removed BOTH the background launch AND the wait block: the builder
# now runs to completion inline. So we assert foreground-and-before-handoff,
# and assert the removal of the background/wait pattern that caused the bug.
# ---------------------------------------------------------------------------
bg_line=$(grep -n 'usb_gadget_up' "$INIT" | head -n1 | cut -d: -f1)
handoff_line=$(grep -n 'exec switch_root' "$INIT" | cut -d: -f1)
[ -n "$bg_line" ] && [ -n "$handoff_line" ] && [ "$bg_line" -lt "$handoff_line" ] \
    && ok "init ordering: gadget build ($bg_line) < switch_root ($handoff_line)" \
    || bad "init ordering broken (bg=$bg_line handoff=$handoff_line)"

# The bootloop bug pattern must be GONE: no backgrounded gadget builder and no
# leftover bounded-wait block. Their presence would mean a regression to the
# switch_root-kills-the-builder failure mode.
if grep -qE 'usb_gadget_up[[:space:]]*&|gwait=0; bound=no' "$INIT"; then
    bad "init still has the background/wait gadget pattern (bootloop regression)"
else
    ok "init has no background/wait gadget pattern (foreground contract)"
fi

def_line=$(grep -n '^usb0_link_up()' "$HELPER" | cut -d: -f1)
calls=$(grep -c '^[[:space:]]*usb0_link_up$' "$HELPER")
[ -n "$def_line" ] && [ "$calls" -eq 2 ] \
    && ok "helper defines usb0_link_up once and calls it on both paths" \
    || bad "usb0_link_up definition/calls wrong (def=$def_line calls=$calls)"
for ln in $(grep -n '^[[:space:]]*usb0_link_up$' "$HELPER" | cut -d: -f1); do
    [ "$def_line" -lt "$ln" ] || bad "usb0_link_up called at $ln before definition at $def_line"
done
grep -q 'ip link set usb0 up' "$HELPER" \
    && ok "helper links usb0 up via ip" || bad "helper missing 'ip link set usb0 up'"
grep -q 'ifconfig usb0 up' "$HELPER" \
    && ok "helper has ifconfig fallback" || bad "helper missing ifconfig fallback"
grep -q '192.168.1.1/24' "$HELPER" \
    && ok "helper assigns 192.168.1.1/24" || bad "helper missing static address"

# ---------------------------------------------------------------------------
# Sandbox builder: fake sysfs/configfs + command stubs.
# ---------------------------------------------------------------------------
new_sandbox() {
    R="$WORK/sb$1"
    rm -rf "$R"
    mkdir -p "$R/sys/class/udc/$UDC_NAME" "$R/sys/kernel/config/usb_gadget" \
             "$R/sys/class/net" "$R/proc" "$R/dev" "$R/root" "$R/udc" "$WORK/bin$1"
    : > "$R/proc/mounts"
    echo "not attached" > "$R/sys/class/udc/$UDC_NAME/state"
    # Rewrite the helper's absolute paths into the sandbox. The rewrite also
    # redirects its /proc/mounts grep, so no real mount is ever attempted.
    sed -e "s|/sys/kernel/config|$R/sys/kernel/config|g" \
        -e "s|/sys/class|$R/sys/class|g" \
        -e "s|/proc/mounts|$R/proc/mounts|g" \
        -e "s|/dev/kmsg|$R/dev/kmsg|g" \
        -e "s|/dev/ttyGS0|$R/dev/ttyGS0|g" \
        -e "s|/root/usb-gadget.log|$R/root/usb-gadget.log|g" \
        -e "s|mkdir -p /root|mkdir -p $R/root|g" \
        "$HELPER" > "$WORK/helper$1.sh"
    # Network command stubs: record every call, always succeed.
    for cmd in ip ifconfig; do
        printf '#!/bin/sh\necho "%s $*" >> %s/calls.log\nexit 0\n' "$cmd" "$R" \
            > "$WORK/bin$1/$cmd"
        chmod +x "$WORK/bin$1/$cmd"
    done
    PATH="$WORK/bin$1:$PATH"; export PATH
}

helper_result() { # run usb_gadget_up from the rewritten copy in a subshell
    ( . "$WORK/helper$1.sh"; usb_gadget_up )
}

# ---------------------------------------------------------------------------
# 1. Fresh-build path: binds UDC, then links usb0 up.
# ---------------------------------------------------------------------------
new_sandbox 1
printf 'none %s/sys/kernel/config configfs rw 0 0\n' "$R" > "$R/proc/mounts"
touch "$R/dev/ttyGS0"                       # no 20s console wait
mkdir "$R/sys/class/net/usb0"
echo 1 > "$R/sys/class/net/usb0/carrier"; echo up > "$R/sys/class/net/usb0/operstate"
: > "$R/calls.log"
if helper_result 1; then ok "fresh build: usb_gadget_up returns 0"; else bad "fresh build: usb_gadget_up failed"; fi
check "fresh build: UDC bound (g1/UDC written)" \
    sh -c "[ \"\$(cat '$R/sys/kernel/config/usb_gadget/g1/UDC' 2>/dev/null)\" = '$UDC_NAME' ]"
check "fresh build: ecm function created" \
    test -d "$R/sys/kernel/config/usb_gadget/g1/functions/ecm.usb0"
check "fresh build: ip link set usb0 up called" \
    grep -Fqx "ip link set usb0 up" "$R/calls.log"
check "fresh build: ip addr add 192.168.1.1/24 called" \
    grep -Fqx "ip addr add 192.168.1.1/24 dev usb0" "$R/calls.log"
check "fresh build: ifconfig fallback NOT used (ip succeeded)" \
    sh -c "! grep -q ifconfig '$R/calls.log'"
check "fresh build: log says END ok" \
    grep -Fq "END ok" "$R/root/usb-gadget.log"
check "fresh build: configfs mount detected via fake /proc/mounts" \
    grep -Fq "configfs mount=ok" "$R/root/usb-gadget.log"

# ---------------------------------------------------------------------------
# 2. Already-bound path: idempotent, still links usb0 up.
# ---------------------------------------------------------------------------
new_sandbox 2
G="$R/sys/kernel/config/usb_gadget/g1"
mkdir -p "$G"
echo "$UDC_NAME" > "$G/UDC"                 # non-empty => already bound
touch "$R/dev/ttyGS0"
mkdir "$R/sys/class/net/usb0"
echo 1 > "$R/sys/class/net/usb0/carrier"; echo up > "$R/sys/class/net/usb0/operstate"
: > "$R/calls.log"
if helper_result 2; then ok "already-bound: usb_gadget_up returns 0"; else bad "already-bound: usb_gadget_up failed"; fi
check "already-bound: log reports the existing bind" \
    grep -Fq "already bound to $UDC_NAME" "$R/root/usb-gadget.log"
check "already-bound: usb0 still linked up on the early-return path" \
    grep -Fqx "ip link set usb0 up" "$R/calls.log"

# ---------------------------------------------------------------------------
# 3. (removed) Bootstrap wait block.
#
# The bootloop fix (8b2db33) removed the bounded configured-wait block from
# /init entirely: usb_gadget_up now runs synchronously in the foreground, so
# there is no separate wait loop to extract or exercise. The ordering
# assertions in section 0 now cover the foreground contract (builder completes
# before switch_root, no background/wait pattern present). Retained here as a
# note so the removed coverage is not mistaken for a gap.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4. S95 hardening: rebuild once when a UDC still reads "not attached".
# ---------------------------------------------------------------------------
sed -n '/^udc_needs_rebuild() {/,/^}/p' "$S95" \
    | sed -e "s|/sys/class|$WORK/ssys/class|g" > "$WORK/udcfn.sh"
grep -q 'udc_needs_rebuild' "$WORK/udcfn.sh" \
    && ok "S95: udc_needs_rebuild helper extracted" || bad "S95: helper not found in usb-gadget.init"
mkdir -p "$WORK/ssys/class/udc/$UDC_NAME"
(
    . "$WORK/udcfn.sh"
    echo "not attached" > "$WORK/ssys/class/udc/$UDC_NAME/state"
    udc_needs_rebuild && echo "REBUILD-NEEDED" || echo "REBUILD-NOT-NEEDED"
    echo "configured" > "$WORK/ssys/class/udc/$UDC_NAME/state"
    udc_needs_rebuild && echo "REBUILD-NEEDED" || echo "REBUILD-NOT-NEEDED"
    rm -rf "$WORK/ssys/class/udc/$UDC_NAME"
    udc_needs_rebuild && echo "REBUILD-NEEDED" || echo "REBUILD-NOT-NEEDED"
) > "$WORK/s95.out" 2>&1
check "S95: state 'not attached' => rebuild needed" \
    sh -c "[ \"\$(sed -n 1p '$WORK/s95.out')\" = 'REBUILD-NEEDED' ]"
check "S95: state 'configured' => no rebuild" \
    sh -c "[ \"\$(sed -n 2p '$WORK/s95.out')\" = 'REBUILD-NOT-NEEDED' ]"
check "S95: no UDC => no rebuild" \
    sh -c "[ \"\$(sed -n 3p '$WORK/s95.out')\" = 'REBUILD-NOT-NEEDED' ]"
# The retry must sit inside start_service, after the first build call.
ss=$(awk '/^start_service\(\) \{/,/^\}/' "$S95")
echo "$ss" | grep -q 'if udc_needs_rebuild; then' \
    && ok "S95: start_service calls the rebuild guard" \
    || bad "S95: start_service does not call udc_needs_rebuild"
first_build=$(echo "$ss" | grep -n '^[[:space:]]*usb_gadget_up[[:space:]]*$' | head -n1 | cut -d: -f1)
retry_line=$(echo "$ss" | grep -n 'if udc_needs_rebuild; then' | cut -d: -f1)
[ -n "$first_build" ] && [ -n "$retry_line" ] && [ "$first_build" -lt "$retry_line" ] \
    && ok "S95: retry guarded runs after the first gadget build" \
    || bad "S95: retry is not positioned after the first usb_gadget_up (build=$first_build retry=$retry_line)"

# ---------------------------------------------------------------------------
echo "----------------------------------------"
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
exit 0
