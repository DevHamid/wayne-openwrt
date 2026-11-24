# Changelog

All notable changes to this project. This is the human-readable history; the
same content is published on the [Releases page](https://github.com/DevHamid/wayne-openwrt/releases),
where each release also carries the built boot images as downloadable assets.

The format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## v0.10.0

**2026-11-24** · [compare changes](https://github.com/DevHamid/wayne-openwrt/compare/v0.9.16...v0.10.0)

### 🚀 Enhancements

- 📡 **modem:** add ModemManager LTE data-call bring-up script ([`c06dda3`](https://github.com/DevHamid/wayne-openwrt/commit/c06dda38582f658331429123526c359baf351a2c))

### 🩹 Fixes

- make split ROM bootstrap fail closed ([`f85eb34`](https://github.com/DevHamid/wayne-openwrt/commit/f85eb343ae5deab6f4d2efde583c7422da622ab6))
- avoid SIGPIPE in OTA manifest rootfs gate ([`2a98477`](https://github.com/DevHamid/wayne-openwrt/commit/2a984775037acbc9c423ed3a656649291ef3a029))
- use single-write sysfs updates in screen guard ([`42868de`](https://github.com/DevHamid/wayne-openwrt/commit/42868def284e079517e5f72d0a05c3b8ccfaa287))
- stage USB gadget helper in ROM rootfs ([`7b24eac`](https://github.com/DevHamid/wayne-openwrt/commit/7b24eac854ce3d8d48ab76cc3b8ac0316ad27643))
- 📦 **rom:** install script v2 — live-root tar overlay instead of reformatting the running root ([`0bd1a18`](https://github.com/DevHamid/wayne-openwrt/commit/0bd1a18614ad80f68e18fcf79568abb461f0a5ce))
- 📦 **rom:** include the diag-reader init in the assembled rootfs ([`2e227fa`](https://github.com/DevHamid/wayne-openwrt/commit/2e227fab8bda3b70e101ed87352b5e54b151e4b7))

### 📖 Documentation

- add first-install clarification and OTA prerequisites to README ([`5cf6f33`](https://github.com/DevHamid/wayne-openwrt/commit/5cf6f33675c6e844f64cad14ffa31421fd5fe79c))
- 📖 **README:** 2026-11-22 status — modem ERR_FATAL loop root-caused and fixed ([`0b5b6a4`](https://github.com/DevHamid/wayne-openwrt/commit/0b5b6a4a9d879fcc23b691e3b82f6f04ac9a7eac))
- record the Wi-Fi root cause + wlan.ko late-load fix; drop dead qrefresh files ([`4dc37c5`](https://github.com/DevHamid/wayne-openwrt/commit/4dc37c50cb8870ee7c4ef07d11c55ae40bc4bd3d))
- boot-loop root cause — AP panic in IPA QMI handle use-after-free ([`94e688b`](https://github.com/DevHamid/wayne-openwrt/commit/94e688b5a5e460f346ded8a9bd7281d52292d8e7))
- record 24.10 promotion and the PID-1 bootstrap fix in the README ([`da50f22`](https://github.com/DevHamid/wayne-openwrt/commit/da50f22607a765ed4890a32f8b0c705771427791))
- embed the generated roadmap SVG in the README ([`11a292c`](https://github.com/DevHamid/wayne-openwrt/commit/11a292c139859c75c389acdc426c4089316769e5))
- add plain-language progress report for the Wayne pocket modem ([`1ec2679`](https://github.com/DevHamid/wayne-openwrt/commit/1ec267977b9106089671d8b7a89f120451fe9734))
- 2026-11-24 status — diag starvation root-caused and fixed, modem stable + registered ([`5536842`](https://github.com/DevHamid/wayne-openwrt/commit/55368429b9f38f2bebefad64380c23039a5464d8))
- 🏷️ **progress:** late-Nov-24 update — ModemManager ROM released, installer rewritten for the live-root layout, recovery automated ([`5825e3d`](https://github.com/DevHamid/wayne-openwrt/commit/5825e3de5c2aa7abe0d028a523cc49b23f3f3acc))
- 2026-11-24 late — ModemManager ROM released; live-root installer v2; diag-reader now in every rootfs ([`67f5a39`](https://github.com/DevHamid/wayne-openwrt/commit/67f5a3915e33206c3b29d6bc25214a2b7466702e))
- add generated roadmap SVG (rendered from the README roadmap) ([`9355c40`](https://github.com/DevHamid/wayne-openwrt/commit/9355c4014957f86bc08366d9acc4047a151c4b4a))

### 📦 Build

- 📦 **2410:** promote ImmortalWrt 24.10.4 to a flashable production ROM ([`12d48a4`](https://github.com/DevHamid/wayne-openwrt/commit/12d48a4e31f6301a1d17da936d8d72e05f3c0b83))
- 📦 **2410:** allow the RAM diagnostic image to carry the full rootfs ([`47a1279`](https://github.com/DevHamid/wayne-openwrt/commit/47a127906a22335c95c3e5ab13a69f6ac8abc3e1))
- 📦 **2410:** fix false 'missing file' ROM gate caused by grep -q under pipefail ([`4d5856e`](https://github.com/DevHamid/wayne-openwrt/commit/4d5856eb55096913074b2042f071817bdb6befa3))
- 📦 **2410:** parameterize the boot-size guard in check-2410.py too ([`5052e3b`](https://github.com/DevHamid/wayne-openwrt/commit/5052e3ba37dd969bcc1d19168c0015fc6e6320ec))
- 🏷️ **check-pack:** fix off-by-one reading the optional MAX_MIB argument ([`9266b65`](https://github.com/DevHamid/wayne-openwrt/commit/9266b65720952476ea054cf006030f8bbd1dcb0a))
- gate ROM publication on the QRTR service registry ([`a570a5d`](https://github.com/DevHamid/wayne-openwrt/commit/a570a5db4a25bd44d27ebb4817665cb637528c72))
- stage WLAN firmware + enable modem auto-boot in image ([`cc88db4`](https://github.com/DevHamid/wayne-openwrt/commit/cc88db4087805d1b6bc899934e51c1a62722c187))
- drop wayne-qrefresh — the qrtr kernel registry supersedes it ([`e7a1324`](https://github.com/DevHamid/wayne-openwrt/commit/e7a1324778bc2277540fc86901762e6f65e45f6c))
- 📦 **2410:** install the persistent USB gadget helper into the ROM rootfs ([`87ef463`](https://github.com/DevHamid/wayne-openwrt/commit/87ef4634be7060ad19f48b9994d29f134b47bc6d))
- 📦 **2410:** assemble ModemManager + LuCI modem glue; enforce 24.10 baseline ([`a4546f5`](https://github.com/DevHamid/wayne-openwrt/commit/a4546f5b4219cdfddf746656eebbf070fffbd205))

### 🧩 Other

- 🏷️ **wayne:** ship modem radio services + qrefresh re-announcer ([`8a8fe83`](https://github.com/DevHamid/wayne-openwrt/commit/8a8fe8319cc7afcde7e44613df592ad70517879a))
- 🔌 **usb:** link usb0 up in the gadget helper instead of relying on netifd ([`1d33bc9`](https://github.com/DevHamid/wayne-openwrt/commit/1d33bc980c2d625c641323c4ecdc584cf62e8dcc))
- 🔌 **usb:** await gadget UDC bind before switch_root so the management link survives ([`5628230`](https://github.com/DevHamid/wayne-openwrt/commit/56282302e55c2fb4405e1cbe8d10193c47ede4de))
- 🏷️ **Add:** diag-reader init service: keep modem DIAG drained ([`014b057`](https://github.com/DevHamid/wayne-openwrt/commit/014b0572063f4cad3d628a92db93384891402445))

### ❤️ Contributors

- shifu
- Ahmad Syarwan Hamid
- DevHamid

## [v0.9.10] — M7 probe script

`scripts/m7-docker-probe.sh` → `/root/m7.sh` (installed by `build.yml`, re-copied
by `overlay-installer/init`). Answers M7 with the running kernel:

- `/proc/cgroups` listing + a real memcg mount that must ACCEPT
  `memory.limit_in_bytes` (listing alone is not proof).
- freezer / pids / devices cgroup mounts.
- `unshare -n` (a net namespace must open, not merely exist).
- overlay mount with copy-up write on the real root filesystem — the exact
  thing `overlay2` needs.
- veth pair + bridge creation, MASQUERADE rule insert/delete.
- RAM/disk headroom and whether a `docker` binary exists.

Verdict: `M7=YES` / `M7=DEGRADED` / `M7=NO`, written to `/root/m7.log`.
Read-only apart from temporary objects it removes.

## [v0.9.10] — 2026-10-17 — M7 prep: container kernel enablers

Kernel config audit for the Docker probe. Vendor defconfig already carried
`CGROUPS`, `CGROUP_SCHED`, `CGROUP_CPUACCT`, `NAMESPACES`, `NET_NS`,
`OVERLAY_FS`, `BRIDGE`, `NF_NAT`, `NETFILTER_XT_TARGET_MASQUERADE`.

Added to `kernel-config-fragment.txt` (pure enablers, no behaviour change):

```
CONFIG_MEMCG=y  CONFIG_MEMCG_SWAP=y   <- withheld (see bisect note below)
CONFIG_CGROUP_DEVICE=y  CONFIG_CGROUP_FREEZER=y  CONFIG_CGROUP_PIDS=y
CONFIG_VETH=y  CONFIG_BRIDGE_NETFILTER=y
```

**Resolved 2026-10-17:** the build failure was `CONFIG_BRIDGE_NETFILTER=y`.
`net/bridge/br_netlink.c` references `nf_call_iptables` / `nf_call_ip6tables` /
`nf_call_arptables`, members that this vendor `br_private.h` does not have
(LKGeek removed br_netfilter). Symbol dropped; `VETH` + `BRIDGE` +
`CGROUP_DEVICE/FREEZER/PIDS` all compiled. Docker's userland proxy covers the
missing bridged-frame filtering for published ports.

**Bisect note:** the first commit carrying all of these (`f6613d1`) failed the
kernel-build step, so this entry describes the *intended* set. The shipped
order is cgroup-device/freezer/pids + veth + bridge-netfilter first; `MEMCG*`
is re-added in a separate commit so a failure there is unambiguously its fault.
Job logs need repo admin (403), so the split is the only way to attribute the
break.

- No `MEMCG` → dockerd exits with *"kernel does not support memory limit
  capabilities"*.
- No `VETH` → containers start but have no network.
- `USER_NS` deliberately left OFF (vendor default). Only rootless Docker needs
  it; root dockerd does not.
- `overlay2` on f2fs/ext4 and real RAM headroom remain probe questions, not
  config questions.

## [v0.9.9] — 2026-10-17 — M6 proven working + screen backlight node fixed

### M6 — USB OTG host mode: WORKS (no kernel patch needed)

Decisive test with the **PC unplugged** (external VBUS was the only blocker):

```
[16:53:20] pre: mode=host udc=a800000.dwc3
[16:53:20] extcon4=USB=0 USB-HOST=1 DP=0
[16:53:20] reg75=enabled TYPEC_MODE=Powered cable w/ sink
[16:53:20] usb_devs=1-0:1.0 1-1 1-1.1 1-1.1:1.0 1-1.2 1-1.2:1.0 1-1:1.0 2-0:1.0 usb1 usb2
```

Real drivers bound downstream:

```
usb 1-1:   idVendor=1a40 idProduct=0801  "USB 2.0 Hub"        (4 ports)
usb 1-1.1: idVendor=0781 idProduct=5590  SanDisk "Ultra"      + usb-storage -> scsi host0 -> sda1 sda2 (FAT parsed)
usb 1-1.2: idVendor=046d idProduct=c542  Logitech Wireless Receiver -> USB HID Mouse input5
```

**Root cause, closed:** with the PC attached, `/sys/class/power_supply/usb`
reports `VOLTAGE_NOW=5019531` — an external 5V is being driven *into* the port.
The PM660 refuses to start its own boost under back-feeding, which is exactly
what `wa_flags=0x72` (`BOOST_BACK_WA`) encodes; all four softstart currents
returned `TIMEOUT rc=-22`. Unplugging the PC removes the back-feed and the same
path softstarts first try.

- The kernel was never wrong: `mode_store` already does the right thing
  (`vbus_active=false` + `dwc3_id_start_peripheral`, `vbus_dwc3` supply wired
  in v0.9.7). **No new driver patch.**
- The v0.9.8 non-fatal patch is what kept this debuggable: on v0.9.7 the VBUS
  refusal aborted before `dwc3_host_init()` and xHCI never appeared.
- Operational rule: host mode is standalone-only. The PC (console) and the
  phone's own source role cannot share the port — observe detached logs
  (`/root/vbus.log` + `dmesg`) or use the serial console during host runs.
- Clean teardown confirmed on PC replug: `Nothing attached`, `reg75=disabled`,
  `usb_devs=` empty, xhci buses deregistered.

### Build: M6 harness is now part of the image

`/root/m6.sh` (role switch + 60s auto-rollback) and `/root/vbus-host-test.sh`
(detached VBUS/enumeration probe) are installed by `build.yml` and re-copied to
the target rootfs by `overlay-installer/init` on every boot, exactly like
`screen.sh`. Previously they only existed in the repo, so every reflash meant
retyping them one line at a time over the serial console.

### Screen: the guard ran but wrote a stub

`screen.sh off` set `brightness 0` and the panel stayed lit. The guard was
alive (`guardfg 90` pid 4398, armed) and doing its job — it was pointed at the
wrong node.

- `/sys/class/leds/lcd-backlight/brightness` — accepts writes, readback is
  clean, **panel never changes** (stub).
- `/sys/class/backlight/backlight/brightness` — `type=raw`, max 4095, verified
  on-device: `0` = panel dark, `4095` = panel lit.
- `/sys/class/graphics/fb0/blank` — exists (4096 B, writable) but reads back
  EMPTY; with `Continuous splash enabled` the DSI path is bootloader-owned, so
  backlight is the actuator to rely on.
- `scripts/screen.sh` now auto-selects the first writable `/sys/class/backlight/*`
  and falls back to the LED node only if none exists.

## [v0.9.8] — 2026-10-16 — M6 on-device follow-up (host regression) + screen guard under procd

### M6: v0.9.7 regression — host mode lost entirely

v0.9.7's DT fix (`vbus_dwc3-supply`) is correct wiring, but on-device the charger's
`smblib_vbus_regulator_enable()` FAILED and `dwc3_otg_start_host()` bailed before
`dwc3_host_init()` — `usb_devs` empty for the whole run (worse than v0.9.6, which at
least brought the xHCI root hubs up). Log: `unable to enable vbus_reg` then
`unable to start host`.

- **`patches/dwc3-vbus-nonfatal.sh`**: log the rc and CONTINUE — host mode always
  comes up; also make the disable path non-fatal (a failed disable skipped all host
  teardown and wedged the next start).
- **`patches/charger-vbus-diag.sh`**: `smb-lib.c` gates every `smblib_err()` behind
  `#ifdef DEBUG`, which the Makefile never defines, so the charger printed NOTHING.
  Adds unconditional `pr_err()` at ENTER / votable-NULL / OTG_CFG-write / boost
  softstart TIMEOUT / EXIT `rc=N`, so the next flash names the failure.

### Screen: guard supervised by procd + `on` veto

- **`overlay-openwrt/etc/init.d/burnin-guard`**: `USE_PROCD=1` + `screen.sh guardfg 90`
  (respawn 3600 5 5). v0.9.7 backgrounded the daemon from `start()`, and procd reaped
  that child on return — so the screen never went off.
- **`scripts/screen.sh`**: new `guardfg` (foreground twin of `guard`); `on` drops a
  VETO flag (`/tmp/.screen.on`, tmpfs — cleared by reboot) that the guard honours, so
  a manual `on` STAYS on. `off`/`guard`/`stop` clear it. v0.9.7 pidfile bug
  (`$$` vs `$!`) also fixed in all modes.

## [v0.9.7] — 2026-10-16 — M6 VBUS root-cause DT fix + in-image screen/burn-in automation

Two fixes in one build. Neither needs a p64 reformat: flash the installer-boot
image (`fastboot flash boot`) and the new boot/rootfs drop in.

### M6 — OTG host 5V (VBUS) root cause + fix

`scripts/vbus-host-test.sh` proved the writable knob
`/sys/module/policy_engine/parameters/pd_vbus_ctrl` does NOTHING: with
`pd_vbus_ctrl=1` and `mode=host` held 120s, `extcon3 (qpnp-smb2)` stayed
`USB=0 USB-HOST=0`, `regulator.75 smb2-vbus` stayed `disabled`, `BOOST_CURRENT=0`,
and only the two xHCI root hubs appeared (no downstream device). Root cause is
in the kernel/DT, not userspace.

Source-verified (DevHamid/LKGeek_sdm660@build-all-rekernel): `dwc3_otg_start_host()`
(`drivers/usb/dwc3/dwc3-msm.c`) raises the OTG 5V boost ONLY through
`devm_regulator_get_optional(dev, "vbus_dwc3")` + `regulator_enable()`. The stock
`ssusb@a800000` DT node (`sdm660-common.dtsi`) declares `USB3_GDSC-supply` +
`dpdm-supply` but **no** `vbus_dwc3-supply`, so `get_optional` returns NULL and the
enable is silently skipped → `smb2-vbus` never rises → nothing enumerates. Android
masks this because its userspace USB HAL enables `smb2-vbus` itself; OpenWrt has no
such HAL.

- **`patches/usb3-vbus-dwc3-supply.sh`**: idempotently adds
  `vbus_dwc3-supply = <&smb2_vbus>;` to the `ssusb@a800000` node.
- **`.github/workflows/build.yml`**: new step "Apply M6 VBUS DT fix" runs the patch
  before compile and greps the tree to confirm it landed.

Next: flash, seat an OTG device, expect `regulator.75 = enabled` and a `1-1:` device.

### Screen / burn-in automation now IN THE IMAGE

`scripts/screen.sh` + `overlay-openwrt/etc/init.d/burnin-guard` were committed but
**never installed** by the build — so the panel stayed lit on the logo and the
user had to run `screen.sh` by hand. Fixed:

- **build.yml** installs `/root/screen.sh` + `/etc/init.d/burnin-guard` and the
  `S99burnin-guard` rc.d link into the image.
- **overlay-installer/init** re-installs both every boot (outside the
  install-once marker), so an already-provisioned p64 picks them up too.
- **`screen.sh` new `guard` mode**: blank after N s, then RE-ASSERT the blank every
  R s. A one-shot `offdelay` can be silently undone by the panel driver coming up
  late — re-asserting wins that race. `burnin-guard` now calls `screen.sh guard 90`.
- **kill-path bug fixed**: the daemons trap HUP/INT/TERM to survive a closed
  session, so the old `kill` (SIGTERM) was IGNORED and the guard kept re-blanking
  right after a manual `on`. `kill_prev` now uses SIGKILL with a `/proc` cmdline
  check (pid-reuse safe). This is the real cause of "offdelay only works after I
  run status/off/on first".

Manual override is unchanged and instant: `sh /root/screen.sh on`, or
`/etc/init.d/burnin-guard stop`.

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
