# Read-only provider receive-path observation — 2026-11-21

## Purpose

Earlier windows counted only accepted firmware **file opens**, so "zero opens"
could not distinguish "the modem never asked" from "the listener was never
exercised". This window adds and validates a total-datagram counter and an
opcode classifier, then repeats the observation without any modem operation.

## Instrumentation change

`source/tqftpserv.c` now prints, per datagram received on any published
listener, `readonly_listener_rx bytes=<n> profile=<key>`, before control-packet
and opcode dispatch; and `readonly_rx=<rrq|wrq|error|other> profile=<key>` for
non-control packets. Both lines are emitted only in the explicit
`-r <dir>` read-only diagnostic mode, so the normal daemon path is unchanged.

Two fixture cases cover it with wrapped syscalls and no network:

- `listen-rx-short` returns a one-byte datagram: the total counter must fire and
  the opcode classifier must not (`test_every_listener_datagram_is_logged_before_dispatch`).
- `listen-rx-rrq` returns a bare RRQ with no filename: the opcode must be
  recorded before the parse fails (`test_listener_records_rrq_before_filename_parse`).

Host and ASan/UBSan suites pass (27 cases each); the static ARM64 daemon and
fixture build clean with warnings as errors.

## Device window

One bounded window on the existing ROM and kernel. No reboot, modem
acquisition, restart request, flash, persistent install, SIM/provisioning
operation or dump-gate change. Provider, firmware copy and journal lived in
owned tmpfs; the window carried an operation budget with one provider start,
75 s provider lifetime and 100 s outer timeout.

- Provider validation `readonly_validation=pass`; all ten service-4096 raw keys
  published on ten distinct local ports, no missing or duplicate key or port.
- Twelve five-second samples: **no WLFW service 69 row, no PHY**.
- Receive path: **104 datagrams received and classified, zero carrying a TFTP
  opcode** (0 RRQ, 0 WRQ, 0 ERROR, 0 other), **zero firmware file opens**.
  The counted datagrams are control traffic on `QRTR_PORT_CTRL`; they prove the
  listener loop ran, and are not firmware requests.
- Independent closeout: same boot, modem ONLINE, crash count 0, original
  read-only `rmtfs` retained, `allow_boot=0`, both dump gates 0, provider
  process gone, service 4096 absent, staging removed. The modem stays ONLINE;
  the observation did not power it off.

Separately verified offline-to-device: **all 30 deployed modem/WLAN firmware
files** (`mba.mbn`, `modem.mdt`, `modem.b00`-`b28`, `WLANMDSP.MBN`) hash-match
the saved source set, so the "requested image is absent or corrupt on the AP"
explanation is not supported for those files.

## What this establishes

- The provider was reachable, published, and its receive path executed during
  the window.
- No TFTP request of any opcode reached it. The modem-side loader therefore did
  not try to fetch `wlanmdsp.mbn` from this provider in this window.
- Combined with `msm/modem/wlan_pd` reporting **UNINIT** and WLFW never
  appearing, the failure is upstream of firmware delivery: the WLAN protection
  domain is not running, so nothing requests its image.

## What this does not establish

- Why the PD is absent. This is not evidence about the AP-side trigger, the
  modem-side spawn policy, or PD accounting.
- Anything about a cold start: the modem was already ONLINE.
- Anything about cellular bearer, IP, NAT, client internet or persistence.

## Next

Trace what makes the modem root PD spawn `wlan_pd` and expose `wlan/fw`
(servreg `elf_loader`/`eloader` path in `MODEM.B17`, and the AP-side client that
would request it), rather than repeating restart requests or provider trials.
Machine-readable: `RX-OBSERVATION-EVIDENCE.json`.
