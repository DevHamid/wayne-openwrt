# Modem-side eloader initialization: concrete static reference

## Measured offline, not a device execution trace

The prior investigation identified image/path strings but had not named their
initialization entry. A bounded read of the saved modem image now links the
WLAN setup routine to an **`eloader_init`-named descriptor**. This is a new
static lead; it does not show whether the routine ran on Wayne.

Exact saved inputs (SHA-256):

- `MODEM.MDT`, 8412 bytes:
  `19f5741aef481cea4d7dd07c813dc3a983ef7efea34d41bd29beba169240a8a8`
- `MODEM.B17`, 13710353 bytes:
  `bed0cf45000908a71cb5fbbf1a7d37b8020634450e026d60b781a151951907e4`
- `WLANMDSP.MBN`, 3717208 bytes:
  `f77e315414f47a421c6020800a9f54d29f68971998b938243bd5f5f337549f50`

These are the saved AP files, not processor-memory readback. Their earlier
on-device file comparison is recorded in [RX-OBSERVATION.md](RX-OBSERVATION.md).
Firmware bytes remain private and are not included in this checkpoint.

## Descriptor and reachable code

Map ELF32 little-endian `MODEM.MDT` PT_LOAD virtual addresses to the matching
`MODEM.Bnn` segment contents before interpreting pointers. At virtual address
`0xc226fe20`, the descriptor contains:

- `+0x00 = 0xc226d170`, which points to the string `eloader_init`.
- `+0x0c = 0xc1916b90`, a code pointer into the WLAN setup routine.
- `+0x24 = 0xc226fe10`; that pointed-to list begins with a pointer to
  `default` and a terminating zero.
- `+0x28 = 0xc226fe18`; that list begins with a pointer to `servreg` and a
  terminating zero.

References to the descriptor address `0xc226fe20` occur at `0xc2276304`
(segment 17) and `0xc3755814` (segment 18). The association is observed data;
interpreting the lists as particular RCINIT policy/dependency fields requires
matching the structure/consumer. No execution order is inferred here.

LLVM's Hexagon-v60 disassembler shows the routine at `0xc1916b90` setting up
these strings in its context:

- `0xc2277080`: `msm/modem/wlan_pd`.
- `0xc22770a0`: `wlan_process`.
- `0xc22770b0`: `wlanmdsp.mbn`.

After allocating/building the default and vendor firmware paths, instruction
packet `0xc1916c24` calls `0xc19165d0` with that context. Null-allocation paths
return without reaching it. The callee contains further checks and thread/event
setup; those conditions are not yet explained as a working runtime sequence.

## What this changes

The modem image has a named initialization entry leading to the WLAN loader;
we should not assert that an AP cold-start command is necessarily missing
simply because no firmware request appeared. Conversely, a descriptor in the
image is not proof it was selected or executed. The live listener result
UNINIT does not by itself distinguish skipped initialization, waiting on a
prerequisite, loader failure, or a different notifier object/state.

Next discriminating source work is to resolve the descriptor's consumer and
the loader's early predicates, then compare those with a working Android
reference. Do not invent an AP QMI request, power-cycle, change DIAG masks or
flash a kernel on the strength of these static pointers.

## Scope and verification

This checkpoint was source-checked by the parent only. The requested independent
review did not execute because its model provider timed out; it is not an
independently reviewed or merge-approved fix.

This inspection used the saved files and host LLVM only. It built no kernel,
opened no phone DIAG connection and sent no modem QMI message. The existing
22 packet/parser/same-socket transport tests were rerun and passed; they
validate the diagnostic helper, not execution of modem `eloader_init`.

Fresh read-only discovery independently reproduced 66 endpoint rows (40 node
0, 26 node 1), locator 64 and notifier 66 present, WLFW 69 absent, and no PHY.
Modem stayed ONLINE / crash count 0 with the original read-only UIO-backed
rmtfs; automatic boot and both dump gates stayed 0. No new modem acquisition,
restart, persistent phone write or flash was performed in this audit.
