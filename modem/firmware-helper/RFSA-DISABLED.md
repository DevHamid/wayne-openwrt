# Retracted: missing QCOM_RMTFS_MEM is not an established WLAN cause

**Correction to commit `841bb608e5214493b63a729d465b56dce6a505c8`:** the
previous version incorrectly called `CONFIG_QCOM_RMTFS_MEM=n` the confirmed
root cause and recommended rebuilding/flashing. That recommendation is
withdrawn. No such kernel change or flash was performed during this audit.

## What the source actually implements

At inspected kernel commit `33647babe2a652c201fb9f87639363ef7cf28cf2`,
`drivers/soc/qcom/rmtfs_mem.c` implements a **shared-memory character device**:

- `qcom_rmtfs_mem_fops` (lines 135–142) supplies open/read/write/release/seek.
- Probe (153–236) maps reserved memory, creates `qcom_rmtfs_mem<client-id>`
  and optionally assigns memory permissions through SCM.
- Its match is `qcom,rmtfs-mem` (265–268). It contains no firmware-path
  translator or QRTR service publisher. Enabling it cannot by itself expose
  `/readonly/firmware/image/` or turn service 14 into a firmware-file server.

This source checkout is a reference, not proof of the installed kernel's exact
revision. The vendor `/proc/config.gz` is known to be a potentially foreign
embedded blob; it does not establish the installed resolved configuration.
Neither the stock Android symbol value nor a sole missing-driver cause was
established by the previous note.

The project's `scripts/build-rmtfs.sh` pins `linux-msm/rmtfs` to
`b30a3eb38f9af283f18dbd3c7755653efc52c094`. In that source:

- [`sharedmem.c` lines 268–313](https://github.com/linux-msm/rmtfs/blob/b30a3eb38f9af283f18dbd3c7755653efc52c094/sharedmem.c#L268-L313)
  explicitly falls back from `/dev/qcom_rmtfs_mem1` to UIO when the former
  returns ENOENT. Lines 124–190 open/map the UIO backend.
- [`rmtfs.c` lines 24, 425–447](https://github.com/linux-msm/rmtfs/blob/b30a3eb38f9af283f18dbd3c7755653efc52c094/rmtfs.c#L425-L447)
  define service 14 and publish it from userspace on port 14.
- That service exchanges storage sectors through shared memory. It is not
  the separate service-4096 TFTP firmware namespace.

A fresh read-only Wayne check found the existing `rmtfs` running with
`-r -P -o /tmp/wayne-rmtfs -v`, holding `/dev/uio0`, whose name is `rmtfs`
and map size is `0x200000`. Service 14 was discovered at node 1 / port 14.
These observations support an active UIO-backed daemon, not the claim that
service 14 is an inert kernel stub. They do not certify every storage RPC.

## Other withdrawn conclusions

- `modemuw.jsn` describes the **remote modem protection domain** and its
  `kernel/elf_loader` service. The word `kernel` there does not identify an
  AP Linux driver or a dependency on `QCOM_RMTFS_MEM`.
- `/readonly/firmware/image/%s` and the vendor-path fallback are confirmed
  modem strings. Strings alone do not select RFSA rather than QRTR TFTP;
  the reviewed `tqftpserv` translator supports those same paths.
- TFTP is **not established as irrelevant** to MPSS/WLAN, and the existence
  of a firmware file on the AP does not prove delivery. Conversely, the
  early-provider and receive-path trials did not observe a client request.
- `QCOM_MODEM_BOOT` was not shown to depend on `QCOM_RMTFS_MEM`; the inspected
  Kconfig declares PIL and subsystem-restart dependencies.
- There is no demonstrated rule that changing service 14 to port 0 fixes
  firmware access. Ports are addresses, not capability flags.
- Existing backing symlinks/hashes do not prove EFS/NV is valid or nonblank.
  No EFS/NV repair or additional protected-partition read is prescribed.

## Established failing gate and next investigation

The [registered-listener trial](PDR-LISTENER.md) already completed the proposed
same-socket sequence: listener `0x0020` succeeded with **UNINIT**; restart
`0x0024` returned **result 1 / error 9**, despite a verified live provider.
Repeating that request or rebuilding for an unproven memory-driver theory
would not distinguish a new hypothesis.

A fresh read-only baseline still has modem ONLINE / crash count 0, locator 64
and notifier 66 present, WLFW 69 absent, and no PHY. Automatic modem boot and
both dump gates remain disabled. The pocket-modem goal is **not complete**.

Continue tracing the modem-side loader's initialization and its prerequisites;
keep static reachability, actual execution, firmware transfer and Wi-Fi
readiness separate. See [ELOADER-INIT.md](ELOADER-INIT.md). This correction is
not a new ROM, verified WLAN fix, or instruction to flash.
