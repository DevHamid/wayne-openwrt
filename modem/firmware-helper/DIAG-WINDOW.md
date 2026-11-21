# DIAG observation: topology verified, capture method unqualified

**Correction to commit `841bb608e5214493b63a729d465b56dce6a505c8`:** the
previous version mislabeled all DIAG rows as AP-local and described log-mask
changes as passive. No DIAG socket, mask change, log-clear command or raw
DIAG capture was executed by this investigation.

## Saved observations

- `/dev/diag` exists (`237:0`, `0600 root:root` in the saved readback).
- [SERVICE-TABLE-RAW.txt](SERVICE-TABLE-RAW.txt) contains **23 service-4097
  endpoint rows**, not 23 AP endpoints:
  - Node **0**: instance 1 / port 29 (MODEM:CMD), instance 3 / port 32
    (MODEM:DCI_CMD).
  - Node **1**: 21 rows, including MODEM:CNTL / DATA / DCI and
    WCNSS:CNTL / DATA / DCI (instances 128 / 130 / 132).
- The saved table does **not** contain node-0 instance 2 / port 26. That
  row in the previous note was invented and is withdrawn.

In inspected kernel commit `33647babe2a652c201fb9f87639363ef7cf28cf2`,
`drivers/char/diag/diagfwd_socket.c` defines the peripheral/channel instance
bases and `socket_open_server()` (483–536) creates and publishes AP server
sockets. `__socket_close_channel()` (538–568) explicitly retains servers.
Therefore a local WCNSS diagnostic endpoint is not proof that a remote WLAN
PD is alive or that a subscriber will receive historical startup logs.
This reference checkout does not establish the installed kernel's exact SHA.

## Unresolved before any live DIAG use

- Trace the exact kernel driver's supported userspace read/ioctl protocol,
  ownership and peer handling before attaching. Do not treat connecting a
  random QRTR socket to an AP control endpoint as a passive broadcast tap.
- Reading masks and changing masks are different operations. Enabling F3
  changes diagnostic state and is not a read-only probe. It needs a qualified
  protocol/cleanup plan and appropriate authorization.
- It is unproven that the missing WLAN startup reason is emitted as an
  accessible F3 message, currently enabled, buffered, or recoverable after
  startup. DIAG existence alone establishes none of those.
- Raw diagnostic frames can contain subscriber/device identifiers and payload
  data. Do not dump them into shared output. Any justified capture needs
  bounded duration, a narrow allowlist, private storage and sanitization.

The earlier assertion that no stock RFS userspace daemon exists was also
unsupported: the stock image listing included `rmt_storage`. Service 14 in
this OpenWrt setup is published by the reviewed userspace rmtfs source;
see [RFSA-DISABLED.md](RFSA-DISABLED.md) for the corrected memory/firmware
separation. Backing symlinks do not establish NV validity.

DIAG remains a possible diagnostic avenue, **not an implemented listener or
an observed explanation** of the WLAN startup failure.
