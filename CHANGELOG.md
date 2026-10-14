# Changelog

All notable changes to this project. This is the human-readable history; the
same content is published on the [Releases page](https://github.com/DevHamid/wayne-openwrt/releases),
where each release also carries the built boot images as downloadable assets.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
