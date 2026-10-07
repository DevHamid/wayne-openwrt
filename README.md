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
