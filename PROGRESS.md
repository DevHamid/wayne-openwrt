# Wayne Pocket Modem — Progress

**Project:** turn an old Xiaomi Mi 6X phone into a **pocket LTE modem + Wi-Fi router** running OpenWrt.
This page is the plain-English progress report. The technical details live in the [main README](README.md).

---

## ✅ What works right now

| Area | Status |
|---|---|
| OpenWrt boots on the phone | ✅ Working |
| Remote access (SSH over the USB cable) | ✅ Working, reliable |
| **Phone modem stays alive** (no more crash loop) | ✅ **Fixed and verified** |
| **Modem registered on the cellular network** | ✅ Working |
| Full low-level modem control (QMI) from OpenWrt | ✅ Working |
| Serial debug console over the same USB cable | ✅ Working |
| ModemManager (the standard Linux modem service) | 🟡 Built into the ROM, being tested |
| Wi-Fi (the phone's own radio) | 🔧 Blocked — kernel loads the Wi-Fi driver too early; corrected build running |
| Automatic OTA updates | 🟡 Pipeline ready |

**The headline:** the phone's modem used to crash every ~30 seconds. We found the exact cause
(the modem's diagnostic stream had no reader on the OpenWrt side, so the modem choked on its own
backlog) and fixed it. The modem now runs **stable for hours**, and it **registers on the cellular
network** — the hardest modem work is behind us.

---

## 🆕 Latest update (Nov 26) — why Wi-Fi still refuses, and the real fix

**Status: corrected CI build dispatched.** Build `45885729188` is running now, using
`kernel_ref=debug/wayne-wlan-sfr-v2` (tip `f997eb3`). Watch it at
https://github.com/DevHamid/wayne-openwrt/actions/runs/45885729188.

**Important distinction:** run `45796829337` did build `debug/wayne-wlan-sfr-v2` and produced
`wlan.ko` as a module — but that was a test build, not the ROM that ships. The ROM that ships
came from run `45857710376`, which used `fix/ipa-ssr-race-20261126` (card #2) instead of
`debug/wayne-wlan-sfr-v2` (card #1). So the published ROM still has qcacld built-in (`=y`) and
wlan.ko can never load. Build `45885729188` is the one that should ship the module-based ROM.

For a while we believed Wi-Fi was stuck in the modem firmware: the theory was that the phone never
handed the Wi-Fi service over to the system, and that a timing fix would unlock it.

To settle it we built a **diagnostic kernel that logs every step of that handover** and ran it on the
phone. The result closed the question: **the handover is perfect.** Modem boots, the Wi-Fi service is
announced, and every stage of the handshake completes cleanly. Nothing in the radio chain is broken.

The actual cause is a build mistake, and a simple one:

- The Wi-Fi driver was compiled **into** the kernel instead of being built as a separate loadable
  piece. So it starts about **half a second after boot** — long before the modem wakes up at ~51 s —
  asks for hardware that is not there yet, gives up, and never tries again.
- The separate driver file shipped in the ROM is then refused by the kernel, because the kernel
  already contains an identical copy of it. Two copies of the same driver cannot coexist.

The fix is to rebuild from the branch that was always meant to ship it as a loadable module — the
one that also carries the modem stability fixes. **That build is running now.** If it behaves, Wi-Fi
should appear for the first time.

**What this means:** the scary theory (broken firmware, broken modem) is off the table. What is left
is ordinary engineering.

---

## 🆕 Latest update (late Nov 24, #2)

- The corrected ROM is **built, verified and published** (release
  `m9-2410-modemmanager-48e7bbc`, build 45505540500): ModemManager + modem web page +
  the modem-stability fix, with a new CI check that **fails the build** if the fix isn't
  enabled in the packaged image.
- A real device lesson from today's install: a freshly installed image had the fix *present*
  but not *enabled* (a missing boot symlink), which kept the modem from staying up. Caught,
  root-caused and fixed at the build level — plus a one-line on-device fix for the current unit.
- The test phone is currently unresponsive (a previous install wedged it; it's in a state where
  only a power cycle/recovery brings it back). The user has been pinged; the moment it's back,
  the verified installer runs automatically from the bridge.

## 🆕 Latest update (late Nov 24)

- The modem software suite (**ModemManager** + a modem page in the router web UI) is **built into
  the ROM** and published as a release.
- Installing it on the test phone taught us two things, both now fixed:
  1. The phone runs OpenWrt **directly from the same flash partition the ROM installs to**, so the
     installer was rewritten to upgrade "in place" instead of wiping the running system.
  2. The modem-stability fix almost didn't make it into the packaged ROM — now the build
     **fails on purpose** if that piece is missing, so it can never happen again.
- The first in-place upgrade is applied and verified on the flash, but the phone hasn't come back
  on its USB link yet after the switch — recovery is automated and will finish the job as soon as
  the phone reappears (a power cycle works too).

## 🔧 What we did to get here

1. **Made the phone reachable** — a reliable network link over the USB cable, plus a serial console.
2. **Stopped the modem crash loop** — the modem's diagnostic log stream needs something on the
   OpenWrt side reading it continuously. We added that tiny reader as a boot service.
3. **Proved the kernel was never the problem** — we compared a working phone and the broken one
   side by side (kernel config, threads, device tree): identical. The difference was the software
   *around* the modem.
4. **Got full modem control** — we can now talk to the modem directly (signal, registration, SIM,
   capabilities) from OpenWrt.
5. **Chose the modem software stack** — ModemManager with its `qcom-soc` plugin, which is made
   exactly for built-in Qualcomm modems like this one, and is already packaged for OpenWrt.

---

## 🔜 What's next

1. **Get Wi-Fi up** — flash the corrected kernel, confirm a Wi-Fi interface appears. This is the
   current blocker and the whole point of the next device session.
2. **Turn on the LTE data connection** — make the connection manager see the modem's data port,
   then run a small real-traffic test.
3. **Add the dashboard** — a page to see signal, data usage and control the link, once there is a
   working connection behind it.
4. **Polish**: Docker support, kernel tuning, and the automatic update pipeline.

---

## 📦 Try it / flash it

- **Builds:** GitHub Actions builds the kernel and the ROM automatically on every push.
- **Install:** put `wayne-openwrt-rom.zip` on the phone in recovery mode (TWRP/OrangeFox) and install
  it — it writes the boot partition and the OpenWrt system partition.
- **Safety:** the phone's IMEI, modem calibration and SIM data partitions are never touched.

---

## 🧭 Where the work is tracked

- Technical details, build steps and troubleshooting: [README.md](README.md)
- Board state and open items: the project Kanban board
- This progress page is regenerated/updated as milestones land.
