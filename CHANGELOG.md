# Changelog

All notable changes to this project. This is the human-readable history; the
same content is published on the [Releases page](https://github.com/DevHamid/wayne-openwrt/releases),
where each release also carries the built boot images as downloadable assets.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [v0.9.6] — 2026-10-15 — M5 persistence: usb0 as real UCI interface (DHCP + dropbear)

M5 hardware verified 2026-10-15: single configfs gadget brings up `acm.usb0`
(`/dev/ttyGS0` serial console) + `rndis.usb0` (USB ethernet). On the PC:
`/dev/ttyACM0` + `rndis_host` NIC. Device: `ttyGS0` + `usb0` @ 192.168.42.1.

**Post-M5 bug:** dropbear never listened on the gadget at boot.

Root cause: `usb-gadget.init` fallback did `ip addr add 192.168.42.1/24 dev usb0`
— a raw address invisible to netifd. dnsmasq (no UCI dhcp.usb0) served no DHCP,
and dropbear refused with `interface usb0 usb0 has no physdev or physdev has no
suitable ip`. The PC then had no IPv4 on the RNDIS NIC at all (link-local only),
so `ssh root@192.168.42.1` = connection refused. dropbear only listened after a
manual `uci delete dropbear.@dropbear[0].Interface` + restart.

- **`overlay-openwrt/usb-gadget.init`**: fallback now creates a real UCI interface
  — `network.usb0` (static 192.168.42.1/24) + `dhcp.usb0` (dnsmasq, lease .100+)
  — and adds `usb0` to dropbear's Interface list only when that list exists. Result:
  plug phone into PC -> DHCP lease -> `ssh root@192.168.42.1`, no manual steps.
  The br-lan path (DHCP @ 192.168.1.1) is unchanged and preferred when it works.

Flashing: `wayne-installer-boot-v0.9.6.img` via `fastboot flash boot` only — the
existing rootfs/config on p64 is kept; no userdata reformat.

## [v0.9.5] — 2026-10-15 — M5: USB gadget ethernet + serial console from ONE gadget

**Path R (runtime UDC steal) is DEAD.** Unbinding the `dwc3` platform device to
free the UDC for a configfs gadget **panics this vendor kernel** — twice, two
independent scripts, both times the phone dropped and rebooted. Console dies at
`echo a800000.dwc3 > /sys/bus/platform/drivers/dwc3/unbind`, log truncates at
`unbind rc=0`, no further output ever reaches disk. Not recoverable at runtime.

**Root cause of the whole M5 blocker:** `CONFIG_USB_G_SERIAL=y` made the legacy
`g_serial` gadget bind the single UDC (`a800000.dwc3`) automatically at boot.
Nothing else can then claim the UDC — every configfs gadget fails with
`ash: write error: Resource busy`.

Changes:

- **`kernel-config-fragment.txt`**: `CONFIG_USB_G_SERIAL` is now **not set**.
  `USB_CONFIGFS_ACM`/`_RNDIS`/`_NCM`/`LIBCOMPOSITE` stay on.
- **New `overlay-common/usb-gadget.sh`**: `usb_gadget_up()` builds ONE configfs
  composite gadget `g1` — `acm.usb0` → `/dev/ttyGS0` (console) + `rndis.usb0` →
  `usb0` (ethernet). Idempotent (safe to call twice).
- **`overlay-openwrt/init`, `overlay-debug/init`, `overlay-installer/init`**:
  replace the old "wait for g_serial" logic with a call to `usb_gadget_up`.
- **New `overlay-openwrt/usb-gadget.init`** (`/etc/init.d/usb-gadget`, `START=95`):
  the persistent p64 rootfs boots procd, not our `/init`, so this service builds
  the gadget there and bridges `usb0` into `br-lan` (fallback: static
  `192.168.42.1/24` + dropbear Interface `usb0`).
- **`overlay-installer/init`**: installs the service + script into the target
  **outside** the install-once guard, so an already-installed p64 also gets it.
- **`build.yml`**: ships `usb-gadget.sh` into all three images and the init.d
  service into the OpenWrt/installer images.

NOT yet built or flashed. Requires CI unfreeze (one kernel rebuild).

## [v0.9.4] — 2026-10-14 — debug installer (robust /init)

Root cause confirmed: the installer `/init` died at **runtime**, silently. Prime
suspect: v0.9's `exec >/dev/console` (line 39) — if that redirect fails, a
non-interactive POSIX shell **exits**, PID 1 dies, the vendor kernel panics, and
the phone reboots to Android with zero output. The working `openwrt` `/init`
never performs that redirect.

Changes (install logic + all 5 guards **unchanged**):

- **No `exec >/dev/console`** anywhere. All output is *mirrored* to
  `/dev/console`, `/dev/ttyGS0`, and `/tmp/installer.log`.
- **Timestamped** `say()` at every step, so the last line printed is the exact
  failure point.
- **`EXIT`/`INT`/`TERM` trap** → no path can kill PID 1; any failure respawns a
  rescue shell on USB serial instead of panicking.
- **Rescue shell from the first seconds**, on `ttyGS0`, respawning forever.
- **configfs `f_acm` fallback** if legacy `g_serial` never binds a `ttyGS0`.
- **3 s "plug in now" pause** before any work.
- CI now prints the installer `/init` sha256 and asserts the `exec >/dev/console`
  line is gone.

## [v0.9.3] — 2026-10-14 — installer-boot.img root-cause investigation

- Symptom: `fastboot boot installer-boot.img` → stuck at Mi logo, no `ttyACM0`,
  phone reboots to Android. `openwrt-boot.img` and `donor-control.img` boot to
  `ttyACM0` fine.
- Evidence gathered from CI run #12 logs (steps 8/9/15/16/17/18/19/20):
  - Step 18: installer uses the plain `pack-boot.py` + donor cmdline verbatim
    (312 chars, **no `root=`**) — the old `root=` theory is dead.
  - `check-pack.py` PASS: kernel + ramdisk byte-identical after re-pack, cmdline
    preserved (312 chars), image 21,348,352 bytes.
  - Ramdisk sizes: `openwrt-boot.img` 6,907,814 B (WORKS) vs `installer-boot.img`
    6,908,450 B (FAILS) — a 636 B delta ≈ the init-script size difference. Kernel
    bytes identical, same rootfs.
  - Kernel config + OTG hard gate (steps 15/20): all green — no kernel-side
    gadget problem.
- Conclusion: **the only functional difference between the working and failing
  image is `/init` itself.** The installer `/init` is clean on disk (`sh -n` OK,
  no CRLF, no non-ASCII), so the failure is at *runtime*: it dies early on-device,
  before it can bring up / use the serial gadget — and when PID 1 dies, the vendor
  kernel panics and reboots (matches: Mi logo → Android).
- Note: local repo `origin/main` ref was stale (pointed at v0.7) — the
  "8 commits ahead" was just an un-fetched remote, not divergence.
- Next: v0.9.4 **debug installer** (see above).

## [v0.9.3] — eMMC persistent rootfs installer + OTG hard gate

- `installer-boot.img`: formats `/dev/mmcblk0p64` (userdata, 49 GiB) as ext4 and
  copies the live OpenWrt rootfs onto it, so the phone can later boot a
  persistent system without a PC.
- OTG hard gate: the build now **fails red** if `CONFIG_EXTCON` /
  `CONFIG_USB_DWC3_DUAL_ROLE` / `CONFIG_USB_XHCI_HCD` / `CONFIG_USB_STORAGE` /
  `CONFIG_BLK_DEV_SD` / `CONFIG_EXT4_FS` did not resolve to `=y`, so a silently
  non-OTG kernel can never ship as a green build.
