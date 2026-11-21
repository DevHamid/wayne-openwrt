# Root-domain QUERY_STATE: UP, with source-verified transport

## Observed result

A fixed read of notifier service **66**, message **`0x0021` (QUERY_STATE)**,
for `msm/modem/root_pd` returned QMI success and **UP (`0x1fffffff`)**.
The final window explicitly matched the sender's AF_QIPCRTR family, node 0,
port 1, as well as transaction 1, message ID, total length and response TLVs.

```
root_query_attempt=1
root_query_sent=1 bytes=27
root_query_peer=matched
root_query=verified state=UP qmi_result=0 qmi_error=0 state_raw=0x1fffffff
root_query_socket=closed
```

Discovery selected service 66 / version 1 / instance 180 from the running
nameserver. Those node/port values describe this window, not a permanent
endpoint assignment. `MODEMR.JSN` supplies the root-domain name and instance.

The pinned vendor `service-notifier-private.h` at inspected reference
`2f7ff9f51ad6d37e067f32944467f0165eb2dfc9` defines QUERY_STATE at lines 15–16,
its name-only request at 40–44 / 155–170, and result plus optional state TLVs
at 173–211. A subscription was unnecessary. This notifier operation is
separate from the **locator** service 64's GET_DOMAIN_LIST, despite both
using message number `0x0021`.

## Two windows, not one retroactively qualified trial

1. The first helper sent one QUERY_STATE and received a header/transaction-
   matched UP response, but used connected `recv()` without recording the
   sender. It passed 13 wrapped native scenarios before its query.
2. A subsequent source audit found that the inspected vendor QRTR receive
   implementation does not enforce a connected-peer receive filter. The
   first result is therefore **downgraded for missing explicit sender
   validation**, not presented as fully verified.
3. A new failing test supplied valid QMI data from wrong node/port/family and
   a short sockaddr. The old query code incorrectly accepted those fixtures.
   The query mode was changed to `recvfrom()` and explicit peer checks.
4. After rebuilding and passing 17 wrapped native scenarios, a separately
   one-shot second read returned the source-verified result above. Both
   earlier and later reservations remain recorded; neither was reset/replayed.

**Cumulative live requests: 2 attempts, 2 successful 27-byte sends.** Both were
root QUERY_STATE reads. There were **zero listener registrations, zero restart
requests and zero modem acquisitions** in these windows. Fixture calls were
socket-intercepted and are not counted as live queries.

The inspected reference `net/qrtr/qrtr.c` at
`33647babe2a652c201fb9f87639363ef7cf28cf2` queues by destination port in
`qrtr_local_enqueue()` and exposes sender metadata in `qrtr_recvmsg()`;
`qrtr_connect()` stores a peer but that path does not filter receives against
it. This checkout is a source reference, not the installed kernel's proven
exact revision. Explicit user-space sender validation avoids relying on that
kernel behavior either way.

## Diagnostic implementation and tests

`pdr_restart.c` now has a fixed **`--query-root`** path which:

- Encodes only the root-domain QUERY_STATE; it does not call the listener,
  provider-liveness or restart paths.
- Makes at most one send attempt, with no retry after interruption, short
  send, timeout, rejection or mismatch; receive timeout is two seconds.
- Matches peer, header and complete TLVs before reporting a state. It rejects
  duplicates, truncation, malformed lengths, unexpected TLVs and nonhex
  parser input. It reports absent and unknown states distinctly.
- Closes its socket on every normal exit and reports close failure explicitly.
- Prints only fixed labels, bounded result/error/state values and counts,
  not arbitrary reply payloads.

`--root-packet` and `--parse-root` are no-socket validation modes. The existing
restart CLI remains separate; this root-state trial does not newly qualify or
authorize those older actuation paths.

The new mode's missing-feature test failed before implementation. A malformed
hex case also failed before its input fix. Wrong-peer fixtures failed before
the transport fix. The corrected build passes:

- **30 host test methods** (original packet/parser and listener scenarios plus
  the new root suite).
- **18 ASan/UBSan test methods**, with leak detection enabled.
- **17 wrapped transport scenarios executed on Wayne before the final live
  query**, including wrong peer, malformed response, timeout and interrupted/
  short send; plus native no-socket packet and decoder checks.

The source was built as userspace only. No kernel was compiled locally or
changed. The live launcher and one-shot/boot pins remain private. Sanitized
counts, source/binary digests and both window grades are in
[ROOT-STATE-EVIDENCE.json](ROOT-STATE-EVIDENCE.json).

## Independent closeout and interpretation

Both windows independently verified the original boot, modem ONLINE / crash
count 0, original read-only UIO-backed rmtfs, automatic boot 0 and both dump
gates 0, no helper processes and temporary staging removed. One-shot reservation
markers remain in tmpfs to prevent replay. No persistent phone installation,
flash, reboot, radio-mode/provisioning change or direct protected-partition
content probe was performed; unrelated background storage activity was not
traced. A subsequent nameserver read still found no WLFW-69 row, and `iw dev`
was empty.

**Established:** root-domain state is queryable and was UP at the final
source-verified sample. Do not describe all SERVREG/domain state as UNINIT
based on the earlier WLAN-domain registration response.

**Not established:** the value of the loader-local state word at
`0xc506d680`, the live initialization-table/group selection, whether
`eloader_init` executed, its locator/file-check return code, or working WLAN.
A root-domain QMI response is not a direct read of that local variable, and
it does not turn the earlier WLAN-domain sample into a simultaneous reading.

Next evidence remains the loader's actual runtime progress/return path,
using a source-qualified narrow diagnostic or a working Android comparison.
Do not repeat root-state reads or rejected restart requests to substitute for
that missing evidence. Cellular bearer/IP/NAT/client internet and persistence
also remain open acceptance gates.
