#!/bin/sh
# M6 root-cause fix: dwc3_otg_start_host() enables VBUS ONLY via
# devm_regulator_get_optional(dev, "vbus_dwc3").  The sdm660-common.dtsi
# ssusb@a800000 node has USB3_GDSC-supply + dpdm-supply but NO vbus_dwc3-supply,
# so in host mode smb2-vbus (5V OTG boost) is never enabled -> no downstream
# devices enumerate.  Android hides this: its userspace USB HAL enables
# smb2-vbus itself.  Fix: wire the regulator into the DT node.
set -e
F=arch/arm64/boot/dts/vendor/qcom/sdm660-common.dtsi
grep -q 'vbus_dwc3-supply' "$F" && { echo "patch already applied"; exit 0; }
python3 - "$F" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = "\t\tUSB3_GDSC-supply = <&gdsc_usb30>;\n\t\tdpdm-supply = <&qusb_phy0>;\n"
new = "\t\tUSB3_GDSC-supply = <&gdsc_usb30>;\n\t\tdpdm-supply = <&qusb_phy0>;\n\t\tvbus_dwc3-supply = <&smb2_vbus>; /* M6: raise 5V OTG boost in host mode */\n"
assert old in s, "anchor not found in sdm660-common.dtsi"
open(p, "w").write(s.replace(old, new, 1))
EOF
echo "OK: vbus_dwc3-supply added to ssusb@a800000"
grep -n 'vbus_dwc3-supply' "$F"
