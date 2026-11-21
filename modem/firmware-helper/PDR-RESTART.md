# PD-restart request — device result (2026-11-21)

One authorized bounded test on a live modem. No partition write, no full modem
restart, no SIM/provisioning change, no dump-gate change.

## Tool

`pdr_restart.c` builds the same request the vendor kernel emits from
`service_notif_pd_restart()` via `icnss_trigger_recovery()`:

- QRTR datagram to QMI service `0x42` (service 66), instance 180, node 0, port 1
- message `0x0024` (`QMI_SERVREG_NOTIF_RESTART_PD_REQ_V01`)
- one TLV `0x01` carrying the PD path `msm/modem/wlan_pd` (the *domain* name from
  the locator map; `wlan/fw` is the request-side name and is not what this
  message takes)

The header is this vendor kernel's packed 7-byte `struct qmi_header`
(`type`, `txn:u16`, `msg_id:u16`, `len:u16`) — **not** the 6-byte layout used by
some other QMI stacks. 12 offline cases pass on host; the same source builds
static ARM64.

## What happened

1. First send: rejected locally at `connect()` with `EINVAL`. Cause was a real
   bug — `sq_family` declared as `char`, leaving the high byte as uninitialised
   padding that the kernel read as part of `__kernel_sa_family_t`. Nothing was
   transmitted.
2. Second send used that wrong struct but connected: the modem answered
   `result=1, error=2` (malformed message), because the 6-byte header was
   decoded as a different transaction/message id. No PD restart.
3. Third send with the corrected 7-byte header, 27 bytes, was accepted at the
   protocol level and answered:
   **`qmi_result=1 (FAILURE), qmi_error=9`**.

No WLFW service 69 appeared, no PHY appeared, and the modem stayed ONLINE with
crash count 0 throughout.

## Caveat that must not be hidden

The read-only provider had already hit its lifetime bound and was **not
running** during the final window, and it was not re-started before the request.
So this run cannot claim "PD restart succeeded but no firmware was requested" —
it can only claim the request was refused. Any firmware handshake would also
have had no server to answer it.

## What it establishes

- The userspace QRTR/QMI path to the modem's service-registry notifier works:
  the request is transmitted, parsed by firmware, and answered with a
  well-formed QMI response.
- The modem refuses this bare request. The kernel only issues it from a client
  that already registered a listener on that service/instance
  (`service_notif_pd_restart()` iterates its connected `qmi_client_list`), which
  a raw one-shot client does not satisfy.

## Follow-up

**Completed:** see [PDR-LISTENER.md](PDR-LISTENER.md). Registration succeeded,
the provider was alive immediately before the same-socket restart, and restart
still returned result 1/error 9. The earlier missing-registration explanation
was a hypothesis and has now been falsified. The listener reported UNINIT;
this recovery API is not established as a cold-start mechanism.
