# Modem service table baseline — 2026-11-21

Read-only `qrtr-lookup` enumeration on the running image (modem ONLINE, crash
count 0). No modem operation, no provider, no writes. Raw capture:
`service-table.txt` in the analysis workspace; summary below is derived from it
by parsing every row, not by eye.

## Topology

`qrtr-lookup` with no argument dumps the whole nameserver table. Node **0** is
the modem (DMS/NAS/WDS/UIM/PDC/EFS/…), node **1** is the AP (DIAG transports,
servreg locator, RFS, DHMS).

| Node | Services |
|---|---|
| 0 (modem) | 40 |
| 1 (AP) | 26 |
| **Total rows** | **66** |

## Presence checks

| Service | Name | Result |
|---|---|---|
| 69 | WLFW | **ABSENT** |
| 66 | Service registry notification | present, node 0, instance 180, port 1 |
| 43 | Subsystem control (ssctl) | present, node 0, instance 18, port 4 |
| 64 | Service registry locator | present, node 1 (AP) |
| 14 | Remote file system (RFS) | present, node 1 (AP) |
| 52 | Dynamic heap memory sharing | present, node 1 (AP) |
| 4096 | TFTP firmware transport | absent (no provider running at capture time) |

The modem publishes 40 QMI services including Device Management (2), Network
Access (3), Wireless Data (1), UIM (11), PDC (36), EFS (21) and Subsystem
Control (43).

## What this corrects and what it establishes

- **Correction:** an earlier note recorded that the post-power-up table
  "contains 66 … and no 69". That was a filtered observation, not a full table.
  The modem actually publishes 40 services; the claim is corrected here.
- The modem-side QRTR stack, PD accounting for the normal services, and the
  modem→AP link are all healthy. The missing WLAN pieces are **specific** to
  `wlan_pd`, not a symptom of a broken modem subsystem.
- No service on the modem advertises itself as a PD/loader trigger (no
  `tms`/`elf_loader`/`peripheral` entry at node 0), so there is no obvious
  modem-side QMI opoint to ask for a PD start.

## Not established

Why `wlan_pd` is not spawned. This table records absence, not cause. It also
does not show services that exist only while the WLAN PD is running.
