# DIAG as the read-only window into wlan_pd startup — 2026-11-21 UTC

No modem restart, no power change, no writes. All observations below are from
read-only commands on the running image.

## What exists

- `/dev/diag` — character device `237:0`, mode `0600 root:root`.
- QRTR service **4097 (DIAG)** is published with **23 transports**, all on the
  AP (node 1):

| instance | port | transport |
|---|---|---|
| 1 / 2 / 3 | 29 / 26 / 32 | MODEM:CMD / MODEM:DATA / MODEM:DCI_CMD |
| 0 | 16440 | MODEM:CNTL |
| 128 / 130 / 132 | 16436 / 16421 / 16422 | **WCNSS:CNTL / WCNSS:DATA / WCNSS:DCI** |
| 64 / 66 / 68 | 16438 / 16419 / 16420 | LPASS:CNTL / LPASS:DATA / LPASS:DCI |
| 256 / 258 / 260 | 16447 / 16427 / 16428 | CDSP:* |
| 320 / 322 / 324 | 16446 / 16425 / 16426 | WDSP:* |
| 192 / 194 / 196 | 16445 / 16423 / 16424 | SENSORS:* |
| 384 / 386 / 388 | 16416 / 16429 / 16430 | unnamed CNTL/DATA/DCI |

- Kernel diag driver is active; latest `dmesg` line:
  `diag: In diag_send_feature_mask_update, control channel is not open, p: 0`

## Why this is the next lever

The modem prints its own reason for not starting `wlan_pd` as F3/debug
messages. Those messages leave the subsystem through the DIAG stream, and the
**WCNSS:DATA / WCNSS:DCI** transports exist precisely to carry WLAN
subsystem debug. Every AP-side observation so far can only tell us *that*
WLFW is absent; DIAG can tell us *why* — which is the question everything else
has failed to answer.

This is the same class of operation as the earlier passive `rx-observe` work:
attach, listen, detach. Nothing is restarted, no state is changed.

## Sketch of a passive listener (not yet built)

1. `socket(AF_QIPCRTR, SOCK_DGRAM, 0)`, `bind()` an ephemeral port.
2. Attach to the WCNSS:CNTL transport (service 4097, instance 128, node 1,
   port 16436) reusing the socket/connect path already proven in
   `service-notifier.c` / `pdr_restart.c`.
3. Send the minimum harmless setup: read the enabled log mask first; enable
   F3 output only if it is off. No SSR commands, no event-log clears.
4. Dump every inbound frame (hex + decoded DIAG header) with timestamps.
5. Detach by closing the socket; verify the process is gone.

## Explicitly out of scope while doing this

Anything that can trigger a subsystem restart or reset, and anything that
writes to the modem: the DIAG SSR/restart command, "SSR ready", log clear,
and mask writes beyond enabling F3.

## Relationship to earlier dead ends

- EFS is authentic: `/tmp/wayne-rmtfs` backing files are symlinks to the real
  partitions `modemst1=p46`, `modemst2=p47`, `fsg=p45`, `fsc=p3`, served
  read-only. A missing/blank modem NV is ruled out, not assumed.
- No separate RFS userspace daemon exists in the stock vendor image (only
  `tftp_server`), so RFS is kernel-provided on both stock and this build.
- `subsystem_restart` parameters on the running image: `enable_debug=0`,
  `enable_ramdumps=0`, `enable_mini_ramdumps=0`, `max_restarts=0`,
  `disable_restart_work=0`; cmdline carries `service_locator.enable=1`.