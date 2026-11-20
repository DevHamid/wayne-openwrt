# Wayne AP-side registry checkpoint

This is a source checkpoint of the tested registry startup milestone, not a finished pocket-modem release. The normal ROM assembler does **not** install these files automatically. Experimental TFTP work, live activation runners, private transcripts, credentials and compiled binaries are not included.

## Runtime layout

- `wayne-qrtr.init` -> `/etc/init.d/wayne-qrtr` (0755): S11 start / K89 stop.
- `wayne-pd-mapper.init` -> `/etc/init.d/wayne-pd-mapper` (0755): S12 start / K88 stop.
- Shared shell helpers, `qrtr-ns`, `qrtr-lookup`, adapted `pd-mapper`, and `locator-query` -> `/usr/lib/wayne/radio/`.
- Authentic `MODEMUW.JSN` / `MODEMR.JSN` from the existing firmware set -> `/usr/share/wayne/pd-maps/`.
- The tested static BusyBox timeout helper must already be `/bin/busybox-static`.

The upstream mapper expects remoteproc. Wayne uses vendor PIL without that class, so `mapper/vendor-pil-mapdir.patch` adds an explicit directory (`-d`) and validation-only (`-n`) path. Both uppercase firmware map names and compressed maps are supported. Source is pinned to linux-msm/pd-mapper `5ecd2fe926aca7abfe40724177f63b942cff3947`; the original license is retained under `mapper/UPSTREAM-LICENSE`.

The fixed query client accepts a port, but has no arbitrary node, QMI service or payload option: it sends only the fixed AP-local `wlan/fw` registry read, once, validates sender/header/TLV/domain fields, and closes. The startup helper selects its port only from the expected local locator tuple.

## Startup and safety

Each service uses a foreground procd `main` instance. Nameserver readiness requires a completed local discovery response without requiring the modem to be online. Mapper startup validates maps, waits for the exact locator tuple, then requires a validated domain response. Polling is bounded; a failed application query is not replayed. A readiness failure stops only the caller's named instance. Unattended respawn is intentionally disabled.

The registry scripts do not acquire the modem, change rmtfs, enable dumps, change provisioning, or set up Wi-Fi. Keep `option allow_boot '0'` unchanged. For deployment, back up/refuse existing destinations, retain the current boot image and a reachable recovery route, and verify USB/rmtfs/modem policy before and after the additive install. If recovery is necessary, removing the two new S11/S12 startup links disables registry startup; no formatting or kernel replacement is required for that rollback.

`EVIDENCE.md` separates observed boot results from open gates. Rebuilding a helper elsewhere does not automatically validate that new binary on hardware.

## Offline tests and builds

Prerequisites: Linux C compiler/UAPI headers, Python 3 with its lzma module, Git, and liblzma development headers/library. These build **userspace only**, never a kernel.

From the repository root:

```sh
python3 modem/registry/test_init.py
mkdir -p modem/registry/build
cc -std=gnu11 -O2 -Wall -Wextra -Werror modem/registry/locator_query.c \
  -o modem/registry/build/locator-query
cc -std=gnu11 -O2 -Wall -Wextra -Werror -Wno-unused-parameter \
  modem/registry/query_fixture.c \
  -Wl,--wrap=socket,--wrap=sendto,--wrap=poll,--wrap=recvfrom,--wrap=close \
  -o modem/registry/build/query-fixture
python3 modem/registry/test_query.py
```

Prepare the pinned upstream sources in ignored build directories:

```sh
git clone https://github.com/linux-msm/pd-mapper.git modem/registry/mapper/source
git -C modem/registry/mapper/source checkout --detach 5ecd2fe926aca7abfe40724177f63b942cff3947
git -C modem/registry/mapper/source apply ../vendor-pil-mapdir.patch
git clone https://github.com/linux-msm/qrtr.git modem/registry/build/qrtr
git -C modem/registry/build/qrtr checkout --detach 6d950d26e50d9ea3607510308fdd653bccc54400
python3 modem/registry/mapper/build_userspace.py --qrtr-source modem/registry/build/qrtr
python3 modem/registry/mapper/test_mapper.py
```

The mapper build also accepts `--cc`, `--static`, `--sanitize`, `--lzma-include`, and `--lzma-library`. The last two support an unpacked development package or a cross sysroot without installing anything on the build host. Follow the user's kernel-CI-only constraint separately: this helper builder does not build or change a kernel.

The tests default to the socket-intercepting fixtures, not a live daemon. They exercise malformed/truncated responses, argument and map refusal, socket closure, no retry, and startup failure/cleanup with fake procd calls. `TRACE_TEST_SHELL` / `TRACE_TEST_APPLETS`, `LOCATOR_RUNNER` / `LOCATOR_FIXTURE`, and `PD_MAPPER_RUNNER` / `PD_MAPPER_TEST_BINARY` / `PD_MAPPER_FIXTURE` select explicit emulation wrappers and test binaries. These tests are not instructions to run an old radio window on the phone.
