# Knowledge Note — Why our 4.19 kernel can carry newer OpenWrt

*Wayne (Mi 6X) · 2026-10-16 · the "car" explainer, kept for morning-coffee reading.*

## Part 1 — The plain picture (read this first)

**A phone OS is a car.**

- **Kernel = engine + chassis.** Only it talks to real hardware: screen, Wi-Fi,
  USB, eMMC, buttons. Nothing moves without it.
- **Userspace (OpenWrt / ImmortalWrt) = dashboard, seats, AC.** BusyBox, `uci`,
  firewall rules, the web UI — everything you actually see and touch.

A firmware file ships **both halves welded together**, so yes: every OpenWrt you
download already has "its" kernel inside. Each release pins a **default engine**:

| Release | Default kernel |
|---|---|
| 19.07 | 4.14 |
| 21.02 | 5.4 |
| 23.05 | 5.15 |
| 24.10 | 6.6 |
| 25.x | 6.6+ |

The number means *"tested with this engine"*, not *"dies on any other"*.

**Why halves can be swapped:** they talk through the **syscall handshake**, and
Linus's iron rule is *never break userspace*. New apps usually run on old
kernels — **until** an app asks for a kernel feature the old kernel lacks. That
is the only wall.

**The two build tools:**

- **ImageBuilder** = LEGO box. Pick your bricks (packages); the engine is
  **welded shut** — you can never change the kernel with it.
- **Buildroot** = the whole factory. You *can* swap engines, but then you own
  every patch, driver and config — it fights you, because its patches target
  *its* kernel.

## Part 2 — What WE actually do (the trick)

Our phone is **not an official OpenWrt target**, so we never asked OpenWrt to
build an engine:

1. **Engine**: the proven **Android 4.19 kernel** (LKGeek) — it already contains
   working drivers for our exact chip (sdm660).
2. **Dashboard**: ImmortalWrt's **prebuilt rootfs** (`armvirt/64`, 21.02.7) — a
   generic aarch64 userspace that is engine-agnostic.
3. We pack kernel + rootfs into one boot image → **hybrid: Android engine,
   OpenWrt interior.**

That is why *"works on Android ⇒ can work on our OpenWrt"* is true **by
construction** — the same engine sits underneath.

## Part 3 — "But we broke the rules"

We broke **one** rule, not all: *21.02 officially ships with 5.4*, and we run its
userspace on 4.19. That worked because the 21.02 dashboard barely asks anything
of a newer engine. Going newer is a **ladder of small asks**, not one wall:

| Userspace | What it asks from the kernel | 4.19 verdict |
|---|---|---|
| 21.02 (fw3) | very little | ✅ proven — we live here |
| 22.03 (fw4/nftables) | nftables machinery | ⚠️ 4.19 has nftables; a few newer expressions missing |
| 23.05 (fw4 default) | same + newer musl/busybox | ⚠️ plausible, same nftables question |
| 24.10 / 25.x | built/tested against 6.x; kmod + netlink + sysfs expectations | 🔴 possible in theory, real work in practice |

**Key insight:** the kernel-version-bound parts are almost entirely **kmods**
(out-of-tree driver modules) — and we use **none**, because our engine carries
its own drivers inside. Pure userspace (musl, busybox, `uci`, dnsmasq, hostapd)
is far more forgiving than release numbers suggest.

**Realistic ladder:** (1) stay 21.02 + 4.19 to finish M6/M7/M9; (2) try **23.05's
rootfs on the same 4.19 engine** — one variable at a time; (3) 24/25 only if 23
works and something there is worth it. Same engine throughout — tuning the
stereo, not rebuilding the car.

## Part 4 — Recovery pointers (technical)

- Repo: `/srv/ssd/wayne/repo` → `github.com/DevHamid/wayne-openwrt`, branch `main`.
- Kernel (engine): `DevHamid/LKGeek_sdm660@build-all-rekernel`, 4.19.325 — built
  separately, **not** by OpenWrt's buildroot.
- Rootfs (dashboard): ImmortalWrt `21.02.7 armvirt/64` prebuilt tarball, pulled in
  `build.yml` → `Assemble OpenWrt initramfs`.
- Packing: `scripts/pack-boot.py` combines `Image.gz-dtb` + our initramfs.
- Latest shipped: **v0.9.7** (M6 VBUS DT fix `vbus_dwc3-supply` + in-image
  screen/burn-in automation). Release assets: `openwrt-boot.img`,
  `installer-boot.img`, `debug-boot.img`, `donor-control.img`, `bisect-*.img`.
- Next action: flash `installer-boot.img` (refresh p64) then `openwrt-boot.img`;
  seat an OTG device; expect `regulator.75 = enabled` and a `1-1:` device.
- Full repo copy of this note: `docs/knowledge-notes/2026-10-16-why-419-carries-newer-openwrt.md`.

*Bottom line: newer OpenWrt buys newer **apps**, not newer **drivers**. Our
drivers already exist — they've been riding in the 4.19 Android engine since day
one.*
