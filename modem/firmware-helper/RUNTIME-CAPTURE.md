# Runtime cold-start capture — 2026-11-21

## What was done

One guarded cold start on a fresh boot (modem `OFFLINING`, never powered that
boot) with the tested instrument from [MAPPER-TRACE.md](MAPPER-TRACE.md)
already serving, plus the read-only service-4096 provider from
[RX-OBSERVATION.md](RX-OBSERVATION.md).

Userspace only: no kernel change, no partition write, no planned reboot, no
radio-mode or provisioning change. Guard: boot id match, `allow_boot=0`, both
dump gates 0, read-only UIO-backed `rmtfs`, modem not ONLINE. The traced
mapper was launched from tmpfs and its own map validation had passed;
`locator-query` verified the locator reply before the boot write.

## Measured result

Boot write at target uptime **833.63 s**. The modem came ONLINE with
**crash count 0** and stayed ONLINE for the full 90 s window. **No WLFW-69 row
and no PHY in any of the 18 samples**, and the provider recorded **zero
firmware opens**.

### The modem did perform the loader locator query

```
mapper_trace seq=5 mono_s=834 mono_ns=251328781 service=kernel_elf_loader \
  src_node=0 src_port=8 domains=1 result=0 error=0 send=ok
```

`src_node=0` is the modem (AP-local queries appear as `src_node=1`), and the
reply carried **one** domain — the AP answered the loader's precheck
successfully. Earlier traces also show three other modem-origin queries
returning zero domains.

This supersedes the earlier inference that nothing asked for the image: the
loader's locator step **did** run and **was** answered in this window. It does
not show what the modem did with the reply.

### The provider was asked to WRITE, and refused

```
readonly_listener_rx bytes=73 profile=1
readonly_rx=wrq profile=1
readonly_write=denied
```

The modem sent a **TFTP WRQ (write request)** to the firmware service. The
read-only diagnostic provider denies writes by design, so the request was
rejected. The 73-byte datagram is consistent with a filename plus mode, but
the filename was deliberately not exported by this instrument and is not
asserted here.

This is the first observed modem-originated transfer request in the whole
investigation, and it is a **write**, not a read. Whether that write is part
of the PD image path, a log/dump upload, or a count/state file is **not
established**.

## A new AP-side blocker: kernel BUG in the IPA driver

Roughly **176 s** after the boot write (uptime 1009.97 s) the AP kernel hit:

```
Kernel BUG at ipa_assert+0x14/0x20
Internal error: Oops - BUG: 0 [#1] PREEMPT SMP
Workqueue: clnt_req ipa_q6_clnt_svc_arrive
Call trace: ipa_assert / ipa_q6_clnt_svc_arrive+0x33c/0x460 /
            process_one_work / worker_thread / kthread
...
Rebooting in 3 seconds..
```

This is captured in `/sys/fs/pstore/dmesg-ramoops-0` and is the reason the
device rebooted. It is an **AP kernel assert on modem service arrival in the
IPA driver**, not a modem firmware fault, and it explains the repeated
unexplained reboots observed during this work. It fires after the modem has
progressed far enough to register an IPA client service.

Consequence: any window that lets the modem run past ~3 minutes currently
takes the whole AP down. That is a separate defect from the missing WLAN PD
and must be fixed before longer observation is meaningful.

## Data-loss hazard discovered (and why an earlier restore failed)

`/` (SYSTEM, `/dev/mmcblk0p61`) is mounted ext4 with **barriers disabled**.
After the unclean reboot, a freshly written 488 KB executable read back as
**0 bytes / SHA `e3b0c442…`** while metadata survived. That produced
`Exec format error` for `pd-mapper` and took the AP locator service down.

Mitigation used from then on: write to a temporary name, `sync`, atomic `mv`,
`sync`, then verify size and SHA-256 by readback. Do not treat a successful
`cp` as a durable install on this filesystem.

## State at the end of this checkpoint

- `pd-mapper` reinstalled from pinned source, readback-verified
  (`1a5935800a56aa5aca121186a205a4db7e1cd23dc52dcb25efd013658b953f1f`).
- Locator 64 published and `locator-query` verified; managed service healthy.
- Modem `OFFLINING` (not booted this boot), `allow_boot=0`, dump gates 0,
  read-only `rmtfs` intact. No further modem start was issued, so the IPA
  BUG is not currently being re-triggered.
- The installed mapper is now a **rebuild of pinned source + the vendor map
  patch**, not the byte-identical ROM original (hash differs). Functionality
  was verified on device; this is a deviation from the shipped image and is
  stated here rather than presented as a clean restore.

## Confirmed vs unresolved

**Confirmed:** the loader queries `kernel/elf_loader` and is answered; the
modem then issues a WRQ that our read-only provider denies; the AP kernel
BUGs in `ipa_q6_clnt_svc_arrive` about 3 minutes after a cold start and
reboots.

**Not established:** which file the WRQ targets, whether denying it blocks PD
startup, why `ipa_q6_clnt_svc_arrive` asserts, and whether the missing WLFW
is a cause or a symptom of the IPA fault.

## Next work

1. Diagnose `ipa_q6_clnt_svc_arrive`'s assert on this pinned tree
   (`ipa_assert` site, expected vs actual client state) — source-only first.
2. Extend the provider trace to export the WRQ **filename** under a strict
   allowlist and bounded length, so the write target is identified without
   dumping payloads.
3. Only then decide whether a narrowly-scoped write permission is justified.
   Do not blanket-enable writes: the current policy is what protects the
   firmware tree.

The pocket-modem goal remains incomplete.
