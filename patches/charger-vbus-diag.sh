#!/bin/sh
# M6 diagnostic: smb-lib.c compiles ALL of its error logging out -- every
# smblib_err()/smblib_dbg() sits inside `#ifdef DEBUG` and the Makefile never
# defines DEBUG. So when smblib_vbus_regulator_enable() fails (the reason
# v0.9.7 printed "unable to enable vbus_reg" with no cause) the charger says
# NOTHING. This adds unconditional pr_err() at the key branches of the enable
# path so one on-device run pinpoints it:
#
#   "find_votable(USB_ICL)=NULL"            -> votable missing (probe order)
#   "OTG boost softstart TIMEOUT"           -> boost never reached DONE
#   "OTG_ENG_OTG_CFG_REG write failed rc=N" -> SPMI register write failed
#   "EXIT FAILED rc=N"                      -> summary line, rc is the answer
set -e
F=drivers/power/supply/qcom/smb-lib.c
grep -q 'M6 diag' "$F" && { echo "patch already applied"; exit 0; }
python3 - "$F" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read()

# 1) OTG workaround timeout (all otg_current steps exhausted)
old = "\tif (i == ARRAY_SIZE(otg_current)) {\n\t\trc = -EINVAL;\n\t\tgoto out;\n\t}\n"
new = ("\tif (i == ARRAY_SIZE(otg_current)) {\n\t\trc = -EINVAL;\n"
       "\t\t/* M6 diag: every OTG current step timed out; the boost never\n"
       "\t\t * signalled BOOST_SOFTSTART_DONE. smblib_err is compiled out. */\n"
       "\t\tpr_err(\"%s: M6 diag OTG boost softstart TIMEOUT (tried %zu currents) rc=%d\\n\",\n"
       "\t\t\t__func__, ARRAY_SIZE(otg_current), rc);\n"
       "\t\tgoto out;\n\t}\n")
assert old in s, "otg_wa tail not found"
s = s.replace(old, new, 1)

# 2) OTG_ENG_OTG_CFG_REG register write failure
old = ("\tif (rc < 0) {\n"
       "\t\tsmblib_err(chg, \"Couldn't set OTG_ENG_OTG_CFG_REG rc=%d\\n\",\n"
       "\t\t\trc);\n\t\treturn rc;\n\t}\n")
new = (old.rstrip("\n") +
       "\n\t\tpr_err(\"%s: M6 diag OTG_ENG_OTG_CFG_REG write failed rc=%d\\n\",\n"
       "\t\t\t__func__, rc);\n\t\treturn rc;\n\t}\n")
assert old in s, "OTG_ENG_OTG_CFG_REG block not found"
s = s.replace(old, new, 1)

# 3) regulator_enable wrapper: entry, votable-miss, and exit rc
old = """\tmutex_lock(&chg->otg_oc_lock);
\tif (chg->otg_en)
\t\tgoto unlock;

\tif (!chg->usb_icl_votable) {
\t\tchg->usb_icl_votable = find_votable("USB_ICL");

\t\tif (!chg->usb_icl_votable) {
\t\t\trc = -EINVAL;
\t\t\tgoto unlock;
\t\t}
\t}
\tvote(chg->usb_icl_votable, USBIN_USBIN_BOOST_VOTER, true, 0);

\trc = _smblib_vbus_regulator_enable(rdev);
\tif (rc >= 0)
\t\tchg->otg_en = true;
\telse
\t\tvote(chg->usb_icl_votable, USBIN_USBIN_BOOST_VOTER, false, 0);

unlock:
\tmutex_unlock(&chg->otg_oc_lock);
\treturn rc;
}
"""
new = """\tmutex_lock(&chg->otg_oc_lock);
\t/* M6 diag: smblib_err is compiled out, so log unconditionally. */
\tpr_err("%s: M6 diag ENTER otg_en=%d icl_votable=%p wa_flags=0x%x\\n",
\t\t__func__, chg->otg_en, chg->usb_icl_votable, chg->wa_flags);
\tif (chg->otg_en)
\t\tgoto unlock;

\tif (!chg->usb_icl_votable) {
\t\tchg->usb_icl_votable = find_votable("USB_ICL");

\t\tif (!chg->usb_icl_votable) {
\t\t\tpr_err("%s: M6 diag find_votable(USB_ICL)=NULL -> -EINVAL\\n",
\t\t\t\t__func__);
\t\t\trc = -EINVAL;
\t\t\tgoto unlock;
\t\t}
\t}
\tvote(chg->usb_icl_votable, USBIN_USBIN_BOOST_VOTER, true, 0);

\trc = _smblib_vbus_regulator_enable(rdev);
\tif (rc >= 0)
\t\tchg->otg_en = true;
\telse
\t\tvote(chg->usb_icl_votable, USBIN_USBIN_BOOST_VOTER, false, 0);

unlock:
\tif (rc < 0)
\t\tpr_err("%s: M6 diag EXIT FAILED rc=%d otg_en=%d\\n",
\t\t\t__func__, rc, chg->otg_en);
\tmutex_unlock(&chg->otg_oc_lock);
\treturn rc;
}
"""
assert old in s, "smblib_vbus_regulator_enable not found"
s = s.replace(old, new, 1)

open(p, "w").write(s)
print("smb-lib.c patched: unconditional vbus-enable diagnostics")
PYEOF
grep -n 'M6 diag' "$F"
