# OpenWrt on Xiaomi Mi 6X (wayne)

**Booting a full [ImmortalWrt](https://downloads.immortalwrt.org/) (OpenWrt fork) on the Xiaomi Mi 6X (wayne, SDM660) — on the stock vendor kernel `4.19.325-LKGeek-perf-devhamid`.**

**Vision / definition of done:** phone = pocket modem + services box, finished entirely on vendor kernel 4.19 + OpenWrt 21.02. **The finish line = a flashable OpenWrt ROM installable from TWRP/OrangeFox (recovery zip) — no PC, no fastboot.** Mainline kernel + OpenWrt 25/newest are a *future* track after v1.0 (mainline still buggy: partial modem, broken power management — moving now would break more than it fixes).

## Roadmap (interactive blueprint)

**Overall progress: ████████░░░░░░░░░░░░ ≈ 50%** — M1–M5 done.

```
YOU ARE HERE
    ▼
[M1✅][M2✅][M3✅][M4✅][M5✅][M6  ][M7? ][M8  ][M9★ ][FUT ]
 kernel  RAM   root  boot  SSH   host  dock? 21svc zip   mainline later
                                              = finish: OrangeFox-flashable ROM
```

### ✅ Done

| # | Milestone | State |
|---|---|---|
| M1 | Kernel boots + serial console | 100% |
| M2 | Full userspace in RAM (switch_root → procd) | 100% |
| M3 | Persistent rootfs on eMMC p64 (v0.9.4, 2026-10-14) | 100% |
| M4 | Standalone boot, no PC (p58 flashed) | 100% |
| M5 | USB gadget ethernet + serial → SSH (v0.9.6, 2026-10-15) | 95% |

- **M5:** ONE configfs gadget (`g1`) = ACM serial (`ttyGS0`↔`ttyACM0`) + RNDIS ethernet (`usb0`↔PC). DHCP + dropbear → `ssh root@192.168.42.1`. Dropbear duplicate-`Interface` bug fixed (normalize to single `usb0` each boot). *Closeout:* flash v0.9.6 installer-boot → zero-touch SSH; re-test on a good USB port (PC port 3-1.2 is a bad Acer hub, not the phone).

### 🔜 Next

- **M6 — USB OTG host mode (pocket modem).** dwc3 as HOST: tethered phone USB → Wayne WAN → NAT. Single UDC = device XOR host; tear the gadget down cleanly; NEVER unbind dwc3 (panics this kernel).
  - **Lever (found 2026-10-15):** `/sys/devices/platform/soc/a800000.ssusb/mode` = the role switch (`peripheral`|`host`). No `usb_role_switch` class on 4.19; extcon0..4 exist but are read-only notifications. PD phy extcon `USB=1` confirms cable presence.
  - **Test harness:** `scripts/m6-roleswitch.sh` — `status` (read-only), `host` (guarded flip + 60s auto-rollback), `hold` (300s window, continuous device logging; `HOLD_S=600` to extend), `peripheral` (manual early return). Must run **detached** (`>/dev/null 2>&1 &`) because the flip kills both SSH and the ttyGS0 console. Log → `/root/m6.log`.
  - **VBUS / OTG power investigation (2026-10-16):** host mode comes up (xHCI bus1+bus2) but with a real device seated on an OTG hub the port shows ZERO enumeration - dmesg never sees a plug event. Evidence: `extcon3 (qpnp-smb2): USB=0 USB-HOST=0` while host is up (charger never notified of host role) and `regulator.75 smb2-vbus state=disabled` (port not sourcing 5V). `scripts/vbus-probe.sh` flips to host, dumps extcon/regulator/power_supply state, attempts `smb2-vbus` enable, auto-rolls back. Log -> `/root/vbus.log`. HARDENED v2 (2026-10-16): a host-mode dump can HANG on a sysfs read (port electrically dead to PC, dwc3 mid-transition); v1 hung, never rolled back, UDC left empty -> BOTH ssh and ttyGS0 dead -> reboot required. v2 adds an INDEPENDENT watchdog that forces peripheral at T+25s even if the main body hangs, drops `find /sys`, and bounds every sysfs read with `timeout`. RULE: never touch the USB cable during a host-mode test. LATEST (2026-10-16): `regulator.75/state` is 0444 -> NOT writable from userspace, root or not; the enable path must be in-kernel. The ONE writable gate found is `/sys/module/policy_engine/parameters/pd_vbus_ctrl` (rw; `echo 1` accepted 0->1) -- it hands VBUS control to the PD policy engine (`drivers/usb/pd/policy_engine.c`, forked QCOM usbpd). `scripts/vbus-host-test.sh` sets pd_vbus_ctrl=1, flips to host, logs extcon3/extcon4/regulator.75/BOOST_CURRENT + device products every 5s for 120s, watchdog rollback. Test: does `smb2-vbus` go enabled and a hub device enumerate -> if yes M6 power is solved; if not, patch the PD PHY driver so host-role raises vbus. Next: if the regulator is writable, force 5V on; else fix the enable path in driver/DT.
  - **CORE PROVEN (2026-10-16, real device):** clean teardown → `mode=host` → xHCI up on BOTH buses (USB2 `1d6b:0002` + USB3 SuperSpeed `1d6b:0003`, 1 port each) → auto-rollback restores `mode=peripheral` + UDC bound, SSH/serial returned. Remaining: downstream device enumeration (needs a real USB device on OTG — PC is a host, invisible to host mode) and VBUS power if a bus-powered device stays dark.
  - *Done when:* a client gets internet THROUGH Wayne via NAT.
- **M7 — Docker feasibility probe on 4.19 (open question, not a promise).** Check live kernel features (`/proc/cgroups`, namespaces, `overlay`), try a static dockerd → `docker run hello-world`. YES → M8 includes Docker. NO → v1.0 runs services native (procd + Hermes), Docker revisited on the future mainline track. *Done when:* probe answered with evidence.
- **M8 — Full OpenWrt experience on 21.02 (the biggest open surface).** Stock armvirt/64 rootfs ships NONE of this today — all of it gets built/probed here:
  - **LuCI webui** — package it into the image (opkg at CI time), reachable over usb0/ethernet; phone = router you configure in a browser.
  - **Wi-Fi — AP (hotspot) vs client mode** — probe vendor `qcacld-3.0`/wlan driver against hostapd/wpa_supplicant on 4.19; vendor driver is cfg80211-based, so AP *may* work natively, but unproven → answer with evidence, not hope.
  - **Cellular data** — SDM660 modem reachable only via Qualcomm IPC/QRTR stack (Android used qmuxd); bring-up = probe qrtr + data-path on 4.19. Hard, honest odds, same evidence rule.
  - **Customization** — opkg feeds, themes, extra services, dockerman only if M7 says yes.
  - Also: Hermes agent port, firewall/NAT zones (lan/usb0/wan).
  *Done when:* Wayne routes + serves (webui up, wifi + modem probed with YES/NO evidence) with config surviving reboot.
- **M9★ — Polish + recovery-flashable ROM → v1.0.** Baked-in root password, RTC/NTP at boot, thermal/charging, USB reconnect watchdog. **The actual finish = flashable OpenWrt ROM for TWRP/OrangeFox**: recovery zip (`updater-script`/`update-binary`) writing boot image + rootfs to p64 with the 5 p64-only guards. *Done when:* zip flashed from OrangeFox → phone boots → SSH works → tag `v1.0`.

### 🔮 Future track (parked, post-v1.0)

**Mainline SDM660 (pmOS) + OpenWrt 25/newest.** Not abandoned — sequenced after the finish. Re-run the M1–M5 gauntlet as acceptance.

### 🧭 Guide rules

- Milestones gated (M6 needs M5 closed; M7 probe before any Docker promise).
- Every flash: rollback ready (`fastboot flash boot boot-backup.img`), OrangeFox on p59 intact, installer touches ONLY p64.
- Evidence over optimism: live sysfs + PC dmesg + CI gates, not assumptions.
- Stack frozen: 4.19 + 21.02 until v1.0. No mid-run kernel/OpenWrt jumps.

### ⚠️ Top risks

1. **M6 single-port exclusivity** — gadget vs host can't coexist; design the switch deliberately.
2. **M7 Docker-on-4.19 odds** — vendor kernel may lack container features; scope v1.0 to survive a NO.
3. **Vendor modem/Wi-Fi ceiling** — define v1.0 by what works (USB networking + routing + services), not by missing radios.

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

Two boot images are produced per build:

| Image | Contents | Purpose |
|---|---|---|
| `debug-boot.img` | kernel + tiny busybox shell (~1 MB ramdisk) | Proves the kernel itself boots on wayne. Dumps device tree, partitions, USB state to a serial console. |
| `openwrt-boot.img` | kernel + full OpenWrt rootfs (~7 MB ramdisk, ~20 MB total) | The real thing. If debug boots and this doesn't, the problem is OpenWrt's userspace, not the kernel. |
| `donor-control.img` | PINNED donor kernel + PINNED donor Android ramdisk | **The control.** Known-good payload repacked through OUR packer. If this boots, our packer is fine; if it bootloops, our image assembly is the bug. |
| `bisect-kernel.img` | OUR kernel + DONOR's Android ramdisk | Splits kernel vs initramfs faults: boots Android → kernel fine; loops → kernel at fault. |
| `bisect-initramfs.img` | DONOR kernel + OUR debug initramfs | Splits the other way: loops → initramfs at fault; stuck-on-logo → PID 1 alive but invisible. |
| `installer-boot.img` | kernel + installer ramdisk | Installs persistent rootfs to `mmcblk0p64` (userdata, ext4). **The only partition ever written.** 5 safety guards. |

## Boot failure troubleshooting (no console on this hardware)

This kernel has no framebuffer console (`CONFIG_VT=n`), so a working boot can look like "stuck on Mi logo". Distinguish failure modes:

| Symptom | Meaning | Next step |
|---|---|---|
| Bootloop (logo reappears) | Reset observed — kernel panic, watchdog, or bootloader rejection. NOT proven to be a panic. | Try the donor-control image |
| Stuck on logo, no loop | Inconclusive — headless boot looks identical | Check USB serial on a PC |

## Build

Every push to `main` runs the workflow. Or run it manually: **Actions → Build OpenWrt Wayne → Run workflow**. Every `v*` tag builds AND publishes a GitHub Release with images attached (public assets — no auth needed to download).

Artifacts land under **Actions → <your run> → wayne-openwrt**.

## Boot (safe, from RAM only)

```bash
# connect phone in fastboot mode
fastboot boot debug-boot.img      # kernel diagnostic shell
fastboot boot openwrt-boot.img    # full OpenWrt
```

`fastboot boot` loads the image into RAM and starts it **without writing anything**. If it fails, the phone simply reboots back to Android.

Flash (persistent, boot partition only — userdata/rootfs untouched):

```bash
fastboot flash boot installer-boot-v0.9.6.img   # then: boot, follow on-device installer
# rollback:
fastboot flash boot boot-backup.img
```

## Access after install (M5)

- **SSH:** plug USB-C into PC → PC gets a DHCP lease (`192.168.42.x`) → `ssh root@192.168.42.1` (root password set via `passwd`).
- **Serial console:** `/dev/ttyACM0` (Linux) or `COM5` (Windows) at 115200 — `screen /dev/ttyACM0 115200` or `picocom -b 115200 /dev/ttyACM0`.
- **Addresses:** phone `usb0 = 192.168.42.1/24`, dropbear LISTEN `192.168.42.1:22`, dnsmasq DHCP range `.100–.149`.
- **Known gotcha:** dropbear `active with no instances` → `uci delete dropbear.@dropbear[0].Interface; uci add_list dropbear.@dropbear[0].Interface='usb0'; uci commit dropbear; /etc/init.d/dropbear restart`.

## Files in this repo

```
.github/workflows/build.yml         the entire build, runs on GitHub Actions (with M5 gate)
kernel-config-fragment.txt          extra kernel options appended to wayne defconfig
overlay-openwrt/init                /init wrapper: kernel → procd handoff
overlay-openwrt/usb-gadget.init     M5: configfs gadget + UCI usb0/dhcp + dropbear normalize
overlay-debug/init                  /init for the debug shell (kernel diagnostics)
overlay-common/usb-gadget.sh        gadget helper (60s UDC wait, logging)
scripts/pack-boot.py                boot.img packer (donor header + cmdline integrity)
scripts/check-pack.py               regression test: repack → unpack → byte-compare
README.md                           this file (roadmap + approach)
CHANGELOG.md                        version history
TERMS-OF-DELIVERY.md                what this delivers (and what it does not)
TERMUX-PUSH-COMMANDS.md             your exact Termux git commands
```

## Credits

- Kernel: [LKGeek_sdm660](https://github.com/DevHamid/LKGeek_sdm660) (Linux 4.19.325, wayne DTS included)
- Userspace: [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 21.02.7 armvirt/64
- Build recipe derived from [Kernel_Action](https://github.com/DevHamid/Kernel_Action)

## Changelog & Releases

Version history lives in [CHANGELOG.md](CHANGELOG.md) and on the [Releases page](https://github.com/DevHamid/wayne-openwrt/releases).

---
**Repo maintenance rule:** on every push, update this README's roadmap/status first — this file is the project's source of truth for progress.
### Screen / burn-in protection (userspace, no kernel change)
Vendor kernel already ships the display stack (`CONFIG_FB_MSM_MDSS=y`,
`CONFIG_BACKLIGHT_QCOM_SPMI_WLED=y`). Userspace control:
- panel: `/sys/class/graphics/fb0/blank` (0=on, 1=blank, 4=power-down). `fb1`/`fb2`
  are MDSS **writeback** outputs, not the panel — use `fb0`.
- backlight: `/sys/class/leds/lcd-backlight/brightness` (0..`max_brightness`=4095).
- build-time auto-guard: `overlay-openwrt/etc/init.d/burnin-guard` (START=99) runs
  `screen.sh offdelay 90` at every boot, so the panel goes dark 90s after boot
  (no more lit logo burning in). Override: `/etc/init.d/burnin-guard stop`, or
  `sh /root/screen.sh on` to light it up manually. Will be replaced by the M8
  on-panel stats display later.
- helper: `scripts/screen.sh` — `status` | `off` | `on` | `set <n>` |
  `offdelay [s]` (one-shot) | `toggle [s]` (alternate off/on, burn-in guard) | `stop`.
  Detached-safe: `sh screen.sh offdelay 90 >/dev/null 2>&1 &`.
- later (M8): a console on fb0 (`/dev/tty1` + `con2fbmap`) can show uptime / net /
  IP stats on the panel.


