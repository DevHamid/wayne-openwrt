# RAM-only TFTP server-check candidate (not live-deployed)

## Finding and evidence boundary

The latest read-only device check retained the same boot, modem ONLINE/crash 0,
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

## Required next experiment (not yet authorized or executed)

An early-provider comparison requires a clean boot and one newly authorized
modem acquisition. A late provider launch cannot reconstruct the completed
startup and has already produced uninformative negative windows in this project.

Keep the current boot image/SYSTEM and stable registry services. With confirmed
physical recovery access and a retained known-good boot backup, arrange one
watched reboot; verify the modem remains off, publish this candidate from tmpfs
before one modem start, and observe filename, completed check, authentic image
opens, WLFW and PHY. Do not restart the nameserver/mapper at observation closeout.
No general writes, provisioning, radio-mode operations or partition writes are
included. A reboot/start may still expose another firmware/kernel fault.

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
