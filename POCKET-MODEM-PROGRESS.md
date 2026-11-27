# Wayne as a Pocket Modem — Progress

Plain-language status of the "phone as a pocket modem" goal: plug the phone in
over USB, get an LTE data connection on your laptop, managed through
`mmcli`/LuCI — no special apps.

## Where we are

**The modem's control channel works.** ModemManager now sees the modem, builds
its internal control port, and can enumerate every service the modem offers.
That is the hard half, and it is verified on the device.

**What still blocks the data connection:** ModemManager builds the modem, then
throws it away because it cannot find the *network* port that carries the
actual traffic. The interface exists (`rmnet_ipa0`), but it is registered in a
way (no parent device, no driver string) that ModemManager's matching code
does not recognise — so it never grabs it as the data port.

## The fix (planned)

Teach ModemManager to recognise that interface by name rather than by its
missing driver. Small, targeted, and ships as a normal swappable package —
**no kernel rebuild, fully reversible.**

## What is verified on hardware

- The modem enumerates fully: all its services are live and visible.
- The control channel is built and working.
- The only blocker is pairing the data port, one layer we have now pinned.

## Update — the blocker was the radio power state (fixed)

The cellular data call was stuck because the **radio was in a `shutting-down`
power state** — it was turning itself off. That one state caused every symptom:
not-registered, no bearer, no data port, "no modems found."

**Fixed:** the radio was powered back on and now shows **real signal
(-92 dBm GSM)**. Antenna and modem hardware are fine. The SIM is in and
readable.

**The one link still remaining:** the radio has signal but has not yet
*attached to the network* (it keeps "searching"). With good signal and a
present SIM that keeps searching, the likely cause is **the SIM not being
activated on a service plan** — a carrier-side step, not a software fix.

**Validated on hardware:** the data interface (`rmnet_ipa0`) is present but
registered in a way ModemManager's matching code does not recognise — the
finding the planned fix targets is now **confirmed on the real device**, not
just in theory.

## Next step

Decode how ModemManager admits that interface, author the one-line fix, then
build the swappable package (operator run) and verify the data call comes up.
