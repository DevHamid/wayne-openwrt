# Filtered mapper trace: prepared and fixture-tested, not installed

## Why this is the next observation point

The modem loader's precheck queries **`kernel/elf_loader`** through locator
service 64 before its file checks; see
[ELOADER-PREDICATES.md](ELOADER-PREDICATES.md). Installed maps contain that
entry, but a no-socket map check and an AP-local `wlan/fw` query do not prove
the modem sent its own request or received a usable reply during startup.

The inspected mapper handled successful requests silently. The added opt-in
trace records the actual request handler and local reply-send outcome, so a
future startup capture can distinguish those stages without raw DIAG access.

## Implemented

`modem/registry/mapper/trace-queries.patch` applies **after** the existing
`vendor-pil-mapdir.patch` to the pinned pd-mapper source. It adds `-t`, allowed
only with an explicit trusted map directory. Nothing enables it by default,
and no existing startup script was changed.

One stderr line per handled locator request records:

- Sequence and monotonic seconds/nanoseconds.
- A fixed service class: `kernel_elf_loader`, `wlan_fw`, `tms_servreg`,
  `other`, or `malformed`.
- Numeric source QRTR node/port, response domain count, QMI result/error.
- Local send outcome: `ok`, `error`, or `encode_error`.

It never echoes arbitrary request names, domain strings, payloads, SIM or
subscriber fields. It emits at most **64 transaction records**, then one
suppression marker. A suppressed interval is an explicit evidence gap, not
an absence of further requests. A timestamp failure emits `clock=error`
instead of fabricating a timestamp.

`send=ok` means the local send API succeeded, **not that firmware consumed
or accepted the reply**. A remote-node request is stronger evidence than an
AP-local readiness request; do not mix them. A trace started after modem
startup cannot reconstruct the earlier transactions.

The malformed-request path also initializes the transaction variable before
decoding, avoiding use of an uninitialized value if decoding rejects the
header. The diagnostic retains the existing response behavior otherwise;
it is not a general upstream codec or input-hardening audit.

## Verification completed

- New trace/privacy/cap tests failed before the feature existed.
- **11 mapper test methods passed on the host**, including the earlier five
  map/wire cases, quiet-default behavior, fixed-label privacy, malformed input,
  send failure, and suppression after 64 records.
- The same **11 methods passed under ASan/UBSan**, with leak detection disabled.
- Static AArch64 mapper and fixture built successfully; **six no-network
  fixture scenarios executed on Wayne**: default quiet, loader request,
  private-name suppression, malformed header, failed send, and log limit.
- The fixture intercepts socket creation and fails if a real socket is opened;
  response sends/publication are intercepted too. No live mapper was started
  or replaced and **zero modem QMI requests** were sent by these tests.
- **7 fixed-query and 7 startup/lifecycle host tests** still pass.
- Applying both published patches to clean pinned source reproduced the
  compiled source bytes exactly; hashes are in `MAPPER-TRACE-EVIDENCE.json`.

Native closeout independently confirmed the original boot, modem ONLINE /
crash count 0, read-only UIO-backed rmtfs unchanged, automatic boot and dump
gates 0, installed mapper PID and binary hash unchanged, and fixture/staging
removed. This does not audit unrelated background storage activity.

## Alternatives inspected, not executed

Bounded inspection of saved `sys_m_diag_init` and its TMS callbacks found
control paths that dispatch system/power actions, not a demonstrated
read-only loader-progress operation. No guessed TMS command was sent. This
inspection is not an exhaustive proof that every DIAG command lacks a safe
query. No DIAG socket, mask change, modem-memory read, dump or electrical
control was used.

A saved embedded Hexagon ELF contains runtime-library exports, including
undefined RCINIT-table symbols. Those file bytes are **not** live root-PD
memory or proof of the current initialization group. They are not used as
a fabricated runtime observation.

## Deployment result

**Done (2026-11-21):** the trace was deployed for one guarded cold start and
captured a real modem-originated `kernel/elf_loader` query answered with one
domain, plus a subsequent modem TFTP **WRQ** that the read-only provider
denied. That window also exposed an AP kernel BUG in
`ipa_q6_clnt_svc_arrive`. See [RUNTIME-CAPTURE.md](RUNTIME-CAPTURE.md).

The observation must be active **before** the relevant startup. Replacing
an already-serving mapper now could interrupt the working locator, while
waiting on an unchanged steady-state boot cannot recover lost startup data.
A controlled startup trial therefore needs a recovery-ready test window,
a source-verified modem-release/cold-start mechanism, and a reversible rollout
for this userspace-only observer. It must not change the kernel or write boot,
vendor, userdata, recovery, EFS/NV or calibration. If a reboot is used to
release the retained modem reference, keep the current known-good boot backup
and physical OrangeFox access available; do not invent `boot=0`, force unload
or use SSR as a shutdown shortcut.

Precommitted interpretation for that future trial:

- **No modem-originated loader query:** inspect initialization/local SERVREG
  readiness or a path that failed before the locator, not map-file presence.
- **Query arrives, zero domains/error:** diagnose the actual mapper inputs or
  transaction instead of guessing a restart command.
- **Query arrives and one expected-domain response is sent:** the AP locator
  progressed; next correlate firmware-provider metadata/requests and WLFW.
  Local send success alone does not prove remote receipt or PD creation.
- **Trace capped, clock failed, publication failed or capture incomplete:**
  report the failed observation; do not infer absent startup.

The pocket-modem goal remains incomplete. This checkpoint fixes an observation
gap and provides a tested instrument, not a Wi-Fi or cellular-data fix.
