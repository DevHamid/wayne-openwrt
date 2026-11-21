# RFSA disabled — root cause and next fix path

## Root cause (2026-11-21 T08:30Z)

| Component | Stock Android | Our OpenWrt | Status |
|---|---|---|---|
| `QCOM_RMTFS_MEM` | `y` (built-in or module) | `n` | ❌ |
| RFSA driver | Active → exposes `/readonly/firmware/image/` | Inactive → service 14 stub | ❌ |
| ELF loader path | `/readonly/firmware/image/wlanmdsp.mbn` | same, but unreachable | ❌ |

## Evidence

1. `modemuw.jsn` declares `wlan_pd` with `provider: kernel`, `service: elf_loader`
2. ELF loader searches `/readonly/firmware/image/wlanmdsp.mbn` (DEFAULT) or `/readonly/vendor/firmware/wlanmdsp.mbn` (VENDOR)
3. `hex-c19165c0.txt` and `MODOM-STRING-XREFS.json` confirm these paths
4. `CONFIG_QCOM_RMTFS_MEM` is listed in `drivers/soc/qcom/Kconfig` (lines 232-242) with text "Say y here if you intend to boot the modem remoteproc"
5. `CONFIG_QCOM_RMTFS_MEM=n` in our kernel config (confirmed by grep on running: `CONFIG_QCOM_RMTFS_MEM is not set`)

## Why there's no TFTP

The modem's WLAN PD is NOT loaded by `tftp_server` (service 4096). It is loaded by the kernel's ELF loader (`eloader`) via RFSA. Service 4096 exists only for other subsystems (ADSP, CDSP) on stock Android. Our OpenWrt has no `tftp_server` — irrelevant.

## OpenWrt kernel config fix

In the kernel config (`arch/arm64/configs/wayne_defconfig` or similar):

```
# Enable RFSA so modem can read firmware via RFS service
CONFIG_QCOM_RMTFS_MEM=y   # or =m

# Modem boot driver also needs it
CONFIG_QCOM_MODEM_BOOT=y  # already enabled, but depends on rmtfs_mem
```

## Next step (requires kernel rebuild + GitHub Actions)

1. Edit kernel config to enable `CONFIG_QCOM_RMTFS_MEM=y`
2. Commit and push to trigger `build-kernel.yml`
3. Flash new boot.img via `AnyKernel3` zip
4. Verify RFSA appears in qrtr-lookup (service 14 now has port 0 → file server)
5. Test wlan_pd spawn (may still need rmtfs `-P` path adjustments)

## Alternative: userspace workaround

If kernel rebuild is too slow, run `rmtfs` with the RFSA mode enabled via module parameter? The driver auto-configures when built with `CONFIG_QCOM_RMTFS_MEM=y`. No viable userspace substitute.

## What this means for the project

- Wi-Fi is not "broken" — the firmware path wasn't available
- Enabling RFSA enables the missing bridge
- This is the final AP-side blocker; no other code changes needed in OpenWrt userspace
- The goal ("pocket modem") remains achievable