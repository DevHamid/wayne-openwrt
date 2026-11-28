# Wayne Pocket Modem — Progress

**Project:** turn an old Xiaomi Mi 6X phone into a **pocket LTE modem + Wi-Fi router** running OpenWrt.
This page is the plain-English progress report. The technical details live in the [main README](README.md).

---

## ✅ What works right now

| Area | Status |
|---|---|
| OpenWrt boots on the phone | ✅ Working — **clean recovery flash validated** |
| Remote access (SSH over the USB cable) | ✅ Working, reliable |
| **Phone modem stays alive** (no more crash loop) | ✅ **Fixed and verified** |
| **Modem registered on the cellular network** | 🟡 **Blocked — signal appears but stuck "searching"** |
| **LTE data connection (internet over the modem)** | 🚧 **Blocked — needs a kernel fix + ROM rebuild** |
| Full low-level modem control (QMI) from OpenWrt | ✅ Working |
| Serial debug console over the same USB cable | ✅ Working |
| ModemManager (the standard Linux modem service) | 🟡 Built into the ROM; pairs control side, blocked on data side |
| Wi-Fi (the phone's own radio) | 🔧 Blocked — kernel loads the Wi-Fi driver too early; corrected build running |
| Automatic OTA updates | 🟠 **Restricted — only within an already-installed baseline** |

**The headline:** the flashable ROM now **installs cleanly from recovery and boots** — that is the
validated baseline. The modem's data connection is still blocked, and we now know *exactly* why: the
modem's data port is set up in a way the standard Linux software refuses to touch, and the fix has to
happen in the phone's low-level kernel (a rebuilt image), not in a settings file. Separately, even the
modem's *registration* now needs attention — it finds signal but can't finish connecting to the network.

---

## 🆕 Latest update (Nov 28, later) — the ROM installs cleanly, and we know exactly what's blocking the modem

**The good news first: the flashable image now installs the right way and boots.** We put it on the
phone through its recovery mode (the same way you'd install a custom system on any old Android phone)
and it came up cleanly — the router system started, and we could reach it over the USB cable. That
clean install is now our **reference baseline**: it's the known-good starting point for everything else.

**We also cleared up an old misunderstanding.** For a while we thought a certain combination of
phone software and router version caused the phone to hang on startup. It didn't. The hangs happened
because our **over-the-air updater was layering a new system on top of a *different* one**, leaving a
half-and-half mix that couldn't boot. That's an updater bug, not a compatibility wall. The rule now:
the first install of a new baseline always goes through recovery; the over-the-air updater is only for
updating a phone that already runs that same baseline.

**On the modem's data connection, we now have the complete answer — and it's a harder one.** The
standard Linux modem software still won't set up the modem's data side (the part that carries internet
traffic). We traced every escape route and each one is closed:

- The modem's data port is created in a way Linux treats as a **"phantom" network device with no real
  hardware behind it**, and the software **refuses to use phantom devices** on principle.
- Normally a set of helper rules would tag the port as real, but **those helpers aren't installed** on
  the phone, so the tagging never happens.
- The software's own manual-reporting tool **can't carry the needed label** (it only accepts a short
  list of fields), and **no settings flag can override** the phantom-device refusal.

**What this means:** the fix isn't a settings tweak or a config file — the modem's data port has to be
set up properly at the **low-level kernel** layer, which means **building a new flashable image**.
That's more work than we'd hoped, but it's a known, buildable path rather than a mystery.

**One more thing to solve: the modem isn't finishing its connection to the network.** The modem's
control side was stuck shutting down; when we forced it awake, it found a **cell signal** but then sat
**"searching"** without ever connecting, and the SIM never finished activating. So registration is now
its own blocker, separate from the data-port issue above. We're tracking both.

**Honest status:** the clean-install baseline is **proven on the real phone**. The data-port root cause
is **fully diagnosed** but the fix is **not built yet** (it needs a kernel change and a rebuild). The
registration problem is **reproduced and measured** but **not yet solved**.

---

## 🆕 Latest update (Nov 28) — we found and fixed the thing blocking the LTE data connection

**Where we are:** the phone's modem already boots, stays stable, and registers on the cellular network.
The one thing left before it works as a real pocket modem is the **LTE data connection** — the link that
carries actual traffic. We've been stuck on that, and this week we finally found *why*.

**What was wrong:** the standard Linux modem software (ModemManager) couldn't finish setting up the
modem because it never saw the modem's **data port** — the piece that carries internet traffic.
It kept saying "can't find a data port" and gave up.

**The surprising cause:** it wasn't the modem, and it wasn't the kernel. It was a safety filter inside
the standard Linux software itself. That filter is meant to ignore ordinary network "noise" that this
kind of phone doesn't use — but the modem's real data port looked enough like that noise that the
software **silently threw it away** before the modem ever got a chance to use it.

**The fix:** we taught the software to recognize this phone's modem data port and let it through.
The change is now part of how the flashable image is built, so every future build includes it.

**What this means:** if it holds up on the phone, the modem software should finally pair the modem's
control and data sides together — the step it's been failing — and the SIM's identity and the LTE
link can come up. That's the difference between "modem registered" and "modem works as a hotspot."

**Honest status:** the fix is written, built into the image recipe, and **verified against a test copy**
of the software's config. It is **not yet confirmed on the real phone** — the phone wasn't reachable
during this session. The moment it's plugged in, the test is simple: does the modem software now show
a modem object, does the SIM finish activating, and does the data link come up. We'll report the result
either way.

---

## 🆕 Latest update (Nov 27, latest) — the modem's diagnostic-drain service is now actually running

The modem-crash fix had one loose end. We'd written a small service (`wayne-diagd`) whose whole job is
to keep the modem's diagnostic stream drained so the modem never chokes on it — but when we checked
the running phone, that service **wasn't actually on the device**. It had been written and built, but
the build recipe that produces the flashable ROM never included it, so the phone silently fell back to
a simpler method that can't work on this hardware.

**We found two problems and fixed both:**
- **The service was never packaged into the ROM.** The ROM-building recipe skipped the step that
  compiles it. Now that step runs before the ROM is assembled, so the service ships every time.
- **Even if it had shipped, it would have failed to start.** The service has to perform a short
  "handshake" with the modem's diagnostic hardware before it can read from it. Our first version sent
  the wrong settings, which the hardware rejects. We corrected the settings to match what the hardware
  requires.

**Proven on the real phone:** we published the fixed ROM, the phone fetched it over the air and
rebooted into it. The diagnostic-drain service is now confirmed **running** (the system reports it as
up, and it's the real service, not the broken fallback). The phone has stayed up **19+ minutes with
zero crash or starvation events** — the failure mode that used to appear within ~5 minutes is gone.

---


## 🆕 Latest update (Nov 27, later #2) — two root causes found

We probed the phone again while it was running (it stayed up 14+ minutes this time). Two clear findings:

- **The diagnostic-drain service is written wrong.** It uses a simple `cat` to read the modem's
  diagnostic stream, but that stream needs a proper "handshake" before it will talk. Without the
  handshake the read fails (`Bad address`), so the service never actually drains anything. The good
  news: the fix is to make the drain do the handshake the way our existing modem tool already knows
  how — a small, contained change. (It hasn't caused a crash yet, but it's a landmine, so we'll fix it.)
- **The modem hardware is fine — the software just isn't wiring it up.** On this boot the modem's
  power-up, its firmware loading, and its internal driver all completed successfully. But the phone
  still reported "no modem found." That pins the problem squarely on the connection-manager support
  we already knew was missing (it doesn't know how to talk to this modem's network hardware), not on
  broken hardware. That's the next thing to fix.

We also learned the phone is now reached over the USB network link (SSH), since a normal OpenWrt boot
has no adb — one of our automated checks mistakenly thought the phone was offline for that reason.

---

## 🆕 Latest update (Nov 27, later) — the boot/reconnect bug is FIXED

**We broke through the biggest day-to-day blocker.** Every time we flashed a new build, the phone
would come back up but the USB connection would be dead — no SSH, no serial console, and we'd have to
power-cycle into recovery to reach it again. That made every test slow and risky.

**We found why, and fixed it.** During startup the phone was setting up its USB connection in the
background, and the moment it switched to the main system that background job got cut off halfway.
The fix: set up the USB connection in the foreground so it finishes before the handover.

**Proven on the real phone:** we flashed the fixed build from recovery and it came back up clean —
SSH over the USB cable connected within 90 seconds, and it stayed up for 8+ minutes (the old builds
died at ~90 seconds). No power-cycle needed between flashes any more. This makes every future test
faster and safer.

**Still on the to-do list (separate items, not new problems):**
- **Wi-Fi** still blocked — the phone's Wi-Fi driver is built into the kernel instead of loading
  separately; needs the corrected kernel build (tracked on the board).
- **Cellular data** still blocked — the phone's modem isn't creating the network device the
  connection manager needs (tracked on the board).
- One housekeeping item: the small service that keeps the modem's diagnostic stream drained isn't
  starting cleanly. It isn't causing crashes right now, but we'll tidy it up.

---

## 🆕 Latest update (Nov 27, earlier) — device in recovery, bootloop/USB picocom/SSH pending, WLAN module pending

- **Phone in OrangeFox recovery** — device was wedged after the last flash; no booted OpenWrt system. SSH/picocom unavailable. User must re-seat USB cable and, if screen dark, hold Power to restart into recovery.
- **Bootloop / USB picocom / SSH issue FIXED** — root cause: /init ran gadget builder in background subshell; switch_root killed incomplete build. Fix (commit 8b2db33): run usb_gadget_up foreground so builder completes before switch_root. CI build 45970126301 in progress.
- **WLAN status:** qcacld built into vmlinux (=y) on the locked v2 baseline; wlan.ko never loads due to duplicate symbol "__qdf_defer_func". The corrected kernel `debug/wayne-wlan-sfr-v2` (CONFIG_QCA_CLD_WLAN=m) is ready in CI run 45796829337 but not yet flashed. Wi-Fi pending that flash + modem data-call unblock (t_7236fbfd).
- **Modem:** Registered (CS=PS=serving), SIM readable. ModemManager in ROM, LuCI page present. Data-call blocked by MM `qcom-soc` plugin: `Failed to find a net port in the QMI modem` — no IPA netdev support, rmnet_ipa0 has no parent QMI device. Next: patch plugin or replicate DPM open from tools/wayne-data.c.
- **Progress:** Build 45885729188 green; release m9-2410-complete-87ef463 published; device in recovery awaiting user re-plug. Board review complete: t_31b6f242 (bootloop investigation, priority 40, ready), t_922f2215 (wifi module registration, ready), t_7236fbfd (modem data call, blocked on IPA netdev), t_ab8e0a26 + t_8d35d152 (WebUI, gated on modem data).
## 🆕 Latest update (Nov 26) — why Wi-Fi still refuses, and the real fix

**Status: corrected CI build completed.** Build `45885729188` finished successfully, using
`kernel_ref=debug/wayne-wlan-sfr-v2` (tip `f997eb3`). All artifacts built: wayne-openwrt-2410,
wayne-openwrt-2305, wayne-openwrt. The 2410 rootfs now ships wlan.ko as a loadable module
(CONFIG_QCA_CLD_WLAN=m). Watch it at
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

1. **Get the modem to finish registering** — it finds a cell signal but stays stuck "searching" and
   the SIM never finishes activating. This is now the **first gate**: nothing else on the modem works
   until it actually connects to the network.
2. **Unblock the LTE data connection (kernel fix + rebuilt image)** — set the modem's data port up
   properly at the low-level kernel layer so the standard software stops refusing it, then rebuild and
   reflash. Once registered, this is what turns the phone into a real hotspot.
3. **Get Wi-Fi up** — flash the corrected kernel so the Wi-Fi driver loads at the right time and a
   Wi-Fi interface appears.
4. **Add the dashboard** — a page to see signal, data usage and control the link, once there is a
   working connection behind it.
5. **Polish**: kernel tuning, and the automatic update pipeline (kept to same-baseline updates only).

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
