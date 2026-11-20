# Registry boot milestone — evidence and remaining gates

This is a safety checkpoint of tested userspace work, not a working pocket-modem release. It does not modify the kernel build selection or automatically add the registry to any image assembler.

## Observed on Wayne

- The registry startup files were added to SYSTEM without replacing existing USB, rmtfs or modem-policy files. A separate readback checked the new files/links and the protected baseline hashes before reboot.
- After one watched reboot, USB SSH returned, and both new procd services were running.
- The kernel logged `Connection established with the Service locator` at uptime **7.652779 s**, then `Service locator initialized` at **7.652803 s**. This is direct kernel-side evidence, separate from the helper's own readiness query.
- A fixed local query returned `wlan/fw -> msm/modem/wlan_pd`, instance 180. The application query does not by itself prove Wi-Fi readiness.
- One subsequent manual modem start reached ONLINE. All fourteen five-second observations reported ONLINE, crash count 0, PHY count 0. Later readbacks on the same boot still showed ONLINE/crash 0; a readback at uptime 913.96 s was approximately nine minutes after the kernel's modem-online event.
- Notification service 66, instance 180, appeared; the kernel logged a connection to that instance. IPA microcode and its modem-driver initialization exchange completed. The `rmnet_ipa0` device existed but was DOWN.

The 70-second bound was an **observation bound**, not an automatic shutdown: the sysfs start retains a kernel reference, and the modem remained online afterward. `allow_boot=0` prevents automatic startup on a later boot; it does not power down an already running modem.

Device wall-clock log dates differ from host UTC. The event offsets above are kernel uptime, not wall-clock timestamps.

## What this does not establish

- The cause of earlier ERR_FATAL events is **not proven**. Earlier pre-mapper observations also included a window without a fresh fatal. There was no controlled A/B experiment. Do not claim the mapper alone fixed the previous crash loop.
- Crash count 0 on a new boot cannot be compared with count 2 on the previous boot as proof that crashes were repaired; counters reset with the kernel.
- WLFW service 69 was not observed in the sampled discovery, no firmware-ready event or Wi-Fi PHY was observed, and no client connection was established. Missing service 69 does not alone identify a regulator, firmware-path or delivery-service root cause.
- No cellular bearer/IP/NAT or client internet test passed. An IPA netdev and DMS/NAS/WDS service discovery are not a working WAN.
- The intended userdata-backed overlay/persistence is still unverified. Registry persistence on writable SYSTEM is not that finish line.
- No CI artifact or release contains this checkpoint automatically. Experimental TFTP work and operational activation scripts are deliberately excluded.

## Safety boundary

The rollout added registry files, four startup/shutdown links and an installation receipt on SYSTEM. It did not write boot/kernel, vendor, userdata or recovery, or request calibration/provisioning changes. The observed rmtfs arguments retained `-r -P`; this is backing-write protection, not proof that no backing reads occurred. Both dump gates and persistent modem autostart stayed 0 during the recorded trial.

## Offline verification

The committed startup fixtures cover delayed discovery, no modem endpoint, bad maps/missing executables, wrong locator tuple, dead managed instance, bounded wait and query failure without replay. The query fixture intercepts the actual socket/send/poll/receive/close path and rejects truncated, malformed, wrong-peer and wrong-domain replies. Mapper fixtures abort on a real socket call and test authentic maps plus publication/response encoding.

Before this checkpoint, these helper tests ran on the host and in matched ARM64 emulation; the mapper/query were also tested with address/undefined-behavior sanitizers. The copied checkpoint source is rerun on the host before committing. These are distinct from the watched device results above, not a claim that the complete product is tested.

The repository README records the high-level goal and this checkpoint. Retained private logs support the device observations; raw transcripts, hardware identifiers, SSH routes, tokens, firmware binaries and disk images are not part of this commit.
