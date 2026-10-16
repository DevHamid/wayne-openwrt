#!/bin/sh
# M6 follow-up: dwc3_otg_start_host() must NOT abort host bring-up when the
# VBUS regulator refuses to enable.
#
# v0.9.7 shipped the DT fix (vbus_dwc3-supply = <&smb2_vbus>) -- correct wiring
# -- but on-device the charger's smblib_vbus_regulator_enable() FAILED, and this
# code path:
#
#     if (!IS_ERR_OR_NULL(mdwc->vbus_reg))
#         ret = regulator_enable(mdwc->vbus_reg);
#     if (ret) {
#         dev_err(mdwc->dev, "unable to enable vbus_reg\n");
#         return ret;                     <-- aborts BEFORE dwc3_host_init()
#     }
#     ...
#     ret = dwc3_host_init(dwc);          <-- xHCI created here, never reached
#
# made host mode regress: v0.9.6 (no supply, enable skipped, ret=0) brought the
# xHCI root hubs up; v0.9.7 brought up NOTHING (log: "unable to enable vbus_reg"
# then "unable to start host", usb_devs empty for the whole run).
#
# Fix: log the failure and CONTINUE. We still get the xHCI host (so an
# externally-powered device / the probe can proceed), and if the regulator ever
# does succeed we get 5V too. The disable path is made non-fatal for the same
# reason: a failed regulator_disable() was skipping ALL host teardown
# (usb_phy_notify_disconnect + dwc3_host_exit), wedging the next host start.
set -e
F=drivers/usb/dwc3/dwc3-msm.c
grep -q 'M6: vbus failure is non-fatal' "$F" && { echo "patch already applied"; exit 0; }
python3 - "$F" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()

# --- enable path ---
old_e = """\t\tif (!IS_ERR_OR_NULL(mdwc->vbus_reg))
\t\t\tret = regulator_enable(mdwc->vbus_reg);
\t\tif (ret) {
\t\t\tdev_err(mdwc->dev, "unable to enable vbus_reg\\n");
\t\t\tmdwc->hs_phy->flags &= ~PHY_HOST_MODE;
\t\t\tmdwc->ss_phy->flags &= ~PHY_HOST_MODE;
\t\t\tpm_runtime_put_sync(mdwc->dev);
\t\t\tdbg_event(0xFF, "vregerr psync",
\t\t\t\tatomic_read(&mdwc->dev->power.usage_count));
\t\t\treturn ret;
\t\t}
"""
new_e = """\t\tif (!IS_ERR_OR_NULL(mdwc->vbus_reg)) {
\t\t\tret = regulator_enable(mdwc->vbus_reg);
\t\t\tif (ret) {
\t\t\t\t/* M6: vbus failure is non-fatal -- keep host mode up so
\t\t\t\t * the xHCI controller still enumerates. v0.9.7 aborted
\t\t\t\t * here and lost the host entirely.
\t\t\t\t */
\t\t\t\tdev_err(mdwc->dev,
\t\t\t\t\t"unable to enable vbus_reg (rc=%d), continuing\\n",
\t\t\t\t\tret);
\t\t\t\tret = 0;
\t\t\t}
\t\t}
"""
assert old_e in s, "enable block not found"
s = s.replace(old_e, new_e, 1)

# --- disable path ---
old_d = """\t\tusb_unregister_atomic_notify(&mdwc->usbdev_nb);
\t\tif (!IS_ERR_OR_NULL(mdwc->vbus_reg))
\t\t\tret = regulator_disable(mdwc->vbus_reg);
\t\tif (ret) {
\t\t\tdev_err(mdwc->dev, "unable to disable vbus_reg\\n");
\t\t\treturn ret;
\t\t}
"""
new_d = """\t\tusb_unregister_atomic_notify(&mdwc->usbdev_nb);
\t\tif (!IS_ERR_OR_NULL(mdwc->vbus_reg)) {
\t\t\tret = regulator_disable(mdwc->vbus_reg);
\t\t\tif (ret) {
\t\t\t\t/* M6: non-fatal -- a failed disable used to skip the
\t\t\t\t * entire host teardown below and wedge the next
\t\t\t\t * host start.
\t\t\t\t */
\t\t\t\tdev_err(mdwc->dev,
\t\t\t\t\t"unable to disable vbus_reg (rc=%d), continuing\\n",
\t\t\t\t\tret);
\t\t\t\tret = 0;
\t\t\t}
\t\t}
"""
assert old_d in s, "disable block not found"
s = s.replace(old_d, new_d, 1)

open(p, "w").write(s)
print("dwc3-msm.c patched: vbus enable/disable failures are now non-fatal")
EOF
grep -n 'vbus failure is non-fatal' "$F"
