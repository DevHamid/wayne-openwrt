# Crash Analysis: Modem/SSR/IPA Race (boot C, commit #5841934)

## Summary
The post-boot-A halt on commit #5841934 is a kernel panic caused by a race between the modem SSR (subsystem restart) path and the IPA Q6 service-arrive workqueue. The modem crashes on its own (diag task starvation), and the kernel's teardown paths race each other, leading to a NULL/bad-page dereference and panic.

## Evidence (pstore from boot C)
- `console-ramoops-0` (44KB), `dmesg-ramoops-0` (96KB), `dmesg-ramoops-1` (118KB)
- Key trace:
  ```
  [69.311715] Fatal error on the modem.
  [69.321799] modem SFR scan: ... dog_hb.c:266:Task starvation: diag, ping: 4
  [69.734790] WARNING: CPU: 1 PID: 62 at qcom_smem_get+0x1bc/0x1f0
  [69.734981] Call trace: qcom_smem_get → microdump_modem_notifier_nb → subsys_notif_queue_notification → subsystem_restart_wq_func
  [69.735024] microdump_modem_notifier_nb: smem 611 not available
  [69.735205] Unable to handle kernel paging request at virtual address ffffff80122050e8
  [69.735261] Internal error: Oops: 96000007 [#1] PREEMPT SMP
  [69.735308] pc : mutex_lock+0x10/0x40
  [69.735313] lr : qmi_txn_cancel+0x24/0x50
  [69.735478] Call trace: mutex_lock → ipa_qmi_send_req_wait → ipa_q6_clnt_svc_arrive
  [69.737541] Kernel panic - not syncing: Fatal exception
  ```

## Root Cause
1. Modem crashes (diag task starvation, SFR watchdog).
2. SSR restart path (`subsystem_restart_wq_func`) fires `microdump_modem_notifier_nb`, which calls `qcom_smem_get` — hits a WARNING (smem item 611 not available during teardown) and then a NULL/bad-page dereference.
3. Simultaneously, the IPA Q6 service-arrive workqueue (`ipa_q6_clnt_svc_arrive`) calls `ipa_qmi_send_req_wait` → `qmi_txn_cancel` → `mutex_lock` on a freed/NULL mutex in the same IPA/QMI transaction structure that SSR teardown just invalidated (`ipa_uc_reset_pipe: Invalid IPA client` ×3 right before).
4. The oops in the IPA path is the fatal one → `Kernel panic - not syncing: Fatal exception`.

## Fix Direction
- `ipa_q6_clnt_svc_arrive` needs to check client validity before `qmi_txn_cancel`.
- `microdump_modem_notifier_nb` needs to guard `qcom_smem_get` against smem item 611 being absent during SSR.
- This is a kernel patch on the IPA/SSR code, not a config change.

## Status
- WLAN module side is correct in this image (`modules.dep` lists `wlan.ko`, `modules.builtin` has no qcacld).
- ICNSS handshake: all stages rc=0 (ARRIVE, CONNECT, IND_REGISTER, MSA_INFO, MSA_PERM, MSA_READY, CAP, HW_POWER) — WLAN firmware handshake is healthy.
- Modem: boots, registers services on qrtr, then crashes at 69s with diag task starvation.
- No wlan module load attempt in this boot's dmesg (the `wlan-load.sh` script runs later, after modem boot — which never completes).
