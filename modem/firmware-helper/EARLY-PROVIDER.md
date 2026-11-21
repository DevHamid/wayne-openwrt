# Early-provider comparison — device result (2026-11-21)

One watched reboot and one modem cold start. No partition write, no persistent
service, no dump-gate change, no SIM/provisioning operation.

## Setup

- Rebooted the existing ROM; boot image prefix still matched the retained
  reference (`77e80a03…b0b6`), `allow_boot=0`.
- Staged the tested static provider in `/tmp` (tmpfs), with `wlanmdsp.mbn`
  copied from the packaged firmware. `tqftpserv-ro -n -r` returned
  `readonly_validation=pass` before any socket was opened.
- Started it under a bounded lifetime. Before the modem was booted,
  `qrtr-lookup 4096` already listed all ten stock keys (versions 1–10) on
  distinct ports 16385–16415, node 1.
- Then one `echo 1 > /sys/class/modem-boot/modem0/boot`.

## Result

- Modem came up clean: `Brought out of reset` at 458.99 s, ONLINE, crash
  count 0 through 18 samples over 102 s.
- `service-notifier: Connection established between QMI handle and 180 service`
  at 459.13 s — the AP notifier did attach to `wlan_pd` (instance 180) once the
  modem booted.
- **Zero** provider requests, **zero** accepted firmware opens, **zero** denied
  requests.
- WLFW service 69 never appeared; `/sys/class/ieee80211` stayed empty.
- Full modem service table after power-up contains 66@"Service registry
  notification service" at instance 180, node 0 — and no 69.

## What this settles

Publishing this tested provider before modem power-up did not fix the blocker.
The outcome matched the late-provider runs: no firmware request, no WLFW, no
PHY. This does not prove that all provider protocol or firmware prerequisites
match Android; only this publication-timing alternative was exercised.

Two ordering facts were measured rather than assumed:

1. `SUBSYS_OFFLINING` is the zero value of the vendor `subsys_state` enum and
   nothing sets `OFFLINE` at probe — it is only written on crash/shutdown. A
   fresh boot that never powered the modem therefore reads `OFFLINING`, not
   `OFFLINE`. Read as "never booted in this boot", not "stuck mid-shutdown".
2. The AP notifier to `wlan_pd` (180) does establish, but that is not the same
   gate as the WLFW server appearing.

## Next lever

ICNSS's server-arrival event is driven by WLFW (69) publication and carries
the MSA/firmware handshake. `icnss_trigger_recovery()` can issue
`service_notif_pd_restart()`, but that is a recovery path, **not demonstrated
as the cold-start mechanism for an uninitialized WLAN PD**. The earlier
claim that this request could start the missing PD was a hypothesis, not a
verified dependency. The follow-up [registered-listener trial](PDR-LISTENER.md)
registered successfully and still received a refused restart, with the
requested domain reporting UNINIT. Continue from Android startup/source
comparison rather than repeating this request.
