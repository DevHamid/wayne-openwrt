# Recorded evidence and limits

## Native findings (2026-11-20/21 UTC)

The work used the existing deployed vendor 4.19 kernel; no kernel change was needed for the QRTR publication correction. Before correction, a bounded live diagnostic retained five valid empty discovery replies while the daemon remained alive. A source-derived forwarding-gate fixture reproduced successful qrtr_publish return with a dropped announcement. Filling the advertised node/port made the service discoverable on Wayne. The original and latest pinned upstream transport source had identical non-whitespace content before the two added assignments.

A later separately reserved window verified all ten stock raw keys simultaneously on ten unique AP data ports. Twelve observation samples completed. No client firmware-file opens were recorded; WLFW service 69 and the Wi-Fi PHY were absent throughout those samples. No current-boot firmware-ready marker was retained. This does not establish absence of every possible malformed/unclassified client packet, the WLAN-selected key, or the reason firmware delivery never started.

Independent readback verified the temporary daemon, publications and staging removed, modem ONLINE/crash count 0, dump gates 0, and the original read-only rmtfs plus registry services unchanged. The modem remained active as it was before this trial; the server watchdog did not power it off. A mode-600 summary journal was retained in tmpfs by design. Background storage activity was not traced: read-only rmtfs does not mean no backing reads occurred.

The stock daemon's inspected ELF64/AArch64 SHA-256 is `c28276d14797688b818c99a8c6d1715fba7f771c0d15f736f2a7058163230c6c`. A read-only dump from the cached V12.0.2.0.PDCCNXM vendor filesystem matched it; the cached OTA vendor member CRC matched `a07c3d16`. This is member integrity, not full OTA-signature validation. Initialization, address encoding and the actual bind/advertisement calls were traced, including relocation-backed role-prefix pointers. The stock daemon was never executed on the phone; it can write RFS metadata and is not a safe drop-in replacement.

## Source and offline checks

`SOURCE-BINDINGS.json` records the unchanged production source/validator digests and the native helper digest. The public collector specimen intentionally omits the live guard and adds an unconditional refusal. Its test fixture uses only synthetic identities; do not promote those fixtures to a native authorization or configuration.

The original candidate passed 26 protocol/publication/namespace cases in each host, sanitizer and static ARM64/QEMU build; 14 lifecycle cases in host and target BusyBox/watchdog emulation; and 13 discovery-validator cases with host/target awk. This public package adds a direct unarmed-specimen refusal check and portable test runners. The exact packaged tree was rebuilt and rechecked: 26 protocol cases passed in each of the three variants; 15 lifecycle and 13 validator cases passed in both host and matched target environments, including refusal before touching pre-existing staging. No independent review, new CI/image build, release or persistent installation is claimed.

Upstream inputs:

- tqftpserv: `linux-msm/tqftpserv` at `eb4b9a04ff92d2753ededf32cc3b6ed287f6e29b`.
- QRTR transport: `linux-msm/qrtr` at `29e36ae164389580a0f8ea7a7fdb728140ae978d`, plus the address assignments visible in `source/qrtr-compat.c` versus `qrtr-upstream.c`.
- QRTR nameserver/header/logging reference: `linux-msm/qrtr` at `6d950d26e50d9ea3607510308fdd653bccc54400`; the vendored files matched its official archive, recorded in `vendor/QRTR-INPUTS.json`.
- Reviewed kernel source: `DevHamid/LKGeek_sdm660` at `2f7ff9f51ad6d37e067f32944467f0165eb2dfc9`.

## What remains open

This was a late-provider test on an already running modem. Early firmware-provider availability has not been tested, and the result does not justify another identical late retry, forced PDR, regulator/GPIO changes or broader firmware access. Wi-Fi readiness, cellular bearer/IP/NAT, client internet, userdata-backed persistence and the complete pocket-modem acceptance remain open. The recovery boot/SYSTEM split and selected kernel baseline are unchanged.
