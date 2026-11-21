# Registered-listener PD-restart trial — 2026-11-21

## Scope and result

One approved live-modem window on the existing ROM and kernel. No reboot, new
modem acquisition, full-modem restart, flash, persistent phone installation,
SIM/provisioning operation or dump-gate change was performed by this trial.
Temporary binaries, firmware copies and logs were confined to owned tmpfs.

**Registration succeeded; restart was still refused. Wi-Fi is not fixed.**

1. Read-only firmware provider validation passed. Discovery verified all ten
   service-4096 raw keys on ten distinct local ports before the QMI sequence.
2. One connected AF_QIPCRTR socket sent message `0x0020`, transaction 1:
   TLV `0x01` = enable 1, TLV `0x02` = `msm/modem/wlan_pd`.
3. The modem returned `result=0, error=0` and current-state TLV `0x10` equal to
   `0x7fffffff` (**UNINIT**, not UP). Raw response:
   `02010020000e0002040000000000100400ffffff7f`.
4. Immediately before the restart, the helper verified the provider PID was
   alive and `/proc/<pid>/exe` matched the owned provider executable.
5. The same socket sent message `0x0024`, transaction 2, TLV `0x01` =
   `msm/modem/wlan_pd`. The modem returned **result 1, error 9**:
   `0202002400070002040001000900`. The socket was closed. No retry occurred.
6. Twelve subsequent five-second samples each had zero WLFW-69 rows and zero
   PHYs. The provider recorded zero client firmware opens, denied requests,
   denied writes, transfer completions or transport errors. Validation routines
   separately opened the staged firmware locally; their diagnostic output must
   not be counted as modem/client requests.
7. Independent SSH readback confirmed the same boot, modem ONLINE/crash count 0,
   original read-only rmtfs retained, `allow_boot=0`, both dump gates 0, no owned
   provider process, service 4096 absent and staging removed. The modem remains
   active; ending the observation did not power it off.

## What changed in the diagnostic

`pdr_restart.c --listen-restart` registers and restarts over one connected
socket, checks provider liveness before opening that socket and again before
the restart, and refuses to restart after failed registration, timeout,
unmatched transaction, malformed frame or changed provider identity. It sends
at most one listener request and one restart request; every normal error path
closes the socket. No long-lived userspace listener is retained; removal of the
firmware-side registration was not separately queried. A missing/unexpected response aborts; this diagnostic
does not implement a general notification/acknowledgement event loop.

Reproduce the offline userspace build from this directory:

```sh
python3 build_pdr.py --arm64-cc "$ARM64_CC"
python3 -m unittest test_probe -v
```

- Host: 12 original packet/parser tests and 10 new wrapped transport tests pass.
- ASan/UBSan: all 10 new wrapped transport tests pass.
- Static ARM64: the same 10 transport scenarios execute successfully **on Wayne**
  with socket/send/receive/provider-identity calls intercepted. These are
  no-network fixtures, not ten additional live modem operations.
- Existing collector lifecycle suite: 15 host tests pass. The adapted live
  launcher passed Wayne's shell syntax check and completed its real capture
  and independent cleanup readback; this does not constitute fresh target-side
  fault-injection coverage of every modified launcher path.
- Source/binary digests and sanitized observations: `PDR-LISTENER-EVIDENCE.json`.
  No kernel was built locally or changed for this trial. The live launcher,
  device baseline pins and private raw logs are not published.

## Interpretation and remaining work

This falsifies the claim that **missing listener registration alone** explains
the earlier error-9 refusal. Expired provider liveness was also corrected in
this trial. Successful notifier registration is not evidence that the requested
PD is running: firmware explicitly returned UNINIT for this name.

The vendor notifier header at inspected commit
`2f7ff9f51ad6d37e067f32944467f0165eb2dfc9` assigns UNINIT `0x7fffffff`, DOWN
`0x0fffffff`, UP `0x1fffffff`. `service_notif_pd_restart()` is a recovery request
for a registered service; its existence does **not** prove it is a cold-start
API or can create an uninitialized WLAN PD. No firmware implementation or
response in this investigation establishes why error 9 occurred.

The source check independently of the trial confirms that ICNSS passes the
locator's **domain name**, not an invented `domain/wlan/fw` concatenation:
`drivers/soc/qcom/icnss.c` lines 1956–1962 retain that name for notifier
registration, and lines 2604–2608 reuse it for restart. In
`drivers/soc/qcom/service-notifier.c`, lines 644–650 traverse the kernel's
**local** connected-client list; they do not establish a firmware rule requiring
all external requesters to register first. These references are at the same
inspected commit above. This does not identify the firmware-side error-9 cause.
Do not replace the tested domain with a guessed suffix.

The attempted independent helper review failed before executing tools because
its model provider was unavailable. The source checks above were performed by
the parent; this checkpoint is not independently reviewed or merge-approved.

Next work is source/reference comparison: trace where working Android starts
and registers the modem-hosted WLAN PD; verify the actual service identifier
and firmware startup prerequisites. Do not repeat the same request, substitute
another domain, or infer that a forced modem restart/power change is a fix.
Cellular bearer/IP/NAT, Wi-Fi-client internet and persistent configuration
remain unverified acceptance gates.
