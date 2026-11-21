# RAM-only TFTP server-check (one live Wayne trial)

## Finding and evidence boundary

The pre-trial read-only device check retained the same boot, modem ONLINE/crash 0,
the original registry/rmtfs processes and disabled automatic-boot/dump gates.
The kernel connected to the WLAN notifier at instance 180; WLFW 69 and the PHY
remain absent. Repeating locator setup is not justified by this evidence.

The saved modem firmware contains `/readwrite/server_check.txt` at
`0xc22b34c0`, adjacent to `hello` at `0xc22b34dc`. The routine starting at
`0xc09ed6ec` passes the filename in the packet at `0xc09ed7d8` and handles its
transaction result. This is static evidence for a server-check path, not proof
that the previously observed 73-byte WRQ requested that exact filename.
Input hashes and addresses are in [RAMCHECK-EVIDENCE.json](RAMCHECK-EVIDENCE.json).

The upstream tqftpserv README documents a modem-boot WRQ to this exact path,
and maps normal readwrite requests to temporary storage.[1] That supports
investigating the check rather than blindly enabling general writes. It does
not establish this Wayne boot's runtime request sequence.

**Hypothesis:** our diagnostic's blanket WRQ denial can prevent a required
TFTP server-readiness check from completing, potentially blocking later WLAN
image requests. The old captured WRQ filename was not retained; live testing
is required before assigning causality. No working WLAN fix is claimed.

## Implemented candidate

The daemon has a new explicit `-c` opt-in alongside its mandatory `-r`
firmware directory. Without `-c`, the earlier read-only policy is unchanged.

- Only the exact NUL-terminated virtual path `/readwrite/server_check.txt` is
  handled by the exception. Other paths still reach the existing deny policy.
- Maximum 64 bytes retained **inside this process's static memory**. No file,
  directory, persistent backing, EFS/NV/calibration path or synthetic firmware
  is created by the exception. Readback returns the bytes actually received;
  it is not a fabricated successful upload or pre-populated `hello` response.
- One final DATA block, validated block/opcode/length, explicit family/node/port
  validation on each received datagram. WRQ commits only after a full final ACK
  send. RRQ supports readback, with or without option negotiation.
- Only modem node 0 may access the exception; this matches this device's
  observed node assignment and is not advertised as a universal QRTR node rule.
- Eight accepted-path attempts per daemon lifetime, a 512-byte request cap,
  no dynamic transfer allocation, and two-second send/receive socket timeouts.
  There is no automatic retry. Malformed/duplicate/unknown options are rejected.
- At most 64 bytes, zero/non-sparse offset and a single negotiated window.
  This is deliberately not a general TFTP writable filesystem or multiblock
  upload implementation. A future trial must also bound the daemon lifetime.
- Firmware serving still uses the existing authentic-image allowlist and opens
  firmware read-only; the existing generic WRQ/file-opening path stays blocked.

## Tests actually run

The new CLI opt-in, check-write, readback, duplicate-option rejection and
send-timeout requirements were observed failing before their respective fixes.

Final results:

- **38 test methods pass on the host.**
- **38 pass with ASan/UBSan**, leak checks enabled.
- **38 pass as static ARM64 under QEMU.**
- **19 socket-intercepted scenarios pass natively on Wayne**, including default
  denial, no-socket validation, memory write/readback, vendor-shaped options,
  path refusal, request cap, timeout, wrong peer family/node/port, short sockaddr,
  short/oversized DATA, wrong block/opcode and existing firmware RRQ behavior.
- A send-timeout requirement found a missing SO_SNDTIMEO; it was added and all
  three full suites plus the native cases were rerun on the final fixture.
- The native fixture wraps socket/send/receive APIs: it did not publish a live
  service or communicate with modem firmware. Its isolated input file is test
  data only, never installed under `/lib/firmware` or served to the modem.
- Independent closeout verified staging removed, same boot, modem ONLINE/crash 0,
  registry/rmtfs unchanged, gates 0, and no candidate service publication.

Userspace was compiled locally; **no kernel was built locally or changed**.
The source and static candidate binary digests are recorded in the evidence.
The shared build recipe remains `build_and_test.py`; pass a real ARM64 compiler
and QEMU together to execute the target suite rather than silently skipping it.

## Early-provider trial

The operator supplied a clean boot, and the provider published all ten keys.
Both collector invocations refused before the modem-start marker because the
provider had already been running too long. Independent readback confirmed the
same boot, modem still off, unchanged registry/read-only rmtfs, and neither a
temporary provider nor any TFTP publication. This was not a WLAN result.

The local [`early-window.sh`](early-window.sh) coordinator stages and verifies
inputs before starting the provider clock, rechecks scope after publication,
and schedules snapshots against absolute uptime rather than stacking lookup
latency onto each sleep. It retains the 360-second provider limit and refuses
to acquire unless at least 350 seconds remain. The offline fixture covers the
old refusal, one-shot acquisition and failure/cleanup paths. The coordinator
is not an armed launcher and is not included in the ROM.

After reauthentication, the approved same boot still showed the never-started
state (`OFFLINING` with control `offline`), crash count 0, no attempt marker,
locator present, and no TFTP, WLFW, or PHY. Preflight first refused staging
because `/proc/mounts` contains two `/tmp` entries. The retry validated the
visible filesystem with BusyBox `stat -f` (tmpfs magic `1021994`), checked all
six payload inputs on Wayne, ran the target watchdog against a harmless child,
and passed the no-socket provider check. Neither staging attempt started the
provider clock.

The live trial published all ten provider keys before one reserved modem start.
All 31 samples over 300 seconds showed modem ONLINE, crash count 0 and no PHY.
The provider accepted one five-byte `server_check.txt` write into process memory
and logged six RRQs, one successful `wlanmdsp.mbn` open, and two end-of-transfer
messages. The payload was not recorded; the number of firmware bytes served was
not independently measured. Three requests were denied by the read-only policy;
their exact paths are not known from the sanitized capture.

WLFW service 69 (version 1, instance 0, node 0) was present at the first positive
sample, 11 seconds after the recorded start reservation, and in every remaining
sample (30 of 31 total). ICNSS logged `QMI Server Connected: state: 0x980`.
No `WLAN FW is ready` message or Wi-Fi PHY was observed. On the running kernel
source (`98c685b86d5c7dc0a7983e7010870dd8ed31e2e8`), `icnss.c` registers
indications after the logged socket connect, then negotiates MSA and capabilities;
the connect message does not prove any of those transactions completed. The
first failed or missing ICNSS step remains unknown. This result supports the
readiness-check hypothesis without proving it is universally required or that
the denied paths caused the remaining failure.

Independent closeout verified the same boot, unchanged registry/read-only
rmtfs processes, disabled automatic boot and dumps, no provider publication,
removed tmpfs staging, and WLFW 69 still present. The modem remains ONLINE;
this observation did not request modem stop, reboot, flash, partition or SIM
changes. No AP or routed cellular data was tested.

Precommitted interpretation:

1. A request to another path remains denied; record only bounded diagnostic
   metadata and investigate it before broadening policy.
2. A check succeeds followed by an image RRQ: the readiness gate progressed;
   continue to WLFW/FW-ready/PHY instead of declaring Wi-Fi fixed.
3. A check succeeds but no image request: this hypothesis alone is insufficient.
4. No check request or incomplete capture: not evidence that the check is
   unnecessary; retain timing and previous-attempt limits.

## Sources

[1] https://raw.githubusercontent.com/linux-msm/tqftpserv/master/README.md — linux-msm tqftpserv protocol and modem boot example
