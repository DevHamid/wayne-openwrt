# Wayne OpenWrt — Progress & Status (User-Friendly)

**Goal:** Turn a Xiaomi Mi 6X (wayne, SDM660) into a pocket modem + services box on stock/vendor kernel 4.19 + ImmortalWrt 24.10. No PC, no fastboot — flashable from TWRP/OrangeFox recovery zip.

---

## Where we are

| Milestone | Status | Notes |
|-----------|--------|-------|
| v2 ROM baseline (kernel + 24.10.4 rootfs) | ✅ Locked | SSH + ECM working, WLAN not yet up |
| Wi-Fi root cause (qcacld built into vmlinux) | ✅ Identified | Build sfr-v2 branch (`=m` module) |
| Wi-Fi module fix (wlan.ko register) | 🔄 In progress | CI build #45856240474 running |
| Modem/SSR crash root cause | ✅ Identified | IPA/SSR race, kernel patch pushed |
| Modem data call (LTE) | ⏳ Gated | Waiting on Wi-Fi + modem fix |
| WebUI (LuCI modem status) | ⏳ Gated | Waiting on modem data call |

## Latest work (2026-11-26)

- **Crash captured & root-caused:** The boot-C halt on commit #5841934 was a kernel panic — a race between the modem SSR (subsystem restart) teardown path and the IPA Q6 service-arrive workqueue. The modem crashes on its own (diag task starvation), then the kernel's teardown paths race each other: `qmi_txn_cancel` → `mutex_lock` on a freed IPA client, plus `microdump_modem_notifier_nb` dereferencing a bad smem pointer. Full pstore (44KB console + 96KB + 118KB dmesg) pulled and documented.
- **Kernel patch pushed:** `fix/ipa-ssr-race-20261126` branch on LKGeek_sdm660 — guards `ipa_q6_clnt_svc_arrive` (workqueues_stopped + NULL checks) and `microdump_modem_notifier_nb` (drv/microdump_dev NULL guard). CI build #45856240474 dispatching now.
- **Analysis documented:** `docs/crash-analysis-20261126.md` + PR #6 on wayne-openwrt.

## What's next

1. CI build completes → flash to device via OTA → verify modem doesn't panic.
2. If modem stable → load wlan.ko → verify wiphy appears → test Wi-Fi.
3. If Wi-Fi works → modem data call (MM net-port / IPA) → LTE.
4. Then WebUI (LuCI modem status + control).

## Key numbers

- Kernel: 4.19.325-LKGeek-devhamid-remastered, vendor tree
- Rootfs: ImmortalWrt 24.10.4
- ROM zip: ~210MB
- Device: Mi 6X (wayne, SDM660), 6GB RAM

## Links

- Repo: https://github.com/DevHamid/wayne-openwrt
- Kernel: https://github.com/DevHamid/LKGeek_sdm660
- Crash analysis PR: https://github.com/DevHamid/wayne-openwrt/pull/6
- CI build: https://github.com/DevHamid/wayne-openwrt/actions/runs/45856240474
EOF
echo "written"