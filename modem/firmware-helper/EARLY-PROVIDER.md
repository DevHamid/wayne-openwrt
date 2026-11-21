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

Early provider availability is **not** the blocker. With the provider publishing
before the modem existed, the outcome is identical to every late-provider run:
no firmware request, no WLFW, no PHY.

Two ordering facts were measured rather than assumed:

1. `SUBSYS_OFFLINING` is the zero value of the vendor `subsys_state` enum and
   nothing sets `OFFLINE` at probe — it is only written on crash/shutdown. A
   fresh boot that never powered the modem therefore reads `OFFLINING`, not
   `OFFLINE`. Read as "never booted in this boot", not "stuck mid-shutdown".
2. The AP notifier to `wlan_pd` (180) does establish, but that is not the same
   gate as the WLFW server appearing.

## Next lever

ICNSS only acts in `icnss_driver_event_server_arrive`, which is driven by the
WLFW (69) server appearing; that event carries the whole MSA/firmware handshake.
`icnss_trigger_recovery()` is the exported path that issues
`service_notif_pd_restart()` for the first instance — i.e. an explicit PD-restart
request is what can start the modem-hosted WLAN PD. Without it the PD serves the
notification endpoint but never publishes WLFW, so no firmware is requested.

That request is a modem-state operation on a live subsystem and needs its own
bounded, separately authorised trial with the provider running first.
