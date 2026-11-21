# Read-only firmware-delivery diagnostic checkpoint

This is a source safety checkpoint, not a ROM integration or a working-Wi-Fi release. It does not change the selected kernel, rootfs assembler, installed services, modem-start policy or recovery layout.

## Included

- A vendor-PIL adapter around upstream tqftpserv, requiring an explicit trusted directory and allowing only the reviewed WLAN image names. Write requests, non-firmware paths, symlinks, special/empty files and excessive windows are refused. The eight-session limit is shared across all listeners.
- The two-line QRTR publisher address correction: fill NEW_SERVER node/port from the socket address. On the reviewed vendor kernel, a zero node can silently drop a late local announcement after remote node zero exists.
- Separate sockets for the stock daemon's raw service-4096 keys 1 through 10. These values appear in QRTR's version column; they are selectors, not ten TFTP packet protocols. One socket cannot preserve the whole set in the pinned port-keyed nameserver.
- Socket-intercepting protocol, publication and nameserver-storage fixtures; complete-set discovery validation; synthetic collector lifecycle fixtures.
- Exact BSD-licensed QRTR dependency inputs, checked against their pinned upstream archive, with a per-file digest manifest. Their LICENSE and the tqftpserv license are retained.

The stock reference is Wayne MIUI V12.0.2.0.PDCCNXM. Its default key 1 maps to msm/mpss and was already covered by the earlier single-key trial. Defaults do not establish the WLAN client's selected key or prove the cause of a missing PHY. See [EVIDENCE.md](EVIDENCE.md) for the actual result and limits.

## Offline checks

From this directory, on Linux with Python 3 and a C compiler:

```sh
python3 build_and_test.py
python3 check_collector.py
```

The first command builds only userspace helpers and runs host plus ASan/UBSan fixtures. Optional static ARM64/QEMU coverage:

```sh
python3 build_and_test.py --arm64-cc "$ARM64_CC" --qemu "$QEMU_AARCH64"
```

For artifact-matched target shell, awk and watchdog coverage:

```sh
python3 check_collector.py \
  --target-shell "$TARGET_TOOLS/busybox" \
  --target-applets "$TARGET_TOOLS" \
  --target-timeout "$TARGET_TIMEOUT_BUSYBOX"
```

The shell wrapper named `busybox` must accept an applet name and run the matching target binary (and loader/rootfs when required). The applet directory supplies the matching target awk and utilities. The watchdog wrapper accepts `timeout` as its first applet argument. No target files, toolchains or emulators are downloaded automatically. Omitting target options performs host checks only; it is not target coverage.

Protocol fixtures intercept networking. Lifecycle fixtures use synthetic state files and a fake daemon; they do not establish native protocol behavior. The actual pinned nameserver storage code is tested with networking forbidden. Only its unmodified reference code receives narrowly scoped legacy compiler-warning exceptions; the adapter retains warnings-as-errors and sanitizer coverage.

## Collector safety

`collector-specimen.sh` is deliberately unarmed: it exits 126 before any staging or hardware access, even when invoked through `sh`. The live boot/rmtfs guard, SSH bridge, credentials, activation budgets and device launchers are not published. Fixtures explicitly remove the refusal prefix and replace the omitted guard with synthetic checks after rewriting hardware paths. The lifecycle logic is preserved, but the public specimen is not the byte-identical live launcher and must not be treated as a native recipe.

Do not remove the refusal and run it on a phone. Any native trial needs a fresh reviewed baseline, owned tmpfs staging, an operation-specific budget, independent watchdogs, unchanged read-only backing/dump protections and independent closeout. No reboot, modem actuation, protected-storage change or electrical-control change is authorized by these files.


Generated binaries and logs stay under ignored `build/`. No firmware images,
private captures, subscriber/calibration data or live device configuration are
included. This checkpoint is not wired into CI or normal image assembly.

## Receive-path counters

In explicit `-r <dir>` read-only mode the daemon prints `readonly_listener_rx`
for every datagram accepted on a published listener and `readonly_rx` for the
opcode of each non-control packet, both before dispatch. This exists because an
"accepted firmware opens" count alone cannot distinguish "no client asked" from
"the listener never ran". Normal (non-`-r`) operation is unchanged and prints
neither line. Live result and limits: [RX-OBSERVATION.md](RX-OBSERVATION.md).

## Fixed root-domain state read

The same userspace diagnostic now has a separate `--query-root <node> <port>`
mode for **QUERY_STATE (`0x0021` on service 66)** and the fixed
`msm/modem/root_pd` name. It neither registers a listener nor restarts anything.
`--root-packet` and `--parse-root <hex>` exercise encoding/decoding without
network access. Live execution still requires fresh service/instance discovery,
an operation budget and independent closeout; do not guess a port.

The peer-validated native read returned root-domain **UP** while subsequent
WLFW discovery and `iw dev` remained empty. A first unpeered sample is graded
separately; both sends are counted. Implementation, negative tests, live scope
and limitations: [ROOT-STATE.md](ROOT-STATE.md).

## PDR listener/restart diagnostic

`pdr_restart.c` also has an explicitly invoked `--listen-restart` mode. Build
and test it with `python3 build_pdr.py --arm64-cc "$ARM64_CC"`. It is not called
by any startup service or ROM assembler. The offline C fixture intercepts
socket operations; running its success case does not restart real hardware.

The approved native trial registered successfully, received **UNINIT** for the
requested domain, then had its same-socket restart refused despite a live
provider. See [PDR-LISTENER.md](PDR-LISTENER.md) and its sanitized evidence JSON.
This falsifies the earlier registration-only explanation, not the overall
pocket-modem design. Do not use a recovery request as an assumed cold-start API.
