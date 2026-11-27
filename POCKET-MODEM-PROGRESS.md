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

## Next step

Decode how ModemManager admits that interface, author the one-line fix, then
build the swappable package (operator run) and verify the data call comes up.
