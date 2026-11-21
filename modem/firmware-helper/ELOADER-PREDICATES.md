# WLAN loader: boot-table consumer and early predicates

## Scope

Offline inspection of the exact saved firmware inputs hashed in
[ELOADER-INIT.md](ELOADER-INIT.md), plus native **no-socket map validation** of
already-installed files. No modem acquisition, restart, radio-mode change,
DIAG operation, protected-partition content read, persistent phone write or
kernel build was performed by this investigation. No WLAN fix is claimed.

## 1. The descriptor is in an initialization group, not only a name index

The earlier descriptor reference at `0xc2276304` belongs to a name/descriptor
pair table: the preceding word points to `eloader_init`. The other reference,
`0xc3755814`, belongs to a null-terminated list of descriptors.

Following that list upward gives:

- Table root `0xc3755108[0]` points to `0xc37550b8`.
- Slot 7 of `0xc37550b8` points to list `0xc3755810`.
- Entry 1 of that list is descriptor `0xc226fe20` (`eloader_init`).
- The descriptor's low byte at `+8` is 7; the next byte is 2. Its entry pointer
  at `+12` is `0xc1916b90`, signed 16-bit priority at `+16` is -2, and its
  `+24` and `+44` words are zero in the saved image.

The list has 22 entries before its terminator. Across all eight lists under
this first table root, the descriptor low byte agrees with its list index.
That cross-check supports the group interpretation independently of a guessed
C structure. A second top-level table exists; its selection at runtime is
not established here. Unbacked/BSS addresses are not read as saved runtime
contents.

Real consumers reference the root at `0xc3755108`, including instruction
packets `0xc09033f8`, `0xc09034c4` and `0xc0903b20`. The group dispatcher reads
a selected list at `0xc0903444`. The initialization-function loop at
`0xc0903c50`–`0xc0903cc0` checks the entry pointer, type byte 2, priority -2,
zero stack/runtime-object fields, then executes the selected pointer with
`callr`. The saved loader descriptor fits those tests. This establishes an
initialization mechanism, **not that this boot selected/reached/executed it**.

## 2. The first state check is not the WLAN listener's state

`0xc19165e0` calls thunk `0xc1916870`, which jumps to `0xc0904f18`.
That function reads the word at `0xc506d680`. The `servreg` initialization
routine (`0xc0904fc4`) initializes this word to `0x7fffffff`; its later worker
has the store of `0x1fffffff` at `0xc09051b0`.

The loader compares the getter's return to `0x1fffffff` at `0xc19165e8`.
This is a local SERVREG subsystem state variable. Do **not** replace its
unknown live value with the **different**, previously measured UNINIT reply
for `msm/modem/wlan_pd` on notifier registration.

The equal-state path performs the domain/file checks below. The other path
creates a worker with entry `0xc1916a0c`; that worker waits on signals before
performing equivalent checks. The live branch and signal state are unknown.

## 3. The loader makes a different locator query from AP WLAN readiness

In `0xc19164d8`, the code obtains a locator handle, then at `0xc19164f8`
passes the string at `0xc3755c60`, **`kernel/elf_loader`**, through thunk
`0xc19165a8` to `0xc09048d4`. This routine copies the service name into its
request, and the send at `0xc09049cc`–`0xc09049dc` supplies message ID **33
(`0x0021`)**. The mapper's pinned schema and existing query/fixture code also
use `SERVREG_LOC_GET_DOMAIN_LIST = 0x21` on service 64. Message `0x0020` on
service 66 is the separate listener operation; earlier notes conflating
those message numbers were incorrect.

The precheck walks returned domain names and compares against the context's
`msm/modem/wlan_pd`. It can return zero on a match **or on a zero-count list**;
nonzero lookup/precheck results lead to an early return in setup. Thus neither
"wlan/fw resolves" nor "missing elf_loader entry necessarily blocks startup"
is a sufficient standalone conclusion.

### Installed maps and fixture check

Native `pd-mapper -n -d /usr/share/wayne/pd-maps` returned:

```
map service=kernel/elf_loader domain=msm/modem/wlan_pd instance=180
map service=tms/servreg domain=msm/modem/wlan_pd instance=180
map service=wlan/fw domain=msm/modem/wlan_pd instance=180
map service=tms/servreg domain=msm/modem/root_pd instance=180
maps_validated=4
```

This mode opens no QRTR socket. It proves installed-map parsing, **not a
completed modem-originated locator exchange**.

The existing socket-intercepting mapper fixture was extended to test:

- `wlan/fw` against the authentic map: one WLAN domain.
- `kernel/elf_loader` against that map: one WLAN domain, instance 180.
- An unknown service: zero domains.
- A synthetic copy with **only** `kernel/elf_loader` removed: zero domains for
  that query, while a `wlan/fw` query still returns the WLAN domain. The
  authentic source and installed maps are unchanged.

All 8 mapper test methods pass, including these five wire cases. They also
pass in a fresh ASan/UBSan userspace build, with leak detection disabled.
The 7 fixed-query and 7 startup/lifecycle host tests pass separately. These
are offline fixtures, not additional modem requests or a kernel build.

## 4. File checks can prevent an observable provider request

After the equal-state domain precheck, setup calls `0xc09ec768` on the
constructed default path, then the vendor fallback when the first result is
-1. This is a stat-like metadata operation, not proof of a completed transfer:

- Return 0 reaches the loader continuation at `0xc191684c`.
- Return -7 selects a retry-worker path.
- Other returns reach the failure exit at `0xc191674c`.

`0xc09ec768` runs local initialization/path checks before dispatching through
an operations-table pointer. The initializer at `0xc09ec8c0` calls backend
setup `0xc09ed04c`, which calls `0xc09efbc8`. That code contains TFTP-sized
block/window setup; when selected, the metadata slot points to `0xc09ecd08`,
which forwards to `0xc09ef44c`. An alternate stub table includes constant -15
returns. This static path is another reason the prior claim that TFTP was
irrelevant was unsupported. It does not establish the live selected table,
actual return code, successful server discovery or firmware delivery.

Consequently zero RRQs at our provider cannot distinguish skipped
initialization from a local rejection, failed lookup/metadata check, a prior
attempt or another route. No retry, filename rewrite or kernel symbol change
is justified solely by that observation.

## Subsequent runtime observation

[ROOT-STATE.md](ROOT-STATE.md) records a sender-validated QUERY_STATE response
of **UP** for the root domain. That is not a direct read of the local state
word or initialization-group progress, and does not establish WLAN readiness.

## Next evidence gate

Determine the **runtime** selected initialization group/progress, local
SERVREG state, locator result and first metadata return along this specific
path. Prefer an already-supported narrow diagnostic or a working Android
comparison. Do not enable a broad DIAG stream, change masks, force SSR or
flash instrumentation without separately qualifying that operation and
recovery path.

The native validation ended with modem ONLINE / crash count 0 and automatic
boot plus both dump gates still 0. It did not recheck PHY or prove cellular
service. The pocket-modem goal remains incomplete.
