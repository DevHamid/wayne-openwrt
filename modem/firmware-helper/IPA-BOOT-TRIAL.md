# IPA containment kernel: boot and one-start observation

## Provenance

Operator flashed only the OpenWrt boot image produced by split-ROM run
`44898788953`, source integration run `44897641932`, kernel source commit
`98c685b86d5c7dc0a7983e7010870dd8ed31e2e8` (adios-wayne parent
`33647babe2a652c201fb9f87639363ef7cf28cf2`).

Bounded installed boot-prefix readback matched the image SHA-256:
`341ff952f561ecba93f86346374451508a3f1101559dba7d31a28ec0b1eab563`.
Running kernel build stamp matched `Sat Nov 21 11:12:49 UTC 2026`.
Installed `modem-boot.ko` digest matched the candidate module, and loaded
successfully. SYSTEM, existing mapper/nameserver and read-only rmtfs were
preserved. Kernel locator initialization occurred at uptime 7.880812 s.

## Authorized device experiment

After confirming physical recovery/known-good backup availability, the operator
explicitly authorized **one guarded modem start**. Preflight verified the same
boot, modem never started, crash count 0, automatic boot disabled, both dump
gates 0, matching module, and one supervised read-only UIO-backed rmtfs.

Exactly one sysfs boot write was issued at uptime 734.43 s. It returned
success. No retry, SSR request, nameserver/mapper/rmtfs restart, provider
replacement, partition write, provisioning or radio-mode operation was
performed by the trial. QRTR discovery was used to observe WLFW presence;
no additional DMS/UIM/NAS/WDS QMI client requests were sent.

## Measured result

- **31 complete snapshots**, sequence 0 through 30, from uptime 735.88 to
  1038.83 s: **302.95 s** of sampled ONLINE state, crash count 0 throughout.
- Existing mapper/nameserver/rmtfs retained their PIDs throughout.
- Exactly one observed IPA new-server event and one arrival-work event:
  service 49, version 1, instance 2, node 0, port 36, init=0, ssr=1.
- INIT_DRIVER send at uptime 736.244823 s, response at 736.257035 s.
- No second INIT_DRIVER, timeout failure or AP panic observed in the window.
- WLFW service 69 absent and PHY count 0 in all 31 snapshots.
- Fresh independent SSH closeout at uptime 1068.58 s confirmed same boot,
  modem ONLINE/crash 0, existing daemons, automatic boot/dump gates 0.
- `rmnet_ipa0` exists but is DOWN with no IP address. No cellular bearer or
  internet connectivity was established.

The modem remains active after observation; the driver has no verified safe
sysfs shutdown operation. A bounded observer is not an automatic power-down.

## What this does and does not establish

The candidate boots and supports one modem/IPA startup plus a clean five-minute
window with the existing registry left untouched. It does **not** prove long-term
stability, a working cellular bearer, WLAN PD initialization, Wi-Fi, or survival
of an actual timeout: **no timeout occurred**.

The prior capture's EXIT cleanup restarted the QRTR nameserver while the modem
remained active. In this source, QRTR controller bind resets non-control sockets
(`net/qrtr/qrtr.c:1454-1498`), and QMI net-reset rebuilds sockets and re-registers
lookups/services (`drivers/soc/qcom/qmi_interface.c:438-471`). IPA's arrival
callback sends INIT_DRIVER without a completed-handshake/tuple deduplication
guard (`ipa_qmi_service.c:780-819,860-880`). These facts make cleanup a credible
confound for the earlier duplicate request; they do not prove why the previous
request timed out. Do not intentionally restart working QRTR services in the
next investigation merely to reproduce that path.

## Source-audit qualifications

On this exact core, `qmi_txn_wait()` already removes the transaction ID before
returning `-ETIMEDOUT` (`qmi_interface.c:342-361`); the added post-wait cancel is
redundant there. The ENETRESET result returns early instead. A second removal by
numeric ID is not ownership-checked and may race with cyclic reuse, so the
extra cancellation needs separate review rather than being advertised as a
proven cleanup fix. No additional kernel edit was made during this trial.

Also, the containment failure return does not clear an earlier
`qmi_modem_init_fin=true`: a failed duplicate attempt can retain prior success
state. Earlier wording that every failure leaves the handshake incomplete was
too broad. This trial observed only the initial successful handshake.

## Next gates

Preserve the working registry and read-only rmtfs. Identify the first missing
WLAN-PD/firmware step with source-backed, read-only observations. Keep bearer,
radio-state/provisioning changes and another modem start outside this trial.
Keep timeout containment and duplicate-event handling as separate review items.
