# rmtfs + raw libqrtr for OpenWrt/ImmortalWrt (wayne sdm660)

This directory holds the OpenWrt build recipes for the two userspace pieces the
modem boot needs that the stock `openwrt/packages` feed does **not** ship in a
useful form:

| Piece | Why custom | What it is |
|---|---|---|
| `libqrtr` (raw) | The feed only has `libqrtr-glib` (meson, glib wrapper). `rmtfs` links `-lqrtr` and uses the raw `libqrtr.h` API (`qrtr_open`/`qmi_encode_message`, `linux-msm/qrtr`). This package builds that raw library (+ `qrtr-ns` binary, though it's not needed here). | `linux-msm/qrtr` @ `29e36ae` |
| `rmtfs` | Not in any OpenWrt feed. The modem's remote-FS service; without it the modem has no EFS backing and the boot sequence never completes. | `linux-msm/rmtfs` @ `b30a3eb` |

`libqmi` / `qmi-utils` / `libqrtr-glib` / `libmbim` / `glib2` ARE in the
stock feed — do not rebuild them, just install from the index.

## Why not "build with the SDK"

The `DevHamid/wayne-openwrt` CI does **not** run an OpenWrt buildroot. It:
1. downloads a prebuilt `immortalwrt-21.02.7-armvirt-64-default-rootfs.tar.gz`
2. applies overlay files into that rootfs
3. packs an initramfs cpio + a kernel into a boot.img

So there is no `make package/feeds/...`, no `feeds.conf`, no top-level
`Makefile`. Package *builds* happen outside CI (in the SDK or a buildroot);
what lands in the repo is the **prebuilt `.ipk` set** listed below, unpacked
into the rootfs during the overlay step.

If you do have a buildroot, the two Makefiles in this directory are drop-in
`package/feeds/wayne/` recipes. But for *this* repo the artifact is `.ipk`
files.

## Where the binaries come from

Feed base URL:
`https://downloads.immortalwrt.org/releases/21.02.7/packages/aarch64_cortex-a53/`

Prebuilt `.ipk` to fetch and unpack into the rootfs (target `aarch64_cortex-a53`):
- `libqrtr` — built from source (recipe below), or fetch a prebuilt `.ipk` if you publish one
- `qmi-utils_1.30.8-1_aarch64_cortex-a53.ipk`
- `libqmi_1.30.8-1_aarch64_cortex-a53.ipk`  (Depends: glib2, libmbim, **libqrtr-glib**)
- `libqrtr-glib_1.0.0-1_aarch64_cortex-a53.ipk` (Depends: glib2)
- `libmbim_1.26.4-3_aarch64_cortex-a53.ipk`
- `glib2_2.66.4-1_aarch64_cortex-a53.ipk` (Depends: zlib, libffi, libattr)
- `libudev-zero_1.0.1-1_aarch64_cortex-a53.ipk` (drop-in for libudev, which rmtfs needs)

`libqmi` in this feed has QRTR baked in (`Depends: libqrtr-glib`, meson
`-Dqrtr=true`). That is the control-plane path. `qmi-utils` provides
`qmicli` / `qmi-network` / `qmi-firmware-update`.

## rmtfs flags — read the source, do not guess

From `rmtfs.c` `getopt(argc, argv, "o:S:Prsv")`:

| Flag | Meaning |
|---|---|
| `-o DIR` | storage root for EFS images (default `/boot`) |
| `-P` | use raw EFS partitions by-name (mmcblk0pNN style) |
| `-r` | read-only storage (don't write EFS) |
| `-s` | **sync to rproc** — opens the remoteproc via `rproc_open()` and writes "start". **Do not use on wayne**: our kernel boots the modem through PIL/`subsystem_get("modem")`, NOT the remoteproc framework; there is no `qcom,q6v5-mss` rproc node to sync, so `-s` makes rmtfs exit with "Failed to get rprocfd". |
| `-v` | verbose |

For wayne: `rmtfs -r -o /var/lib/rmtfs` (read-only EFS backing in a dir).
Run it from the init script (`modem/rmtfs` in the repo), not with `-s`.

## The device node caveat

`rmtfs_mem_open_uio()` opens `/dev/qcom_rmtfs_uio1` (hardcoded), then reads
udev sysattrs `maps/map0/addr` and `maps/map0/size` off that device. Our
kernel's `msm_sharedmem` driver creates a *standard* uio device,
`/dev/uioN`, named `rmtfs` (`uio_register_device`, `info->name = rmtfs`).

So you **must** create a symlink in the init script *before* starting rmtfs:
```sh
ln -sf /dev/uio0 /dev/qcom_rmtfs_uio1   # whichever uioN is the rmtfs one
```
The udev sysattr path `maps/map0/addr` exists on standard uio devices, so the
daemon's `udev_device_new_from_devnum()` + `parse_hex_sysattr("maps/map0/addr")`
works once the symlink is there.

## Boot order recap

1. kernel up → `/dev/uioN` present (rmtfs node)
2. init script: `ln -sf /dev/uioN /dev/qcom_rmtfs_uio1`
3. mount modem VFAT partition ro → wire `/lib/firmware/{mba.mbn,modem.mdt,modem.bNN}`
4. `rmtfs -r -o /var/lib/rmtfs`
5. `echo 1 > /sys/class/modem-boot/modem0/boot`
6. `qmicli --dms-set-operating-mode=online` (from `qmi-utils`)
7. WDS start-network → `rmnet_data0` → netifd

## The two Makefiles (SDK/buildroot use)

- `libqrtr/Makefile` — builds raw `libqrtr.so` + `qrtr-ns`.
- `rmtfs/Makefile` — builds the rmtfs daemon, depends on `libqrtr` + `libudev-zero`.

Both are written for the OpenWrt SDK (`include $(TOPDIR)/rules.mk`, meson for
qrtr, simple Makefile passthrough for rmtfs). They are reference recipes — the
shipped artifact in this repo is the rootfs overlay, not a buildroot package.
