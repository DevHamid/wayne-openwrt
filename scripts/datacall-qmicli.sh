#!/bin/sh
# LTE data-call bring-up via qmicli over QRTR for the wayne (sdm660) built-in modem.
# Prereqs (in ROM): qmicli, qrtr-ns running, modem booted (S97modem-boot-trigger).
# Notes:
#  - The WDS client must be opened on the modem node (node 0). qmicli --device-open-qmi
#    handles the QRTR client allocation.
#  - If Start Network fails with error 70 (InvalidOperation), the IPA mux bind
#    (WDS 0x00A2) or DPM Open Port is still missing - check
#    `dmesg | grep -i ipa` for endpoint allocation logs.
set -eu
APN="${1:-internet}"
PROFILE="${2:-1}"

echo "== WDS Set Data Format (rmnet link layer)"
qmicli -d qrtr://0 --wds-set-data-format=link-layer-protocol=raw-ip || true

echo "== WDS Start Network (apn=$APN profile=$PROFILE)"
qmicli -d qrtr://0 --wds-start-network="apn=$APN,ip-family=ipv4,profile-index=$PROFILE"

echo "== WDS Get Current Settings"
qmicli -d qrtr://0 --wds-get-current-settings
