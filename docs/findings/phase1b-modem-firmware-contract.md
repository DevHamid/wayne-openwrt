# Phase 1b — Modem firmware contract: exact files, paths, and load order

Status: VERIFIED (static analysis, /srv/ssd/kernel-work @ d55e4acb1, branch a7-mglru-v5)
Depends on: docs/findings/phase1-modem-wlan-mechanism.md

## 1. The two drivers that read firmware

The modem bring-up touches TWO separate firmware loads, in a fixed order:

**(a) MBA — loaded first, by `pil_mss_reset_load_mba()`**
**(b) modem image — loaded second, by `pil_boot()`**

Both use `request_firmware()`, i.e. plain files in `/lib/firmware/`.

## 2. MBA firmware — `pil-msa.c:651`

```c
int pil_mss_reset_load_mba(struct pil_desc *pil)
{
    ...
    char fw_name_legacy[10] = "mba.b00";
    char fw_name[10]       = "mba.mbn";
    char *dp_name          = "msadp";
    ...
    fw_name_p = drv->non_elf_image ? fw_name_legacy : fw_name;
    ret = request_firmware(&fw, fw_name_p, pil->dev);
    if (ret) {
        dev_err(pil->dev, "Failed to locate %s (rc:%d)\n", fw_name_p, ret);
        return ret;
    }
    ...
    ret = request_firmware(&dp_fw, dp_name, pil->dev);
    if (ret) {
        dev_warn(pil->dev, "Debug policy not present - %s. Continue.\n", dp_name);
    }
```

Required:
- **`/lib/firmware/mba.mbn`** (or `mba.b00` if `non_elf_image` is set — see section 4)

Optional, warns and continues if absent:
- **`/lib/firmware/msadp`** — debug policy. `dev_warn`, not fatal.

`msadp` is the one file that is genuinely optional. Everything else is mandatory.

## 3. Modem image — `peripheral-loader.c:1252`

```c
snprintf(fw_name, sizeof(fw_name), "%s.mdt", desc->fw_name);
ret = request_firmware(&fw, fw_name, desc->dev);
```

`desc->fw_name` comes from `pil-q6v5-mss.c:160` (`drv->q6->desc.fw_name = subsys->fw_name`),
which comes from the DT at `sdm660.dtsi:2298`:

```
qcom,firmware-name = "modem";
```

So the required files are:
- **`/lib/firmware/modem.mdt`** — mandatory, hard failure if absent
- **`/lib/firmware/modem.b00`, `modem.b01`, ... `modem.bNN`** — segments

Segment naming is at `peripheral-loader.c:1024`:
```c
snprintf(fw_name, ARRAY_SIZE(fw_name), "%s.b%02d", desc->fw_name, num);
```

The `.mdt` is the metadata/ELF header that describes the segments; the `.bNN` files are the
payload. You need the whole set — an `.mdt` with no `.bNN` will not boot.

## 4. `qcom,sequential-fw-load` — what it changes

`sdm660.dtsi` mss node has `qcom,sequential-fw-load`. It is read at
`pil-q6v5-mss.c:326`:
```c
q6_desc->sequential_loading = of_property_read_bool(pdev->dev.of_node,
                                                    "qcom,sequential-fw-load");
```

Effect: the segments are loaded and authenticated one at a time, in order, rather than all at
once. **This does not change the file set** — it is still `modem.mdt` + `modem.bNN` — but it
does change the ordering and how `pil_boot()` walks them. The `.bNN` files must be present and
correctly numbered; a gap in the sequence is fatal.

Practical consequence: you cannot cherry-pick a subset of segments. Copy the entire
`modem.mdt` + `modem.b*` set.

## 5. `qcom,pil-self-auth` — this one DOES change behavior significantly

`sdm660.dtsi` mss node has `qcom,pil-self-auth`. Read at `pil-q6v5-mss.c:330`:
```c
q6->self_auth = of_property_read_bool(pdev->dev.of_node, "qcom,pil-self-auth");
if (q6->self_auth) {
    res = platform_get_resource_byname(pdev, IORESOURCE_MEM, "rmb_base");
    q6->rmb_base = devm_ioremap_resource(&pdev->dev, res);
    if (IS_ERR(q6->rmb_base))
        return PTR_ERR(q6->rmb_base);
    drv->rmb_base = q6->rmb_base;
    q6_desc->ops = &pil_msa_mss_ops_selfauth;     /* <-- OPS TABLE SWAP */
}
```

**This swaps the entire reset-ops table** (`pil-msa.c:1023` vs `:1035`):

```c
/* self-auth DISABLED, or MBA loaded as segments not init_image */
struct pil_reset_ops pil_msa_mss_ops = {
        .proxy_vote    = pil_mss_make_proxy_votes,
        .proxy_unvote  = pil_mss_remove_proxy_votes,
        .auth_and_reset = pil_mss_reset,
        .shutdown      = pil_mss_shutdown,
};

/* self-auth ENABLED: MBA loaded in init_image, modem headers authenticated in
 * init_image, modem segments authenticated in auth_and_reset */
struct pil_reset_ops pil_msa_mss_ops_selfauth = {
        .init_image    = pil_msa_mss_reset_mba_load_auth_mdt,
        .proxy_vote    = pil_mss_make_proxy_votes,
        .proxy_unvote  = pil_mss_remove_proxy_votes,
        .mem_setup     = pil_mss_mem_setup,
        .verify_blob   = pil_msa_mba_verify_blob,
        .auth_and_reset = pil_msa_mba_auth,
        .deinit_image  = pil_mss_deinit_image,
        .shutdown      = pil_mss_shutdown,
};
```

Consequences of self-auth being ON (it is, per DT):
1. **A `rmb_base` register resource is mandatory.** If the mss DT node lacks an
   `IORESOURCE_MEM` named `rmb_base`, `pil_mss_loadable_init()` returns the error and probe
   FAILS. Must verify the node has it.
2. The MBA is loaded via `init_image` and authenticated through `pil_msa_mba_verify_blob()`,
   which writes to `rmb_base` RMB registers (`pil-msa.c:951-975`) — i.e. it talks to the
   TrustZone/MBA through a shared register block.
3. This is the path that requires TrustZone cooperation. **If the TZ app on this device does
   not accept the MBA blob, boot fails here** — and this is the single most likely place for
   an Android-vs-OpenWrt difference that is NOT fixable in the kernel.

## 6. Complete required file list

Mandatory in `/lib/firmware/`:
```
mba.mbn          (or mba.b00 if non_elf_image)
modem.mdt
modem.b00
modem.b01        ... through the highest segment present in the .mdt manifest
```

Optional (warns, continues):
```
msadp            debug policy
```

NOT needed for the modem (common misconception):
```
wlanmdsp.mbn     -- WLAN FW is fetched by the Q6 over QMI, icnss.c has no request_firmware
bdwlan.bin/.elf  -- icnss2 only; CONFIG_ICNSS2 is not set on this device
```

## 7. How to verify the exact segment set

The `.mdt` is an ELF header describing the segments. The authoritative count is in the `.mdt`
itself, so do not guess the `.bNN` range — read it from the file once it is on disk:

```
On the phone, once modem.mdt is present:
  ls -la /lib/firmware/modem.*
  # then confirm the highest bNN matches the segment count in the mdt
```

If the segment set is incomplete, `pil_boot()` fails and (see Phase 1 section 4)
`subsystem_powerup()` may **panic** unless `ignore_ssr_failure` is set.

## 8. Rootfs integration notes

- Rootfs is on **p64** and is writable, so `/lib/firmware/` should persist across reboots.
- It did NOT persist last time: the M8 staging was lost and the diag report showed
  `/lib/firmware/` empty. Verify after every reflash with `ls -la /lib/firmware/`.
- OpenWrt keeps firmware in `/lib/firmware/` by convention; `request_firmware()` also searches
  the paths in `/sys/module/firmware_class/parameters/path` if set. Default is `/lib/firmware`.

## 9. Open questions — RESOLVED (both answered by cheap static checks)

**Q1: Does the mss node have `rmb_base`?** **YES.** `sdm660.dtsi` mss node reg-names:
```
reg-names = "qdsp6_base", "halt_q6", "halt_modem",
            "halt_nc", "rmb_base", "restart_reg",
            "cxip_lm_vote_clear";
```
`rmb_base` is present, so `pil_mss_loadable_init()` will succeed at `:333-337` and the
self-auth path is viable. **This was the cheap check worth doing first and it passed.**

**Q2: `mba.mbn` or `mba.b00`?** **`mba.mbn`.** `non_elf_image` is set from
`qcom,mba-image-is-not-elf` (`pil-q6v5.c:764`), and that property is **ABSENT** from the mss
node (grep count = 0). So `fw_name_p = fw_name` = `"mba.mbn"` (`pil-msa.c:669`).

## 10. Remaining open question (not statically answerable)

**TrustZone acceptance of the MBA blob.** With `qcom,pil-self-auth`, the MBA is authenticated
through the `rmb_base` register block by TrustZone. If the TZ app on this device rejects the
blob, boot fails at `pil_msa_mba_verify_blob()` / `pil_msa_mba_auth()` — and no kernel change
fixes that. Only a boot test answers it. This is the single most likely place for a genuine
Android-vs-OpenWrt wall.

## 11. Files of record

- `drivers/soc/qcom/pil-q6v5-mss.c:146` modem_powerup; `:160` fw_name assignment;
  `:305-340` loadable_init + self_auth ops swap; `:326` sequential_loading
- `drivers/soc/qcom/pil-msa.c:651` pil_mss_reset_load_mba (mba.mbn / mba.b00 / msadp);
  `:937` init_image selfauth path; `:951` verify_blob RMB registers; `:1023` ops;
  `:1035` ops_selfauth
- `drivers/soc/qcom/peripheral-loader.c:1024` `"%s.b%02d"` segments; `:1252` `"%s.mdt"`
- `arch/arm64/boot/dts/vendor/qcom/sdm660.dtsi:2264` mss node (`sequential-fw-load`,
  `pil-self-auth`, `firmware-name="modem"`, `memory-region=<&modem_fw_mem>`)
