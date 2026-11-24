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
| Wi-Fi (the phone's own radio) | 🟡 Firmware staged, bring-up in progress |
| Automatic OTA updates | 🟡 Pipeline ready |

**The headline:** the phone's modem used to crash every ~30 seconds. We found the exact cause
(the modem's diagnostic stream had no reader on the OpenWrt side, so the modem choked on its own
backlog) and fixed it. The modem now runs **stable for hours**, and it **registers on the cellular
network** — the hard part is behind us.

---

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

1. **Install the new ROM** (ModemManager + modem web page + Wi-Fi firmware) and verify it boots.
2. **Turn on the LTE data connection** and run a small real-traffic test.
3. **Bring up Wi-Fi** so the phone shares that connection.
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
