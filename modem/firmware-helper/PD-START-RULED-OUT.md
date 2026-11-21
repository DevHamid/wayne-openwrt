# WLAN-PD startup: measured results and scoped exclusions

This is source/firmware analysis, not a working WLAN fix. Earlier wording
(`b1f76c3` and following notes) overstated what service discovery, imports and
zero provider requests could exclude. The statements below supersede those
broad exclusions.

## Measurements retained

The separately recorded [listener trial](PDR-LISTENER.md) registered
`msm/modem/wlan_pd` successfully and received **UNINIT** (`0x7fffffff`). The
same socket then sent one restart, which returned **result 1 / error 9** with
the provider verified alive. This rejects missing listener registration alone
as the explanation for that refusal. It does not establish the refusal's cause.

The [provider observation](RX-OBSERVATION.md) discovered all ten reviewed
service-4096 keys and exercised its receive loop. No TFTP opcode or firmware
open was observed there during the bounded window; WLFW 69 and PHY were also
absent. Selected deployed firmware files matched the saved source set.
These observations do not trace every transport, earlier startup attempt or
modem-internal operation.

## What the inspected paths exclude, and what they do not

1. **The tested `wlan/fw` map is present.** The AP kernel's reviewed locator
   client requests a service-name mapping from the AP mapper; the validated
   reply supplies `msm/modem/wlan_pd`, instance 180. Missing that particular
   entry would produce a success response with a zero-domain list, not the
   observed mapping. This does not certify all possible startup queries or
   inputs. Numeric QRTR services and SERVREG names are different namespaces.
2. **The inspected peripheral broker is not a demonstrated modem client.**
   `pm-service` exposes Binder and QMI CSI server APIs; its inspected imports
   do not establish a modem-side QMI startup request. That is no reason to port
   the broker speculatively. Server-only QMI imports do not, however, exclude
   every non-QMI side effect, indirect device vote or action of another daemon.
3. **The reviewed recovery path is not a proven cold-start API.**
   `icnss_trigger_recovery()` requires existing PDR registration and forwards
   `service_notif_pd_restart()` for the registered domain. The direct trial
   tested that protocol operation and was rejected. This is an exclusion of
   that proposed recovery shortcut, not proof that no cold-start path exists
   anywhere in the kernel or firmware.
4. **The saved firmware includes the WLAN loader's names and setup code.**
   `MODEM.B17` has the domain, process/image names and default/vendor path
   templates. The subsequent [initialization inspection](ELOADER-INIT.md)
   identifies an `eloader_init`-named descriptor referencing the WLAN setup
   routine. Static presence is not execution; these strings neither prove
   that nothing asked for the image nor select RFSA over TFTP.

## Remaining unknown and next discriminant

No observed transaction or runtime trace yet identifies why WLAN firmware
service 69 fails to become available. Candidate mechanisms include skipped
initialization, an unmet prerequisite, an unobserved loader attempt/failure,
or notifier-name/state behavior that needs further explanation.

The next safe source step is to resolve the `eloader_init` descriptor consumer
and its early predicates, then compare with the working Android reference.
Continuous QRTR announcement capture during a separately authorized cold
start could catch a transient **numeric service** such as WLFW 69; it would
not directly enumerate SERVREG `kernel/elf_loader` names or explain all
internal failures. No cold start is necessary merely to inspect the saved
initialization tables.

Do not replay the rejected restart, rebuild for the retracted
[QCOM_RMTFS_MEM theory](RFSA-DISABLED.md), fabricate calibration or infer a
firmware transport from a path string. Provider timing/coverage were tested
in their recorded windows, not universally proved correct for all startup
conditions. Cellular bearer/IP/NAT, Wi-Fi-client internet and persistent
configuration remain unverified.
