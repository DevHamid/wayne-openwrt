# OpenWrt on Xiaomi Mi 6X (wayne) — Phase 1: RAM-only boot image

**Booting a full [ImmortalWrt](https://downloads.immortalwrt.org/) (OpenWrt fork) OS on the Xiaomi Mi 6X — entirely in RAM.** Nothing is flashed: `fastboot boot` loads the image into RAM, and a reboot returns to Android. (For the flashing stage later, keep your TWRP backup and original boot.img handy.)

## How it works

```
┌────────────────────────────────────────────────────────────┐
│                        boot.img                            │
│  ┌──────────────┐  ┌───────────────────────────────────┐  │
│  │ kernel + DTB │  │ initramfs = FULL OpenWrt rootfs   │  │
│  │ (wayne)      │  │ (ImmortalWrt 21.02.7 armvirt/64)  │  │
│  └──────────────┘  └───────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
        kernel boots → unpacks initramfs into RAM → runs /init
        → /init hands control to OpenWrt's /sbin/init (procd)
```

Nothing is written to the phone's flash. The entire OS lives inside the boot image's ramdisk, which the kernel unpacks into RAM at boot. This is why we can test safely with `fastboot boot` — no flashing required for experiments.

Two boot images are produced per build:

| Image | Contents | Purpose |
|---|---|---|
| `debug-boot.img` | kernel + tiny busybox shell (~1 MB ramdisk) | Proves the kernel itself boots on wayne. Dumps device tree, partitions, USB state to a serial console. |
| `openwrt-boot.img` | kernel + full OpenWrt rootfs (~7 MB ramdisk, ~20 MB total) | The real thing. If debug boots and this doesn't, the problem is OpenWrt's userspace, not the kernel. |
| `donor-control.img` | PINNED donor kernel + PINNED donor Android ramdisk | **The control.** Known-good payload repacked through OUR packer. If this boots, our packer is fine; if it bootloops, our image assembly is the bug. |
| `bisect-kernel.img` | OUR kernel + DONOR's Android ramdisk | Splits kernel vs initramfs faults: boots Android → kernel fine; loops → kernel at fault. |
| `bisect-initramfs.img` | DONOR kernel + OUR debug initramfs | Splits the other way: loops → initramfs at fault; stuck-on-logo → PID 1 alive but invisible. |

## Boot failure troubleshooting (no console on this hardware)

This kernel has no framebuffer console (`CONFIG_VT=n`), so a working boot can look
like "stuck on Mi logo". Distinguish failure modes:

| Symptom | Meaning | Next step |
|---|---|---|
| Bootloop (logo reappears) | Reset observed — kernel panic, watchdog, or bootloader rejection. NOT proven to be a panic. | Try the donor-control image below |
| Stuck on logo, no loop | Inconclusive — headless boot looks identical | Check USB serial on a PC |

Every build ships diagnostic images for splitting kernel vs initramfs faults:

| Image | Kernel | Ramdisk | Tells us |
|---|---|---|---|
| `donor-control.img` | PINNED donor | PINNED donor | Bootloader accepts our assembly? Test THIS FIRST. |
| `bisect-kernel.img` | OUR build | DONOR's Android ramdisk | Boots Android → our kernel fine, fault is our initramfs. Loops → kernel pairing at fault. |
| `bisect-initramfs.img` | DONOR's | OUR debug initramfs | Loops → our initramfs pairing at fault. Stuck on logo → inconclusive (headless). |

## Files in this repo

```
.github/workflows/build.yml         the entire build, runs on GitHub Actions
kernel-config-fragment.txt          extra kernel options appended to wayne defconfig
overlay-openwrt/init                /init wrapper: kernel → procd handoff
overlay-debug/init                  /init for the debug shell (kernel diagnostics)
scripts/pack-boot.py                boot.img packer (donor header + cmdline integrity)
scripts/check-pack.py               regression test: repack → unpack → byte-compare
README.md                           this file
TERMS-OF-DELIVERY.md                what this delivers (and what it does not)
TERMUX-PUSH-COMMANDS.md             your exact Termux git commands
```

## Build

Every push to `main` runs the workflow. Or run it manually: **Actions → Build OpenWrt Wayne → Run workflow**.

Artifacts land under **Actions → <your run> → wayne-openwrt**.

## Boot (safe, from RAM only)

```bash
# connect phone in fastboot mode
fastboot boot debug-boot.img      # kernel diagnostic shell
fastboot boot openwrt-boot.img    # full OpenWrt
```

`fastboot boot` loads the image into RAM and starts it **without writing anything**. If it fails, the phone simply reboots back to Android. Nothing is flashed, nothing is lost.

## The USB serial console (how you actually see anything)

Both images bring up a USB serial gadget at boot. When the phone boots:

1. Plug the phone into a PC
2. A new serial port appears: `/dev/ttyACM0` (Linux) or `COM5` (Windows)
3. Open it at 115200 baud:

```bash
# Linux
screen /dev/ttyACM0 115200

# or
picocom -b 115200 /dev/ttyACM0
```

The debug image drops you to a root shell immediately. The OpenWrt image shows the full boot log.

## Status

Milestone 1: **kernel boots + OpenWrt rootfs starts** (this repo).

Next milestones (tracked in the roadmap):
- [ ] USB ethernet (RNDIS/NCM) → ping the phone from a PC
- [ ] `opkg` package management working
- [ ] Modem/mobile data (the end goal — hardest part, Qualcomm IPC-RPC plumbing)
- [ ] Flashable recovery zip (TWRP) so `fastboot` is no longer needed
- [ ] Persist OpenWrt config across reboots

## Credits

- Kernel: [LKGeek_sdm660](https://github.com/DevHamid/LKGeek_sdm660) (Linux 4.19.325, wayne DTS included)
- Userspace: [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 21.02.7 armvirt/64
- Build recipe derived from [Kernel_Action](https://github.com/DevHamid/Kernel_Action)

### 2026-10-14 — installer-boot.img root cause investigation (v0.9.3, CI run #12)
- Symptom: `fastboot boot installer-boot.img` → stuck at Mi logo, no `ttyACM0`, phone reboots to Android. `openwrt-boot.img` and `donor-control.img` boot to `ttyACM0` fine.
- Evidence gathered from CI run #12 logs (steps 8/9/15/16/17/18/19/20):
  - Step 18: installer uses the plain `pack-boot.py` + donor cmdline verbatim (312 chars, **no `root=`**) — the old `root=` theory is dead.
  - `check-pack.py` PASS: kernel + ramdisk byte-identical after re-pack, cmdline preserved (312 chars), image 21,348,352 bytes.
  - Ramdisk sizes: `openwrt-boot.img` 6,907,814 B (WORKS) vs `installer-boot.img` 6,908,450 B (FAILS) — a 636 B delta ≈ the init-script size difference. Kernel bytes identical, same rootfs.
  - Kernel config + OTG hard gate (steps 15/20): all green — no kernel-side gadget problem.
- Conclusion: **the only functional difference between the working and failing image is `/init` itself.** The installer `/init` is clean on disk (`sh -n` OK, no CRLF, no non-ASCII), so the failure is at *runtime*: it dies early on-device, before it can bring up / use the serial gadget — and when PID 1 dies, the vendor kernel panics and reboots (matches: Mi logo → Android).
- Note: local repo `origin/main` ref was stale (pointed at v0.7) — the "8 commits ahead" was just an un-fetched remote, not divergence.
- Next: v0.9.4 **debug installer** — timestamped log to serial from the very first line, a 3 s "plug in now" pause before anything else, and a respawning shell on `ttyGS0` on ANY failure path so nothing can ever die silently again.

### 2026-10-14 — v0.9.4 debug installer (robust /init)
Root cause confirmed: the installer `/init` died at **runtime**, silently. Prime suspect: v0.9's `exec >/dev/console` (line 39) — if that redirect fails, a non-interactive POSIX shell **exits**, PID 1 dies, the vendor kernel panics, and the phone reboots to Android with zero output. The working `openwrt` `/init` never performs that redirect.

v0.9.4 changes (install logic + all 5 guards **unchanged**):
- **No `exec >/dev/console`** anywhere. All output is *mirrored* to `/dev/console`, `/dev/ttyGS0`, and `/tmp/installer.log`.
- **Timestamped** `say()` at every step, so the last line printed is the exact failure point.
- **`EXIT`/`INT`/`TERM` trap** → no path can kill PID 1; any failure respawns a rescue shell on USB serial instead of panicking.
- **Rescue shell from the first seconds**, on `ttyGS0`, respawning forever.
- **configfs `f_acm` fallback** if legacy `g_serial` never binds a `ttyGS0`.
- **3 s "plug in now" pause** before any work.
- CI now prints the installer `/init` sha256 and asserts the `exec >/dev/console` line is gone.

Push (from Termux, in `~/wayne-openwrt/repo`):
```
git -C ~/wayne-openwrt/repo pull --rebase origin main
# apply the updated files from the bundle, then:
git add -A && git commit -m "v0.9.4: debug installer (trap+log+rescue shell, drop exec>/dev/console)"
git push origin main
```
