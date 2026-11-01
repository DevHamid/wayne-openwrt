# Phase 1 — Q6 modem / WLAN bring-up: kernel boot mechanism, rootfs contract

Status: VERIFIED (static analysis, /srv/ssd/kernel-work @ d55e4acb1, branch a7-mglru-v5)
Device: wayne (SDM660), ImmortalWrt, kernel 4.19.325-LKGeek-perf-devhamid

## 1. The mechanism — who boots the Q6

`pil-q6v5-mss.c:146 modem_powerup()` is the ONLY thing that starts the modem:

```c
static int modem_powerup(const struct subsys_desc *subsys)
{
    struct modem_data *drv = subsys_to_drv(subsys);
    if (subsys->is_not_loadable) return 0;
    reinit_completion(&drv->stop_ack);
    drv->subsys_desc.ramdump_disable = 0;
    drv->ignore_errors = false;
    drv->q6->desc.fw_name = subsys->fw_name;
    return pil_boot(&drv->q6->desc);      /* <-- actual boot */
}
```

Call chain into it:
- `subsystem_restart.c:945 __subsystem_get(name, fw_name)` -> `subsys_start(subsys)` (`:836`) -> `subsys->desc->powerup(subsys->desc)`
- `subsystem_restart.c:842` — same call, second site, reached via `subsystem_powerup()` (`:773`), used by the restart/SSR path
- `subsys_start()` is static; `subsystem_powerup()` is static. Both are reached only from
  `__subsystem_get()` / `subsystem_restart_dev()`.

**No autoboot.** `pil_subsys_init()` (`pil-q6v5-mss.c:231`) ends at `subsys_register()`
(`:274`) and stops there. `subsys_register()` (`subsystem_restart.c:1811`) only allocates the
`subsys_device`, adds it to `subsys_bus_type` ("msm_subsys"), creates the sysfs attrs and the
`/dev/subsys_<name>` char node. It does NOT call powerup.

Confirmed by grep across the whole tree: no `subsys_boot(`, no `subsys_get(` callers in
`drivers/soc/qcom/`, and `pil_boot(` appears only as a prototype in
`peripheral-loader.h:119` plus the inline stub at `:137`. The venus/adsp/cdsp boot lines come
from `subsys-pil-tz.c`, which uses a different self-contained path (`qcom,firmware-name`
derived name at `:1090`) that the modem does not share.

## 2. The kernel is fine — the trigger is missing

DT is correct and loadable:
- `sdm660.dtsi:2264` `pil_modem: qcom,mss@4080000`, compatible `"qcom,pil-q6v55-mss"`
  (matched by `mss_match_table[]`, `pil-q6v5-mss.c:528-533`)
- `qcom,is-not-loadable` is ABSENT -> `pil_mss_loadable_init()` runs -> `drv->q6` populated
- `sdm660.dtsi:2298` `qcom,firmware-name = "modem"`
- No `qcom,pas-id` -> `"No pas_id found."` is dev_info, non-fatal (`pil-q6v5-mss.c:415-418`)

Defconfig: `CONFIG_MSM_PIL_MSS_QDSP6V5=y` (`:707`), `CONFIG_MSM_PIL=y` (`:716`),
`CONFIG_MSM_SYSMON_QMI_COMM=y` (`:717`), `CONFIG_MSM_PIL_SSR_GENERIC=y` (`:718`).

So: driver bound, subsystem registered, `/sys/class/subsys/subsys_modem` exists — and nothing
ever calls powerup. **The kernel exposes a boot interface and waits for someone to use it.**

## 3. CORRECTION — there is no userspace boot trigger to write

I told the user Phase 2 would be "a small userspace program that boots the modem subsystem."
That is wrong. There is no such interface, and this is the single most important finding here.

`subsystem_restart.c:1411 subsys_device_fops`:
```c
static const struct file_operations subsys_device_fops = {
        .owner  = THIS_MODULE,
        .open   = subsys_device_open,
        .release = subsys_device_close,
};
```
No `.read`, no `.write`, no `.unlocked_ioctl`, no `.compat_ioctl`. The `/dev/subsys_modem`
char node (`:1459`, `device_create(char_class, ..., "subsys_%s", name)`) is open/close only.

The sysfs attrs are read-only: `subsys_attrs[]` (`:382`) is `name`, `state`, `crash_count`,
`restart_level`, `firmware_name`, `system_debug` — none is a trigger.

`subsystem_get()` / `subsystem_get_with_fwname()` (`:1006`, `:1022`) are the real boot entry
points and both are `EXPORT_SYMBOL` — **kernel-only, no sysfs/chardev wrapper.** Nothing in
this tree calls them.

Therefore: userspace cannot boot the modem on this kernel as it stands. A kernel patch is
required to expose it (an ioctl on subsys_device_fops, or a writable sysfs attr).

## 4. CORRECTION — the firmware requirement I got wrong

`pil-q6v5-mss.c:160`: `drv->q6->desc.fw_name = subsys->fw_name;` and
`sdm660.dtsi:2298` `qcom,firmware-name = "modem"`.

`peripheral-loader.c:1252-1255`:
```c
snprintf(fw_name, sizeof(fw_name), "%s.mdt", desc->fw_name);
ret = request_firmware(&fw, fw_name, desc->dev);
if (ret) {
    pil_err(desc, "Failed to locate %s(rc:%d)\n", fw_name, ret);
```

So the modem loads `/lib/firmware/modem.mdt` from disk. I previously claimed "on SDM660 FW is
loaded by the remote Q6 via QMI/PIL, no request_firmware in icnss" — half right (icnss does
not request WLAN firmware; that part was verified) but the conclusion "firmware is a dead
end" was wrong. The modem PIL absolutely requests firmware from disk.

**The device report showed `/lib/firmware/` EMPTY** (section 8: no `wlanmdsp.mbn`, no
`bdwlan.bin`, nothing wlan/wcn). That is not cosmetic — even with a boot trigger, `pil_boot()`
would fail at `request_firmware("modem.mdt")` and `subsys_start()` would return the error.
`subsystem_powerup()` (`:773`) would then `panic()` on powerup failure unless
`dev->desc->ignore_ssr_failure` is set.

Firmware is therefore a HARD prerequisite, not a side quest. It must be in place before any
boot-trigger patch can be validated.

## 5. WLAN firmware — the v1/v2 asymmetry

`icnss.c` (v1, the one bound on this device) has NO `request_firmware` call at all — verified
by grep. On SDM660 the WLAN firmware is fetched by the Q6 itself over QMI once the WLFW
server comes up, which is why WLAN dies when the modem/servloc dies.

`icnss2/qmi.c:40-46` DOES reference firmware files:
```
BDF_FILE_NAME_PREFIX        "bdwlan"
ELF_BDF_FILE_NAME           "bdwlan.elf"
BIN_BDF_FILE_NAME           "bdwlan.bin"
DUMMY_BDF_FILE_NAME         "bdwlan.dmy"
```
`icnss2/qmi.c:809` `request_firmware(&fw_entry, filename, &priv->pdev->dev)`.

So: built-in WLAN FW is fetched remotely (icnss v1 path); icnss2 would want bdwlan.* on disk.
Do not conflate the two. `CONFIG_ICNSS2` is not set and the device report confirmed icnss2
absent.

## 6. Why servloc dies — the dependency chain, restated

`service-locator.c:28` `LOCATOR_SERVICE_TIMEOUT = 300000` (ms). Report showed the timeout
fire at t=313.65s = 300s + ~13.7s boot overhead, `rc = -62` = **-ETIME** (driver's own code at
`:283`), not ETIMEDOUT(110).

Chain (each link verified earlier this investigation):
```
no boot trigger -> Q6 never runs
  -> service locator has no remote to talk to
  -> get_service_location("wlan","wlan/fw") fails (icnss.c:2012)
  -> no PDR notifier registered for WLAN
  -> WLFW QMI server never advertised (icnss_qmi.c:1342-1348)
  -> wlfw_new_server() never fires (icnss_qmi.c:1282)
  -> ICNSS_FW_READY never set
  -> icnss_driver_event_register_driver() bails (icnss.c:1339, "FW is not ready yet")
  -> pld_snoc_probe never runs
  -> no wiphy -> no wlan0
```
`adsprpc: PDR notifier locator for adsp is down` is the SAME locator failing for a different
consumer -> transport-wide, not a WLAN bug.

## 7. Instrumentation state (corrected earlier this session)

- Running kernel HAS `CONFIG_DEBUG_FS=y` — pulled in transitively by a dependency
  (`select DEBUG_FS` in `mm/Kconfig:692`, `kernel/trace/Kconfig:471`, `net/sunrpc/Kconfig:40`,
  `drivers/md/bcache/Kconfig:23`, `drivers/edac/Kconfig:36`) and present in NEITHER wayne
  defconfig. Adding `CONFIG_DEBUG_FS=y` is redundant.
- `CONFIG_DYNAMIC_DEBUG` is OFF (`lib/Kconfig.debug:81` `default n`) — the real gap.
  This is the only symbol that lets `icnss_pr_dbg()` / `icnss_qmi_pr_dbg()` be enabled at
  runtime.
- `CONFIG_ICNSS_DEBUG` deliberately not set — `drivers/soc/qcom/Kconfig:965` help text says it
  enables BUG_ON on hardware-register access (hang risk).

Retracted claims, do not repeat:
- "icnss2 + SKIP_QMI can fix this": icnss2 is ABSENT on-device, `Makefile:106` gates it on
  CONFIG_ICNSS2 (unset), and it would race the bound ICNSS for the same `"qcom,icnss"`
  compatible (`icnss2/main.c:3533`).
- "no subsys-pil-tz line for modem is an asymmetry": `subsys-pil-tz.c:1090` names itself from
  `qcom,firmware-name`; only venus/adsp/cdsp/kgsl use that driver. The modem uses
  pil-q6v5-mss. Expected absence, means nothing.
- "firmware is a dead end / loaded by remote Q6": WRONG for the modem. See section 4.
- "DEBUG_FS is off, we are debugging blind": wrong, see section 7.

## 8. Phase 2 — what actually has to happen

Two independent prerequisites, both mandatory, order matters:

**(a) Firmware on disk, first.** `/lib/firmware/modem.mdt` (+ `.b00`-`.bNN` segments per
`peripheral-loader.c:1024` `"%s.b%02d"`) must exist. Rootfs is on p64 and is writable, so it
should persist — but the M8 staging did NOT persist last time, so verify with
`ls -la /lib/firmware/` after any reflash. Without this, `pil_boot()` fails at
`request_firmware()` and the failure is a hard error, possibly a panic.

**(b) A kernel patch to expose the boot trigger.** No userspace interface exists (section 3).
Cheapest options, in order of preference:
  1. Writable sysfs store on the subsys device, e.g. `echo modem > /sys/class/subsys/.../boot`
     calling `subsystem_get(name)` on write and `subsystem_put()` on "0".
  2. `.unlocked_ioctl` on `subsys_device_fops` — matches Android's internal pattern more
     closely but more code and more risk.
Either way it is a real source patch to `subsystem_restart.c` + a rebuild, not a config change.

**(c) Then the OpenWrt integration.** Once the kernel can boot it, an init script/procd service
should call it at boot so it survives reboot — that part is the "userspace" work I originally
promised, and it only exists AFTER (b).

## 9. Open questions for Phase 2

- Does `modem.mdt` need `qcom,sequential-fw-load` handling? The mss node HAS
  `qcom,sequential-fw-load` (`dtsi`, mss props) — `pil-q6v5-mss.c` reads it, and it changes how
  `.bNN` segments are loaded in order. Must confirm the firmware set matches.
- `qcom,pil-self-auth` present on mss — affects whether PIL authenticates via TZ. Need to
  confirm TrustZone accepts it on this device (Android did; a different TZ app may not).
- Is `modem_powerup` failure `panic()`-safe? `subsystem_powerup()` panics unless
  `ignore_ssr_failure` is set. If the patch calls `subsystem_get()` and firmware is missing,
  that is a panic, not a clean error. Must set `ignore_ssr_failure` or guarantee firmware first.

## 10. Files of record

- `drivers/soc/qcom/pil-q6v5-mss.c:146` modem_powerup; `:231` pil_subsys_init; `:454` probe;
  `:528` mss_match_table
- `drivers/soc/qcom/peripheral-loader.c:1024` `"%s.b%02d"` segments; `:1252` `"%s.mdt"` + request_firmware
- `drivers/soc/qcom/subsystem_restart.c:945` __subsystem_get; `:836` subsys_start;
  `:842` powerup call; `:773` subsystem_powerup; `:1411` subsys_device_fops (NO ioctl);
  `:1459` /dev/subsys_%s; `:382` sysfs attrs (read-only); `:1811` subsys_register
- `drivers/soc/qcom/service-locator.c:28` timeout; `:283` -ETIME
- `drivers/soc/qcom/icnss.c:2012` get_service_location; `:1339` FW-not-ready bail
- `drivers/soc/qcom/icnss_qmi.c:1282` wlfw_new_server; `:1342-1348` qmi_add_lookup
- `drivers/soc/qcom/icnss2/qmi.c:40-46` bdwlan.* names; `:809` request_firmware
- `arch/arm64/boot/dts/vendor/qcom/sdm660.dtsi:2264` mss node; `:2298` firmware-name "modem"
- `arch/arm64/configs/vendor/wayne-oss-perf_defconfig:707,716,717,718` PIL config
- On-device report: `/tmp/wayne-diag/report.txt` (246 lines), regenerated by
  `scripts/wayne-diag.sh` on branch `openwrt-kernel`
