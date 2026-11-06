# wayne modem bring-up

Mi 6X (wayne, sdm660) on OpenWrt/ImmortalWrt as a pocket modem. The three
files in this directory are the modem boot path, recreated 2026-11-05 after
the originals were lost with `/srv/ssd` (the old local server), then
cross-checked against the recovered originals. Everything below is verified
against `DevHamid/LKGeek_sdm660 @ fix-ksu-sugrant` (head adbaae8f6), which
is what `.github/workflows/build.yml` clones.

## Transport: QMI over QRTR. Not MBIM.

| Plane | What actually carries it | Kernel / DT |
|---|---|---|
| Control | QMI over **QRTR** (glink `IPCRTR` channel) | `CONFIG_QRTR=y`, `CONFIG_QRTR_SMD=y`, `qcom,modem_qrtr` node in `sdm660.dtsi` |
| Data | **rmnet**, hardware-offloaded to IPA | `CONFIG_RMNET=y`, `CONFIG_RMNET_IPA=y`, `qcom,rmnet-ipa` node |

MBIM is a USB framing protocol (CDC-MBIM). The wayne modem firmware does
not speak MBIM over QRTR, and there is no MBIM function driver in this
tree. MBIM would only appear if you tethered the *phone* to a PC as a USB
modem — and even then it is a userspace bridge over the same QMI WDS
calls, not a second modem protocol.

**Consequence for OpenWrt:** `uqmi` will *not* work here — it only talks to
`/dev/cdc-wdmX` (QMI-over-USB). You need `libqmi` built with QRTR transport
plus `qmi-proxy`, or postmarketOS-style `qrtr-ns` + a small `qmicli`
bring-up script that hands the resulting `rmnet_data0` to netifd.

## Files

| File | Role |
|---|---|
| `modem-boot.c` | kernel module; drives `subsystem_get("modem")`, exposes sysfs |
| `rmtfs` | procd init script; mounts firmware partition, wires `/lib/firmware`, creates the uio symlink, starts the rmtfs daemon |
| `README.md` | this doc |

## What is already in place (kernel side)

- `pil_modem: qcom,mss@4080000` — `compatible = "qcom,pil-q6v55-mss"`
  (matched at `pil-q6v5-mss.c:522`), `qcom,firmware-name = "modem"`,
  `qcom,sequential-fw-load`, `qcom,pil-self-auth`, `status = "ok"`, plus
  the `qcom,mba-mem@0` child (matched at `:508`).
- Reserved memory: `modem_fw_region` (~126 MB), `pil_mba_region` (2 MB).
- Defconfig: `MSM_PIL_MSS_QDSP6V5=y`, `MSM_PIL=y`, `MSM_SUBSYSTEM_RESTART=y`,
  `MSM_PIL_SSR_GENERIC=y`, `QCOM_SMEM=y`, `RPMSG_QCOM_SMD=y`,
  `RPMSG_QCOM_GLINK_SMEM=y`, `QCOM_GLINK=y`, `QRTR=y`, `QRTR_SMD=y`,
  `QCOM_QMI_HELPERS=y`, `RMNET=y`, `RMNET_IPA=y`, `UIO_MSM_SHAREDMEM=y`.
- No wayne overlay touches `pil_modem` — nothing disables it.
- The rmtfs sharedmem node binds **as-is** (see DT patch below).

**The firmware payload is gone.** It used to live at
`/srv/ssd/vendor-work/modem-firmware/` (325 files, 91.58 MB); that disk is
lost and the remounted `/srv/ssd` is empty. Re-extract from the phone's
modem partition (device-side: `dd` the partition, loop-mount the VFAT) and
push the files into this repo — git survives, costs zero local storage.

## How the modem actually boots on this branch

`pil-q6v5-mss.c`'s `pil_subsys_init()` registers subsys `"modem"` with
`.powerup = modem_powerup()`, and `modem_powerup()` ends in
`return pil_boot(&drv->q6->desc)`. So `subsystem_get("modem")` **is** the
whole MBA+modem boot. The entire PIL stack and `subsystem_restart` are
built-in (`=y`).

```
subsystem_get("modem")     subsystem_restart.c
  -> modem_powerup()       pil-q6v5-mss.c:146
  -> pil_boot()            pil-q6v5.c
     -> pbl_mba_boot()     pil-msa.c:656-670
        request_firmware("mba.mbn")   (or "mba.b00" for non-elf images)
     -> request_firmware("modem.mdt")  peripheral-loader.c:1252 ("%s.mdt")
     -> request_firmware("modem.bNN")  peripheral-loader.c:1024 ("%s.b%02d")
  -> wait_for_err_ready()  modem signals ready over smp2p
```

Two traps this settles:

1. `pil_mss_reset_load_mba()` is **not** the boot function. Its only call
   site is `pil-q6v5-mss.c:198`, inside `modem_ramdump()` — the ramdump
   path. The MBA load during boot happens in `pil-msa.c` via
   `pbl_mba_boot()`. The old design called `pil_mss_reset_load_mba()` from
   a module — unexported (insmod would fail with `Unknown symbol`) and
   semantically wrong. `modem-boot.c` no longer touches it.
2. `subsystem_restart("modem")` is **not** a cold-boot substitute:
   `__subsystem_restart_dev()` requires `SUBSYS_ONLINE` and WARNs
   otherwise. It is for SSR recovery only. Use the `boot` attribute for a
   cold boot.

## rmtfs daemon: flags, the uio symlink, and why not `-s`

`rmtfs` links `-lqrtr -ludev -lpthread` (raw `libqrtr` from
`linux-msm/qrtr`; the OpenWrt feed's `libqrtr-glib` is a different glib
wrapper and does not satisfy it). Its CLI (`rmtfs.c` `getopt(argc, argv,
"o:S:Prsv")`):

- `-r` — read-only EFS backing
- `-o DIR` — storage root (default `/boot`)
- `-P` — use raw EFS partitions by-name
- `-s` — sync to the remoteproc. **Do not use on wayne**: it calls
  `rproc_init()` and exits with "Failed to get rprocfd", because this kernel
  boots the modem through PIL/`subsystem_get("modem")`, not the remoteproc
  framework.
- `-v` — verbose

The daemon opens `/dev/qcom_rmtfs_uio1` **hardcoded** (`rmtfs_mem_open_uio()`)
and reads udev sysattrs `maps/map0/{addr,size}` off it. Our kernel's
`msm_sharedmem` driver creates a standard uio device (`/dev/uioN`, name
`rmtfs`). So the init script creates the symlink
`/dev/qcom_rmtfs_uio1` → `/dev/uioN` before starting the daemon. The
daemon is invoked with `-r -o /var/lib/rmtfs` and no device argument.

## Userspace stack (built from the feed / recipes)

On the OpenWrt rootfs you need:

- `rmtfs` — built from `openwrt-packages/rmtfs` (depends on raw `libqrtr` +
  `libudev-zero`)
- `libqmi` + `qmi-utils` — from the stock feed (`qmicli`, `qmi-network`); QRTR
  is baked in (`Depends: libqrtr-glib`)
- `libqrtr-glib`, `libmbim`, `glib2` — feed deps of libqmi
- `libudev-zero` — drop-in libudev for rmtfs

See `openwrt-packages/README.md` for the full build/install path.

## DT patch: not needed on `fix-ksu-sugrant`

An earlier round of bring-up notes (and the supplied
`sdm660-rmtfs-fix.patch`, which moves `reg` to `<0x0 0x88f00000>`) assumed
`drivers/uio/msm_sharedmem/msm_sharedmem.c:153` rejects a zero base with
`-EINVAL`. **The current driver does not.** On `fix-ksu-sugrant` @
adbaae8f6 the same line takes the dynamic-allocation path
(`is_addr_dynamic = true` → `dma_alloc_coherent`, SZ_4K guards), and the
rejection text ("Shared memory base is zero") does not exist anywhere in
the file. So `reg = <0x0 0x200000>` binds fine, `/dev/uio*` appears, and
no DTS change is required.

**Fallback only:** if `/dev/uio*` never shows up at runtime (the
`dma_alloc_coherent` failing is the one plausible cause), apply
`sdm660-rmtfs-fix.patch` then — it moves the region into the verified free
gap `0x88f00000..0x8ac00000`, 2 MB-aligned so the guard pages fit.

## Boot order (never swap 3 and 4)

1. Kernel up; `/dev/uio*` present
2. `rmtfs` init script (`START=95`) mounts the firmware partition
   read-only, wires `/lib/firmware`, creates
   `/dev/qcom_rmtfs_uio1` → `/dev/uioN`
3. `rmtfs` daemon (`-r -o /var/lib/rmtfs`) answering remote-FS requests
4. Modem boot: `echo 1 > /sys/class/modem-boot/modem0/boot` (rc.local or
   init.d at `START=97+`)

Boot the modem before rmtfs answers and you get the MBA hand-off followed
by a watchdog bite. That looks like a firmware fault and isn't one.

## Firmware file wiring

The kernel loader requests **lowercase** `mba.mbn`, `modem.mdt` and
`modem.bNN` through the firmware loader, resolved under `/lib/firmware/`.
Android ships `MBA.MBN` / `MODEM.MDT` / `MODEM.B*` uppercase on the
partition. The `rmtfs` script bridges the case gap with symlinks
(`/lib/firmware/modem.mdt` → `/mnt/modem/MODEM.MDT`, same for `mba.mbn`
and every `modem.bNN`). Nothing else to do — `mba.mbn` is wired too,
because `pil-msa.c` requests it under a fixed name.

**Alternative:** before the first boot,
`echo MODEM > /sys/class/modem-boot/modem0/fwname` (basename only, no
extension — PIL appends `.mdt` / `.bNN` itself). Fails with `EBUSY` after
the modem is already up, because `modem_powerup()` copies the name into
the PIL descriptor at powerup time. Note this does not affect `mba.mbn`,
which is always requested under that fixed name.

## sysfs interface

```
/sys/class/modem-boot/modem0/state      ro   online | offline (last err %d)
/sys/class/modem-boot/modem0/boot       wo   write 1 -> subsystem_get (idempotent)
/sys/class/modem-boot/modem0/restart    wo   write 1 -> subsystem_restart (SSR only)
/sys/class/modem-boot/modem0/fwname     rw   firmware basename, first boot only
```

Typical sequence on device:

```sh
insmod modem-boot.ko
/etc/init.d/rmtfs start
cat /sys/class/modem-boot/modem0/state          # offline
echo 1 > /sys/class/modem-boot/modem0/boot
cat /sys/class/modem-boot/modem0/state          # online
```

A failed boot write never panics the box — the error code lands in
`state`. The module deliberately does not boot the modem at init, so
rmtfs gets its chance first.

## Diagnostics, in order

1. `ls /sys/class/uio/` and `cat /sys/class/uio/uio*/name` — is there a
   `rmtfs` device? If not, the sharedmem driver failed; see DT patch
   (fallback), then `dmesg | grep -i sharedmem`.
2. `cat /sys/class/modem-boot/modem0/state` — `-22` means the PIL
   rejected the firmware (check `/lib/firmware/modem.mdt` wiring),
   `-6`/`-12` means the MBA load path (check `mba.mbn`), a boot write that
   leaves no error but never reaches `online` means
   `wait_for_err_ready()` timed out — almost always rmtfs not answering.
3. `dmesg | grep -iE "sharedmem|uio|rmtfs|pil|modem|qrtr"`.

`pil-q6v5-mss: No pas_id found.` is `dev_info`, non-fatal — the driver
falls back to the non-PAS path. Don't chase it.

## Build

Cross-compile against the kernel tree the CI produces (`fix-ksu-sugrant`,
4.19). The module needs `CONFIG_QCOM_PIL`, the subsystem stack, and
`CONFIG_UIO_MSM_SHAREDMEM` — all `=y` in `wayne-oss-perf_defconfig`.
Out-of-tree against this tree: `#include <soc/qcom/subsystem_restart.h>`
resolves (in-tree drivers use the same form).

## On-device safety

- Only write `boot` (recovery) and read `system` for verification. Do not
  touch `vendor` or `userdata`; a bad write there needs a full re-flash.
- Have a known-good boot image + OrangeFox recovery installed before
  flashing anything. Restore path: flash the backup boot image from
  recovery, reboot, done.
- The firmware partition is mounted read-only; nothing on the phone is
  written by this flow.
