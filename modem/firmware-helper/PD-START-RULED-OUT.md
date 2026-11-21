# Why the WLAN PD never starts — what is ruled out (2026-11-21)

Read-only source and firmware analysis on the deployed image. No device
operation was performed for this note; the live facts it cites were measured in
the windows recorded in `PDR-LISTENER.md` and `RX-OBSERVATION.md`.

## The measured state

`msm/modem/wlan_pd` reports **UNINIT** (`0x7fffffff`) on notifier registration,
QMI restart is refused with `result 1 / error 9`, WLFW service 69 never appears,
no PHY exists, and the read-only provider receives no TFTP opcode at all while
its receive path verifiably runs. The modem is ONLINE with crash count 0 and all
30 deployed modem/WLAN firmware files match the saved source set.

Taken together: the modem never reaches the point of asking for `wlanmdsp.mbn`,
so the failure is before firmware delivery, not in it.

## Ruled out by source, at the pinned revision

1. **The AP-side locator map is not the gap.** The modem's process-domain
   manager asks the AP for a domain by *service* name (SERVREG_LOC service
   `0x40`, `GET_DOMAIN_LIST` request `0x20`, `name` in TLV 1) and the AP answers
   with the owning domain and instance. `pd-mapper.c` matches on
   `pd_map->service`, and our map set already answers `wlan/fw ->
   msm/modem/wlan_pd, instance 180`. A missing map entry would have produced no
   answer at all, which is not what we observe.
2. **`pm-service` is not a PD starter.** It is the Android peripheral-manager
   broker (`vendor.qcom.PeripheralManager`): a Binder service plus a **QMI CSI
   server** for clients such as `cnss-daemon` (which calls
   `pm_client_register`/`pm_client_connect`). Its only QMI symbols are
   server-side (`qmi_csi_register_with_options`, `qmi_csi_send_resp/ind`,
   `common_qmi_idl_type_table_object_v01`). It tracks and votes peripheral
   state and relays restart requests between clients; it does not issue a modem
   QMI request that would create a PD. Porting it alone would not start `wlan_pd`.
3. **The kernel has no cold-start path.** `icnss_trigger_recovery()` is reached
   only from the debugfs node (`test_mode 3`), requires `ICNSS_PDR_REGISTERED`
   and an existing notifier handle, and calls `service_notif_pd_restart()` with
   the already-registered domain. That is byte-for-byte the request we sent
   directly, and the modem refused it. There is no exported or sysfs entry point
   that spawns a PD that is not already running.
4. **The modem image already knows what it would need.** `MODEM.B17` carries
   `msm/modem/wlan_pd`, `wlan_process`, `wlanmdsp.mbn`, `eloader-%s`,
   `/readonly/firmware/image/%s` and `/readonly/vendor/firmware/%s`, plus
   `USERPD is not present in DEFAULT path` / `... in VENDOR path`. So the domain
   name, the user-PD process name and the RFS path template are embedded; the
   PD image name does not have to come from the AP.

## The remaining unknown

Something that should make the modem's root PD (TMS) spawn the `wlan_pd` user PD
does not happen on this build. The candidate space is now narrow:

- a boot-time condition inside the modem (a TMS/PD configuration input the AP
  never supplies, or one it supplies late), or
- an AP-side request that stock Android makes and we do not.

Neither is reachable by static analysis of the files we already hold; the
distinguishing observation is a modem cold start with continuous QRTR
announcement capture, to see whether `wlan_pd`'s services (`elf_loader`,
`servreg`) or WLFW 69 appear even briefly before disappearing.

## What this note does not claim

It does not identify the root cause, does not prove stock Android starts the PD
the same way, and does not validate any fix. It removes four candidate causes so
no further work is spent on them: provider timing, provider protocol coverage,
locator/map completeness, and a missing kernel/userspace restart API.
