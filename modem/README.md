# wayne modem bring-up

Mi 6X (wayne, sdm660) on OpenWrt/ImmortalWrt as a pocket modem. These three
files are the modem boot path, recreated 2026-11-05 after the originals were
lost with `/srv/ssd` (the old local server). Everything below is verified
against `DevHamid/LKGeek_sdm660 @ fix-ksu-sugrant` (4.19), which is what
`.github/workflows/build.yml` now clones.

## Files

| File | Role |
|---|---|
| `modem-boot.c` | kernel module; drives `subsystem_get("modem")`, exposes sysfs |
| `rmtfs` | procd init script; mounts firmware partition, starts rmtfs daemon |
| `README.md` | this doc |

## How the modem actually boots on this branch

`pil-q6v5-mss.c`'s `pil_subsys_init()` registers subsys `"modem"` with
`.powerup = modem_powerup()`, and `modem_powerup()` ends in
`return pil_boot(&drv->q6->desc)`. So `subsystem_get("modem")` **is** the
whole MBA+modem boot. The entire PIL stack and `subsystem_restart` are
built-in (`=y`).

`pil-q6v5-mss.c` exports nothing. The old design called
`pil_mss_reset_load_mba()` from a module — that function is unexported
(insmod would fail with `Unknown symbol`) and is the ramdump path only
(line 198, inside `modem_ramdump()`). `modem-boot.c` no longer touches it.

The rmtfs sharedmem node needs **no DTS patch** on this branch: both live
branches' `msm_sharedmem.c` are byte-identical and take the dynamic-alloc
path (`reg = <0x0 0x200000>` → `dma_alloc_coherent`, SZ_4K guards). The
node binds as-is.

## Boot order (never swap 3 and 4)

1. Kernel up; `/dev/uio*` present
2. `rmtfs` init script mounts the firmware partition read-only at `/mnt/modem`
3. `rmtfs` daemon answering remote-FS requests
4. Modem boot: `echo 1 > /sys/class/modem-boot/modem0/boot`

Boot the modem before rmtfs answers and you get the MBA hand-off followed
by a watchdog bite. That looks like a firmware fault and isn't one.

## Firmware file wiring

`peripheral-loader.c` requests `"<fw>.mdt"` then `"<fw>.b%02d"` through the
firmware loader — lowercase, resolved under `/lib/firmware/`. Android ships
uppercase `MODEM.MDT` / `MODEM.bNN`. Two ways to bridge, pick one:

- **Default (symlinks):** the `rmtfs` script creates
  `/lib/firmware/modem.mdt` → `/mnt/modem/MODEM.MDT` and lowercase
  `modem.bNN` symlinks. Nothing else to do.
- **Set the basename instead:** before the first boot,
  `echo MODEM > /sys/class/modem-boot/modem0/fwname` (basename only, no
  extension — PIL appends `.mdt` / `.bNN` itself). Fails with `EBUSY`
  after the modem is already up, because `modem_powerup()` copies the
  name into the PIL descriptor at powerup time.

## sysfs interface

```
/sys/class/modem-boot/modem0/state      ro   online | offline (last err %d)
/sys/class/modem-boot/modem0/boot       wo   write 1 -> subsystem_get (idempotent)
/sys/class/modem-boot/modem0/restart    wo   write 1 -> subsystem_restart (SSR)
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

A failed boot write never panics the box — the error code lands in `state`.
The module deliberately does not boot the modem at init, so rmtfs gets its
chance first.

## Transport

QMI over QRTR (glink IPCRTR; `qcom,modem_qrtr` node in `sdm660.dtsi`); data
plane via rmnet + IPA. `uqmi` is unusable here — it needs `/dev/cdc-wdmX`.
Use libqmi built with QRTR transport plus `qmi-proxy`, or `qrtr-ns` +
`qmicli`.

## Diagnostics

```sh
dmesg | grep -iE 'sharedmem|uio|rmtfs|pil|modem|qrtr'
ls -l /dev/uio*                                  # rmtfs sharedmem node
cat /sys/class/uio/uio*/name                     # expect 'rmtfs'
cat /sys/class/modem-boot/modem0/state
/etc/init.d/rmtfs status
```

`pil-q6v5-mss: No pas_id found.` is `dev_info`, non-fatal — the driver
falls back to the non-PAS path. Don't chase it.

## Build

Cross-compile against the kernel tree the CI produces (fix-ksu-sugrant,
4.19). The module needs `CONFIG_QCOM_PIL`, the subsystem stack, and
`CONFIG_UIO_MSM_SHAREDMEM` — all `=y` in `wayne-oss-perf_defconfig`.

## On-device safety

- Only write `boot` (recovery) and read `system` for verification. Do not
  touch `vendor` or `userdata`; a bad write there needs a full re-flash.
- Have a known-good boot image + OrangeFox recovery installed before
  flashing anything. Restore path: flash the backup boot image from
  recovery, reboot, done.
