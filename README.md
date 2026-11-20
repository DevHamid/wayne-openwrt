# OpenWrt on Xiaomi Mi 6X (wayne)

**Booting a full [ImmortalWrt](https://downloads.immortalwrt.org/) (OpenWrt fork) on the Xiaomi Mi 6X (wayne, SDM660) — on the stock/vendor Linux 4.19 kernel tree.**

**v1.0 goal:** a standalone pocket modem using Wayne's native cellular modem and Wi-Fi AP on the vendor Android 4.19 kernel with ImmortalWrt 24.10.4. A Wi-Fi client must get an address and reach the internet over Wayne's own cellular connection, with configuration surviving a reboot. The ROM installs from TWRP/OrangeFox without a PC or fastboot. Mainline stays a post-v1.0 track.

## Current status (2026-11-20)

The work is now **structure-first**. We are not treating the full-initramfs image as the product; it remains a RAM/test vehicle. The product path is:

```text
OrangeFox/TWRP recovery zip
  ├─ boot.img              = kernel + tiny static system-bootstrap initramfs
  ├─ system/                = ext4 OpenWrt rootfs (rootfs.tar.gz extracted here)
  └─ userdata/              = persistent config/overlay, selected by rootfs fstab
```

- **Last recorded ujail CI:** run `44397558231`, commit `d266292`, passed. It built the capability-compatible `procd-ujail` package through the pinned 24.10 SDK feed.
- **Pre-install baseline (historical, 2026-11-20):** SSH reaches the same boot; modem OFFLINE, crash count 2, `allow_boot=0`, dump flags 0, original read-only rmtfs retained, and no Wi-Fi PHY. The bounded read-only boot-image digest matches the retained reference Android image. The rootfs build marker is older than the installed kernel, so do not use its source-run field as current kernel provenance or overwrite the marker with the reference rootfs. Eleven of twelve checked baseline files match; this is not a whole-live-rootfs identity claim. Candidate deployment must be additive, preserving USB/rmtfs/modem policy. This was recorded before the operator confirmed recovery access and before the additive install/reboot described below.
- **Current Wi-Fi evidence:** the vendor WLAN/ICNSS driver probes during kernel boot, but `/sys/class/ieee80211` is empty and no Wi-Fi PHY exists. The repeated `PR_CAPBSET_DROP(38)` error is real on this image (`cap_last_cap=37`), but the ujail deployment must be tested before using the userspace failure as a Wi-Fi conclusion.
- **Earlier radio diagnostics (before this checkpoint):** repaired the collector, then captured one bounded ~60-second modem window with six complete discovery snapshots (216 endpoint rows). No fresh modem fatal/SSR was observed and crash count stayed 2. DMS/UIM/NAS services appeared, but locator 64 and WLFW 69 were absent in every snapshot; PHY count stayed zero and no firmware-ready event was retained. Independent readback verified modem OFFLINE, no held modem descriptor, original read-only rmtfs unchanged, dump flags off, and temporary nameserver/staging removed. **Next discriminant: host protection-domain mapping.** The image has no `pd-mapper`; authentic `MODEMUW.JSN` provides `wlan/fw` in `msm/modem/wlan_pd`, and upstream pd-mapper publishes locator service 64. Its default remoteproc-based map discovery cannot be used unchanged on this vendor PIL system, which has no remoteproc class. An explicit-directory userspace candidate now passes eight offline tests separately on the host, with address/undefined-behavior sanitizers, and as static ARM64 under QEMU, including the authentic WLAN map response and locator version/instance encoding. Native no-socket map validation now passes on Wayne after SSH reauthentication; an independent readback verified temporary staging/process absence, modem OFFLINE with crash count 2, read-only rmtfs unchanged, and dump flags 0. No mapper startup service or ROM integration has been installed. A subsequent bounded modem-off probe verified native local locator publication: service 64 appeared at version 1 / instance 1 / local node 1 after starting the candidate, and independent readback confirmed both temporary daemons and staging absent with modem/rmtfs/dump state unchanged. A subsequent single fixed AP-local `wlan/fw` registry query returned the validated domain `msm/modem/wlan_pd`, instance 180, on Wayne's native QRTR stack; separate readback confirmed client/daemon/staging cleanup and unchanged OFFLINE/crash-count-2/rmtfs/dump state. This proves a live local locator exchange, not built-in ICNSS consumption or WLAN readiness. At that stage the services were not installed persistently and cold-boot consumption was unverified; the checkpoint below supersedes that status, without establishing a Wi-Fi fix.
- **Device-tested registry checkpoint (2026-11-20 UTC):** the S11 nameserver/S12 mapper pair was installed additively on SYSTEM and survived one watched reboot. Both services run under procd; the kernel reports `Service locator initialized` at **7.65 s**, and a fixed local query returns `wlan/fw -> msm/modem/wlan_pd`, instance 180. A subsequent manual modem start was ONLINE/crash 0 in fourteen five-second samples and later readbacks; the kernel connected to notification instance 180, IPA initialized and `rmnet_ipa0` existed. **This does not prove the cause of previous ERR_FATAL events:** an earlier pre-mapper window also had no fresh fatal, and there is no controlled A/B result. The 70-second watch was not an automatic modem shutdown. **Still open:** WLFW service 69 was not observed, there is no Wi-Fi PHY, no cellular bearer/IP/client internet is established, and userdata-backed persistence is unverified. Dump gates and `allow_boot` stayed 0; no boot/kernel/vendor/userdata/recovery write or provisioning change was performed by the rollout. Source, pinned mapper patch, offline tests and evidence limits are in `modem/registry/`. This checkpoint is not yet wired into the normal ROM assembler; experimental TFTP work is excluded.
- **Split-ROM handoff: VERIFIED ON DEVICE.** The `9d06ed8` boot image mounted `PARTNAME=system` (`/dev/mmcblk0p61`), executed PID 1, and reached OpenWrt's procd; SSH came up at `192.168.1.1`. This closes the PID-1 portion of M8-S3.
- **24.10 split ROM now built on request.** Baseline for the persistent ROM moves from 21.02.7 to ImmortalWrt 24.10.4 (armsr/armv8). `build-2410-split-rom.yml` reuses the device-proven kernel, assembles the 24.10.4 rootfs with `scripts/assemble-2410.py`, adds the persistent USB helper, stages modem/WLAN firmware, packs the corrected PID-1 bootstrap, and emits the same recovery-flashable `wayne-openwrt-rom.zip` layout (boot+system+installer). **Device-verified 2026-11-19:** the 24.10.4 ROM boots on Wayne (`r33602-e717d133ed6d`), SSH works on `192.168.1.1`, screen-off holds.
- **In-system OTA (`wayne-ota`) added.** The running system downloads a signed-by-checksum boot image and rootfs archive, verifies both, backs up the current boot, writes `PARTNAME=boot`, stages the archive under `/wayne-ota`, and reboots. The bootstrap then verifies the archive in RAM, keeps rollback copies of the previous tree and boot image, swaps the system tree, and drops to a rescue shell if verification fails. Only `boot` and `system` are ever written. `scripts/test-ota.sh` covers the valid, checksum-mismatch, and incomplete-archive paths.
- **Debug kernel lane.** `debug/icnss-verbose` branches off `adios-wayne` (which stays untouched) and enables `DEBUG_FS` + `ICNSS_DEBUG`; `build.yml` takes a `kernel_ref` input so instrumented kernels build without moving the stable branch.

- **Screen guard false failure: fixed in source.** The guard runs and the panel turns off, but BusyBox `printf '0\n' > brightness` performs two writes; sysfs rejects the second, so the helper logged `brightness write failed` every 20 s even though brightness 0 applied. On-device: `printf '0'` failed 0/10, newline-only failed 10/10, `echo 0` failed 0/20. `screen.sh` now uses single-write `echo` for brightness and framebuffer blank. A regression test fails on the old form and passes on the fix.
- **Screen-off is working**, but userdata persistence is still absent: the ROM rootfs has no `/etc/config/fstab`. Persistence remains the open M8-S4/M9 gate.
- **Registry-test safety boundary:** only temporary tmpfs/procd state was changed and then removed. No permanent service or boot link, partition write, boot-image change, reboot, radio-mode change, or SIM/provisioning operation was performed by these tests; the original read-only rmtfs and disabled dump settings were retained.

## Roadmap (interactive blueprint)

**Overall state:** M1–M7 closed; M8 active; M9 structure frozen but runtime handoff still pending.

```
YOU ARE HERE
    ▼
[M1✅][M2✅][M3✅][M4✅][M5✅][M6✅][M7✅][M8▶ ][M9★ ][FUT ]
 kernel  RAM   root  boot  SSH   host  dock✗ structure  ROM  mainline
                                                  = finish: v1.0
```

### ✅ Done

| # | Milestone | State |
|---|---|---|
| M1 | Kernel boots + serial console | 100% |
| M2 | Full userspace in RAM (switch_root → procd) | 100% |
| M3 | Persistent rootfs on eMMC p64 (v0.9.4, 2026-10-14) | 100% |
| M4 | Standalone boot, no PC (p58 flashed) | 100% |
| M5 | USB gadget ethernet + serial → SSH (v0.9.6, 2026-10-15) | 95% |
| M6 | USB OTG **host** mode — VBUS 5V + real device enumeration (2026-10-17) | 100% |
| M7 | Docker feasibility probe on 4.19 (v0.9.10, real device, 2026-10-17) | 100% — answer: **NO** |

- **M5:** ONE configfs gadget (`g1`) = ACM serial (`ttyGS0`↔`ttyACM0`) + RNDIS ethernet (`usb0`↔PC). DHCP + dropbear → `ssh root@192.168.42.1`. Dropbear duplicate-`Interface` bug fixed (normalize to single `usb0` each boot). *Closeout:* flash v0.9.6 installer-boot → zero-touch SSH; re-test on a good USB port (PC port 3-1.2 is a bad Acer hub, not the phone).

### 🔜 Next — structure-first execution

1. **Ship the split product shape, not another full-initramfs product image.** Keep the boot partition small: kernel plus static bootstrap only. Keep the complete OpenWrt rootfs in `system`.
2. **Make the bootstrap observable.** It must emit markers for gadget setup, partition discovery, ext4 mount, `/sbin/init` validation, and `switch_root`; on failure it must stop in a rescue loop instead of attempting a blind handoff.
3. **Deploy the CI-built ujail compatibility package in the next debug image.** Re-read the installed package version and `/sbin/ujail` hash, then verify that the `PR_CAPBSET_DROP(38)` loop is gone or reduced to a non-fatal compatibility message.
4. **Only then continue Wi-Fi bring-up in gates:** userspace startup → firmware/BDF discovery → ICNSS/QMI readiness → PHY registration → scan → AP/client test. An empty PHY is not declared fixed by installing a userspace package.
5. **Validate the recovery zip as a separate experiment:** extraction to `system`, boot image contents, mount/handoff markers, and rollback path. Do not use a successful recovery extraction as proof that the next boot reached OpenWrt.

#### Historical closeout notes

- **M6 — USB OTG host mode (pocket modem). ✅ CLOSED 2026-10-17.** dwc3 as HOST: tethered phone USB → Wayne WAN → NAT. **PROVEN:** PC unplugged → `reg75=enabled`, `extcon4 USB-HOST=1`, xHCI → hub (1a40:0801) → SanDisk Ultra (0781:5590) as `sda` with `sda1 sda2` FAT parsed + Logitech receiver as HID mouse. **ROOT CAUSE:** external VBUS (`VOLTAGE_NOW=5019531`) back-feeds the port; PM660 `BOOST_BACK_WA` (`wa_flags=0x72`) refuses to boost → `softstart TIMEOUT rc=-22` on all 4 currents. Unplug → first-try success. Kernel correct as-is (`mode_store` already sets `vbus_active=false` + ID-ground); v0.9.7 DT supply + v0.9.8 non-fatal were both required. **Rule: host mode is standalone-only** — PC console and source role cannot share the port. Remaining work is M6b (below), not the core. Historical investigation: Single UDC = device XOR host; tear the gadget down cleanly; NEVER unbind dwc3 (panics this kernel).
  - **Lever (found 2026-10-15):** `/sys/devices/platform/soc/a800000.ssusb/mode` = the role switch (`peripheral`|`host`). No `usb_role_switch` class on 4.19; extcon0..4 exist but are read-only notifications. PD phy extcon `USB=1` confirms cable presence.
  - **Test harness:** `scripts/m6-roleswitch.sh` — `status` (read-only), `host` (guarded flip + 60s auto-rollback), `hold` (300s window, continuous device logging; `HOLD_S=600` to extend), `peripheral` (manual early return). Must run **detached** (`>/dev/null 2>&1 &`) because the flip kills both SSH and the ttyGS0 console. Log → `/root/m6.log`.
  - **Shipped in the image (v0.9.9):** `build.yml` installs `scripts/m6-roleswitch.sh` → `/root/m6.sh` and `scripts/vbus-host-test.sh` → `/root/vbus-host-test.sh`; `overlay-installer/init` re-copies both every boot (idempotent, same as `screen.sh`). No more retyping the harness over a serial console after a reflash.
  - **VBUS / OTG power investigation (2026-10-16):** host mode comes up (xHCI bus1+bus2) but with a real device seated on an OTG hub the port shows ZERO enumeration - dmesg never sees a plug event. Evidence: `extcon3 (qpnp-smb2): USB=0 USB-HOST=0` while host is up (charger never notified of host role) and `regulator.75 smb2-vbus state=disabled` (port not sourcing 5V). `scripts/vbus-probe.sh` flips to host, dumps extcon/regulator/power_supply state, attempts `smb2-vbus` enable, auto-rolls back. Log -> `/root/vbus.log`. HARDENED v2 (2026-10-16): a host-mode dump can HANG on a sysfs read (port electrically dead to PC, dwc3 mid-transition); v1 hung, never rolled back, UDC left empty -> BOTH ssh and ttyGS0 dead -> reboot required. v2 adds an INDEPENDENT watchdog that forces peripheral at T+25s even if the main body hangs, drops `find /sys`, and bounds every sysfs read with `timeout`. RULE: never touch the USB cable during a host-mode test. LATEST (2026-10-16): `regulator.75/state` is 0444 -> NOT writable from userspace, root or not; the enable path must be in-kernel. A writable gate `/sys/module/policy_engine/parameters/pd_vbus_ctrl` (rw; `echo 1` accepted 0->1) was tested with `scripts/vbus-host-test.sh` (pd_vbus_ctrl=1 + host flip, logs extcon3/extcon4/regulator.75/BOOST_CURRENT every 5s for 120s, watchdog rollback) -- RESULT: it changed NOTHING. For 120s in host mode `extcon3 (qpnp-smb2)` stayed USB=0/USB-HOST=0, `regulator.75 smb2-vbus` stayed disabled, BOOST_CURRENT=0, and only the two root hubs appeared (no downstream device). So pd_vbus_ctrl is NOT the lever. ROOT CAUSE FOUND (source-verified in DevHamid/LKGeek_sdm660@build-all-rekernel): `dwc3_otg_start_host()` (drivers/usb/dwc3/dwc3-msm.c) raises the OTG 5V boost ONLY through `devm_regulator_get_optional(dev, "vbus_dwc3")` and then `regulator_enable()`; the stock `ssusb@a800000` DT node (sdm660-common.dtsi) declares `USB3_GDSC-supply` + `dpdm-supply` but NO `vbus_dwc3-supply`, so get_optional returns NULL and enable is silently skipped -> smb2-vbus never rises -> nothing enumerates. Android hides this because its userspace USB HAL enables smb2-vbus itself; OpenWrt has no such HAL. STATUS (v0.9.7 on-device, 2026-10-16): the DT fix landed but host mode REGRESSED -- dmesg shows `unable to enable vbus_reg` then `unable to start host`, and usb_devs was EMPTY the whole run (v0.9.6 at least brought up the xHCI root hubs). Reason: with the supply now valid, regulator_enable() actually runs; when the charger refuses it, dwc3_otg_start_host() returned BEFORE dwc3_host_init() -> no xHCI at all. v0.9.8 fixes this two ways (patches/dwc3-vbus-nonfatal.sh + patches/charger-vbus-diag.sh): (1) a VBUS failure is now NON-FATAL -- log rc, continue -> host mode always comes up (as in v0.9.6) and we finally SEE the charger rc; (2) smb-lib.c compiled out ALL its error logging (#ifdef DEBUG; the Makefile never defines it) -> unconditional pr_err at every enable-path branch (ENTER / votable NULL / OTG_CFG write fail / boost softstart TIMEOUT / EXIT FAILED rc=N). The `M6 diag ...` dmesg lines from the next flash pinpoint the exact failure. Next: rebuild+flash, seat an OTG device, read the `M6 diag` line, confirm reg75=enabled and a `1-1:` device appears.
  - **CORE PROVEN (2026-10-16, real device):** clean teardown → `mode=host` → xHCI up on BOTH buses (USB2 `1d6b:0002` + USB3 SuperSpeed `1d6b:0003`, 1 port each) → auto-rollback restores `mode=peripheral` + UDC bound, SSH/serial returned. Remaining: downstream device enumeration (needs a real USB device on OTG — PC is a host, invisible to host mode) and VBUS power if a bus-powered device stays dark.
  - *Done when:* a client gets internet THROUGH Wayne via NAT.
- **M7 — Docker feasibility probe on 4.19. ✅ ANSWERED 2026-10-17: `M7=NO`, and CONFIRMED BY COMPILE 2026-10-18.** MEMCG was re-tested properly in v0.9.11 (commit fe7bb8a, run 39044591879): the vendor kernel **does not compile** with it — `mm/vmscan.c:210,227,237,239,609,659,665: error: use of undeclared identifier 'shrinker_rwsem'` (10 errors, `make[2]: *** [mm/vmscan.o] Error 1` → `make[1]: *** [kernel/Makefile:1227: mm] Error 2`). The original bisect was misleading — it captured an interactive menuconfig session, not a compile — so this build is the first true proof. MEMCG reverted (15db500); the answer is final, not a to-do. (v0.9.10 `/root/m7.sh` on the real device; log `/root/m7.log`). ONE real blocker: `CONFIG_MEMCG` off — vendor `mm/` refused to compile with it (bisect f6613d1 → 3f840e6 kept the build green), so dockerd dies with "kernel does not support memory limit capabilities". Everything else Docker needs PASSED: overlayfs mount + copy-up write on the ext4 p64 rootfs, veth pair, bridge, MASQUERADE, net/mnt/pid/uts/ipc namespaces, and freezer/pids/devices controllers — proof the v0.9.10 fragment additions landed and run. Two of the probe's three `fatal`s decoded as false negatives: `memory cgroup mount failed` = same MEMCG root cause (double-counted); `unshare -n rejected` = busybox built WITHOUT the `unshare` applet (`rc=127`, not a kernel gap — `CONFIG_NET_NS=y` and the net namespace PASS). CEILING even after a MEMCG build = DEGRADED only: `CONFIG_SECCOMP` off (dockerd would need `--security-opt seccomp=unconfined`, no syscall sandbox) and LKGeek dropped `br_netfilter` (published-port DNAT across docker0 depends on the userland proxy). **DECISION (2026-10-17): accept NO — v1.0 runs services native (procd + Hermes), matching the Orange Pi reference minus Docker. Docker revisited on the mainline track.** Cheap prep whenever wanted: enable the busybox `unshare` applet (userspace-only, zero kernel risk).
  - **Kernel audit 2026-10-17 (v0.9.10).** The vendor defconfig already had `CGROUPS`, `CGROUP_SCHED`, `CGROUP_CPUACCT`, `NAMESPACES`, `NET_NS`, `OVERLAY_FS`, `BRIDGE`, `NF_NAT`, `NETFILTER_XT_TARGET_MASQUERADE`. Missing and now added to the fragment: `MEMCG`, `MEMCG_SWAP`, `CGROUP_DEVICE`, `CGROUP_FREEZER`, `CGROUP_PIDS`, `VETH`, `BRIDGE_NETFILTER`. Without `MEMCG` dockerd aborts with "kernel does not support memory limit capabilities"; without `VETH` containers get no network. `USER_NS` stays OFF (vendor default) — dockerd does not need it, only rootless mode does.
  - **Probe shipped (v0.9.10):** `scripts/m7-docker-probe.sh` → `/root/m7.sh`. One line: `sh /root/m7.sh`. It reads `/proc/cgroups`, mounts memory/freezer/pids/devices, opens a fresh net namespace (`unshare -n`), does a REAL overlay mount with copy-up write on the actual root filesystem, creates a veth pair + bridge, and pushes a MASQUERADE rule. Verdict line: `M7=YES` / `M7=DEGRADED` / `M7=NO`. Log: `/root/m7.log`. Read-only apart from temp objects it deletes; touches no USB, display or partition.
  - **Still unknown until booted:** whether `overlay2` works on this f2fs/ext4 rootfs, whether dockerd starts under 4.19 without a seccomp profile fight, and real memory headroom (3 GB RAM, OpenWrt base is ~50 MB). Those are answered by the probe, not by reading config.
- **M8 — Full OpenWrt experience on 21.02/24.10 (active, structure-first).** The RAM-only image is a test vehicle; the product is the split boot/system ROM.
  - **M8-S0 — Base runtime. ✅ Partially verified.** 24.10.4 boots to a shell and SSH. The existing screen guard was observed to turn the panel off. A manual modem start with the AP-side registry running was observed ONLINE/crash 0 during the recorded window; this does not establish the earlier crash cause or permanent stability. No Wi-Fi PHY has been observed.
  - **M8-S1 — ujail compatibility. ✅ CI / ⏳ device.** Run `44397558231` built `procd-ujail` from the pinned 24.10 SDK. The phone is still running the older image (`source_run=44151039361`, `procd` `42d39376-r1`), so the device result is pending a new image containing the package.
  - **M8-S2 — Split boot/system product structure. ▶ Current focus.** `boot.img` contains only the kernel and tiny static bootstrap; `system` is ext4 and receives `rootfs.tar.gz`; userdata carries persistent config/overlay selected by the rootfs fstab. No full OpenWrt rootfs is allowed in the product boot image.
  - **M8-S3 — Runtime handoff. ⏳ Pending.** Prove partition discovery, ext4 mount, `/sbin/init` presence, `switch_root`, and post-handoff SSH with serial markers. A completed recovery extraction is not sufficient evidence.
  - **M8-S4 — Wi-Fi. ⏳ Blocked at PHY detection.** After S1, test userspace startup → firmware/BDF requests → ICNSS/QMI readiness → PHY registration → scan → AP/client. The vendor qcacld/cfg80211 driver probing at kernel boot does not prove a registered radio.
  - **M8-S5 — Cellular data. ⏳ Pending.** Probe the Qualcomm IPC/QRTR path and data interface only after the modem ERR_FATAL/SSR behavior is isolated; no calibration/EFS writes.
  - **M8-S6 — Services and polish. ⏳ Pending.** LuCI, firewall/NAT zones, native services, feeds, and reboot-persistent configuration. Docker remains out of v1.0 because M7 is closed NO.
  *Done when:* the split ROM boots from the recovery-installed system rootfs, SSH and native services survive reboot, and Wi-Fi/modem are reported with separate verified YES/NO results.
- **M9★ — Polish + recovery-flashable ROM → v1.0.** The structure is agreed but not runtime-closed: recovery zip (`updater-script`/`update-binary`) installs the rootfs to **system** and writes the kernel + tiny bootstrap to **boot**; config/overlay persists on userdata via the rootfs fstab. *Done when:* the zip is verified, flashed from OrangeFox, the bootstrap mounts system and reaches OpenWrt, SSH works, rollback is documented, and the tag `v1.0` is published.

### 🔮 Future track (parked, post-v1.0)

**Mainline SDM660 (pmOS) + OpenWrt 25/newest.** Not abandoned — sequenced after the finish. Re-run the M1–M5 gauntlet as acceptance.

### 🧭 Guide rules

- Milestones gated (M6 needs M5 closed; M7 probe before any Docker promise).
- Every flash: rollback ready (`fastboot flash boot boot-backup.img`), OrangeFox on p59 intact, installer touches ONLY p64.
- Evidence over optimism: live sysfs + PC dmesg + CI gates, not assumptions.
- Release baseline: vendor Android 4.19 + ImmortalWrt 24.10.4. No mainline switch before v1.0.

### ⚠️ Top risks

1. **M6 single-port exclusivity** — gadget vs host can't coexist; design the switch deliberately.
2. ~~**M7 Docker-on-4.19 odds**~~ — ANSWERED 2026-10-17: NO (MEMCG + seccomp absent; everything else green). v1.0 already scoped native, so the schedule is untouched.
3. **Native radio bring-up** — an SSH boot or USB-tethered WAN is useful for debugging but does not satisfy the pocket-modem release gate. Prove native cellular WAN and Wi-Fi AP working together before tagging v1.0.

## How it works

```
┌────────────────────────────── boot.img ──────────────────────────────┐
│  kernel + DTB  │  tiny static bootstrap /init                        │
└──────────────────────────────────────────────────────────────────────┘
                 │ finds PARTNAME=system
                 ▼
┌──────────────────────────── system (ext4) ──────────────────────────┐
│  complete OpenWrt rootfs: /sbin/init, procd, services, firmware      │
└──────────────────────────────────────────────────────────────────────┘
                 │ mount userdata and apply the rootfs fstab policy
                 ▼
        bootstrap validates /sbin/init → switch_root → procd
```

The full-initramfs image follows the same userspace after unpacking, but it
does **not** exercise the product's system-partition handoff and is therefore
only a test/control image.

Two boot images are produced per build:

| Image | Contents | Purpose |
|---|---|---|
| `debug-boot.img` | kernel + tiny busybox shell (~1 MB ramdisk) | Proves the kernel itself boots on wayne. Dumps device tree, partitions, USB state to a serial console. |
| `openwrt-boot.img` | kernel + full OpenWrt rootfs in RAM | RAM-only control image. It does not test the system-partition mount or recovery installation path. |
| `donor-control.img` | PINNED donor kernel + PINNED donor Android ramdisk | **The control.** Known-good payload repacked through OUR packer. If this boots, our packer is fine; if it bootloops, our image assembly is the bug. |
| `bisect-kernel.img` | OUR kernel + DONOR's Android ramdisk | Splits kernel vs initramfs faults: boots Android → kernel fine; loops → kernel at fault. |
| `bisect-initramfs.img` | DONOR kernel + OUR debug initramfs | Splits the other way: loops → initramfs at fault; stuck-on-logo → PID 1 alive but invisible. |
| `installer-boot.img` | kernel + installer ramdisk | Legacy/test installer path. It is not the v1.0 product path and must not be confused with the recovery zip. |
| `rom-boot.img` | kernel + tiny system-bootstrap ramdisk | **The ROM's product boot image.** Bootstrap mounts `PARTNAME=system` as ext4, validates `/sbin/init`, and `switch_root`s into the installed OpenWrt. No `root=` on the cmdline. |

**Release artifact: `wayne-openwrt-rom.zip`** — the TWRP/OrangeFox flashable ROM (M9 structure): `boot/boot.img` = `rom-boot.img`, `system/rootfs.tar.gz` = the OpenWrt rootfs, and `META-INF` `update-binary` formats/extracts `system` and writes `boot.img`. Built by CI on every run and attached to tag releases. The recovery log and first-boot serial markers are required to close the handoff gate.

## Boot failure troubleshooting

This kernel has no framebuffer console (`CONFIG_VT=n`), so a working boot can look like "stuck on Mi logo". Distinguish failure modes:

| Symptom | Meaning | Next step |
|---|---|---|
| Bootloop (logo reappears) | Reset observed — kernel panic, watchdog, or bootloader rejection. NOT proven to be a panic. | Try the donor-control image |
| No host `/dev/ttyACM0` at 30 seconds | Inconclusive. Bootstrap may wait up to 60 seconds for a UDC; absence does not prove kernel death or failed rootfs handoff. | Capture from power-on through startup; use kernel/serial logs if available |
| `openwrt-boot.img` fails | Does not exercise the system-partition rootfs install/mount path | Diagnose its kernel + initramfs independently |

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

## First install (recovery required)

The **first** installation of a new baseline must be via OrangeFox recovery flash:
push the latest `wayne-openwrt-rom.zip` to the device and install it in recovery.
This establishes the boot image and the system rootfs together. No OTA exists for
this initial bootstrap.

## OTA updates (after baseline installed)

Once a baseline is installed, subsequent ROMs can be applied OTA without recovery:

```sh
wget -O /tmp/MANIFEST https://github.com/DevHamid/wayne-openwrt/releases/download/<tag>/MANIFEST
wayne-ota /tmp/MANIFEST
```

`wayne-ota` stages the update and reboots; the bootstrap installs it before the
normal handoff. Guarantees and limits:

- Writes only `PARTNAME=boot` and `PARTNAME=system` (staging lives in `/wayne-ota` on system).
- Verifies both SHA-256 hashes and the archive's required entries before touching anything.
- Keeps `boot.prev` and a compressed copy of the current rootfs in RAM; if the new tree fails verification the old tree and boot image are restored and the bootstrap drops to a rescue shell.
- A staged-but-unverified update leaves the old system intact; only a verified update is applied.
- `MANIFEST` is generated by `scripts/make-manifest.sh <version> <tag> <boot.img> <rootfs.tar.gz>`.
- Offline install: the manifest argument also accepts `file:///path` or a bare absolute path, so a manifest + payload pushed over the USB link can be installed with no upstream network on the phone.

### Prerequisites for OTA

1. The baseline must already be installed (recovery flash step above).
2. Each release publishes: `wayne-openwrt-rom.zip`, `rom-boot.img`, `MANIFEST`, `rootfs.tar.gz`.
3. The `wayne-ota` binary on-device must support `file://` URLs (added in commit 2c7ac8c). Check with:
   ```sh
   grep -q 'file://' /usr/sbin/wayne-ota && echo ok || echo needs-update
   ```
   If it reports needs-update, flash the latest recovery ROM to get the updated binary.

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

**Knowledge Notes:** plain-language + technical explainers of the build live in `docs/knowledge-notes/` (mirrored to the Telegram group topic). They exist so the journey is readable over morning coffee, not only as diffs.
### Screen / burn-in protection (userspace, no kernel change)
Vendor kernel already ships the display stack (`CONFIG_FB_MSM_MDSS=y`,
`CONFIG_BACKLIGHT_QCOM_SPMI_WLED=y`). Userspace control:
- panel: `/sys/class/graphics/fb0/blank` (0=on, 1=blank, 4=power-down). `fb1`/`fb2`
  are MDSS **writeback** outputs, not the panel — use `fb0`. NOTE: on this vendor
  kernel `fb0/blank` READS BACK EMPTY (4096 B, writable, show() is a stub) and
  the bootloader runs `Continuous splash enabled`, so the DSI path is bootloader-
  owned at handoff. Backlight is therefore the reliable actuator: brightness 0
  is what actually darkens the panel.
- backlight: **`/sys/class/backlight/backlight/brightness`** (type=raw,
  0..`max_brightness`=4095). NOT `/sys/class/leds/lcd-backlight/` — that node
  exists and accepts writes with clean readback, but it is a STUB: the panel
  never changes. Found 2026-10-17 (screen stayed lit at brightness=0);
  verified `/sys/class/backlight/backlight/` drives the real WLED string
  (echo 0 -> dark, echo 4095 -> lit). `screen.sh` now auto-detects the first
  writable `/sys/class/backlight/*` and only falls back to the LED path.
- build-time auto-guard: `overlay-openwrt/etc/init.d/burnin-guard` (START=99) runs
  `screen.sh guard 90` at every boot, so the panel goes dark 90s after boot and
  STAYS dark (no more lit logo burning in). The build now installs
  `/root/screen.sh` + the init script into the image itself (v0.9.7) - earlier
  builds shipped them only in the repo, so nothing auto-ran and offdelay had to
  be primed by a manual off/on first. `guard` re-asserts the blank every 20s,
  winning the race against the panel driver coming up late. Override:
  `/etc/init.d/burnin-guard stop`, or `sh /root/screen.sh on` (kills the loop
  instantly). Will be replaced by the M8 on-panel stats display later.
- helper: `scripts/screen.sh` — `status` | `off` | `on` | `set <n>` |
  `offdelay [s]` (one-shot) | `guard [s] [r]` (off after s, re-assert every r;
  DEFAULT at boot) | `toggle [s]` | `stop`. Detached-safe:
  `sh screen.sh guard 90 20 >/dev/null 2>&1 &`.
  Kill-path bug fixed (2026-10-16): the daemons trap HUP/INT/TERM to survive a
  closed session, so the old `kill` (SIGTERM) was IGNORED - the guard kept
  re-blanking right after a manual `on`. That is the real cause of "offdelay
  only works after I run status/off/on first". kill_prev now uses SIGKILL with
  a cmdline check (pid-reuse safe), so `on`/`stop` always win.
  Second bug (v0.9.7): the daemons wrote `$$` (the parent pid, already dead)
  to the pidfile instead of `$!` (the real backgrounded subshell), so the
  daemon could never be killed and `status` lied. Fixed in all three modes.
  v0.9.8: burnin-guard now runs the guard under PROCD (`USE_PROCD=1`,
  `screen.sh guardfg 90`, respawn) instead of backgrounding it from start()
  -- procd reaped the backgrounded child, so the screen never went off.
  `on` now drops a VETO flag (/tmp/.screen.on, tmpfs = cleared by reboot)
  that the guard honours, so a manual `on` STAYS on; `off`/`guard`/`stop`
  clear it.
  v0.9.9: the guard DID run and DID set brightness 0, yet the panel stayed lit —
  because it was writing the stub LED node. Backlight target corrected to
  `/sys/class/backlight/*` (auto-detect); this is the actual fix for "screen
  doesn't turn off automatically".
- later (M8): a console on fb0 (`/dev/tty1` + `con2fbmap`) can show uptime / net /
  IP stats on the panel.


