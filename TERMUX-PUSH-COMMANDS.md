# Termux push commands — v0.9 (eMMC persistent rootfs installer)

v0.9 adds a **self-installing** boot image. First boot it formats
`/dev/mmcblk0p64` (userdata), copies OpenWrt onto it, and boots from eMMC.
Every later boot just boots — the install runs at most once.

Changed/added:
- `scripts/pack-boot-root.py`   (NEW — cmdline-override packer)
- `overlay-installer/init`      (NEW — the installer)
- `.github/workflows/build.yml` (2 new steps; all v0.8 steps unchanged)

## 1. Download and unpack

```bash
cd ~
rm -rf wayne-openwrt-tmp
mkdir -p wayne-openwrt-tmp
cd wayne-openwrt-tmp
unzip "$(find /storage/emulated/0 -name 'wayne-openwrt-v0.9.zip' 2>/dev/null | head -1)"
ls -a    # MUST show: .github  scripts  overlay-installer  kernel-config-fragment.txt
```

## 2. Copy into your clone

```bash
cd ~
git clone https://github.com/DevHamid/wayne-openwrt.git repo
cp -r wayne-openwrt-tmp/. repo/
cd repo
git status    # should list the new files + build.yml as modified
```

## 3. Commit and push

```bash
git add .
git commit -m "v0.9: eMMC persistent rootfs installer (self-installing, one-shot)"
git push origin main
git log --oneline -1    # MUST show the v0.9 message
```

## 4. Watch the build

Actions -> "Build OpenWrt Wayne". Confirm the config-dump step still shows
`PASS: CONFIG_EXTCON=y`. Artifacts now include `installer-boot.img`.

## 5. THE INSTALL (read first)

**This image WRITES to /dev/mmcblk0p64 and destroys the Android data on it.**
You approved this (test phone). Nothing else is touched.

1. `fastboot boot installer-boot.img`
2. Watch the serial console. You will see:
   ```
   installer: target           : /dev/mmcblk0p64
   installer: target name      : userdata
   installer: target size      : <N> GiB
   installer: *** FORMATTING /dev/mmcblk0p64 (userdata) ... ***
   installer: copying live rootfs -> /mnt/target ...
   installer: install complete -- marker written
   installer: switch_root -> /mnt/target /sbin/init
   ```
3. You then land in the normal OpenWrt shell — but now running from eMMC.
4. `df -h /` should show ~49 GB, NOT a small ramdisk.

Re-running `fastboot boot installer-boot.img` is safe: the marker is found and
the install is skipped.

## 6. If a guard trips

The installer refuses to write and drops to a shell. Expected messages:
```
FATAL -- /dev/mmcblk0p64 is not a block device
FATAL -- /dev/mmcblk0p64 is only N GiB -- refusing
FATAL -- /dev/mmcblk0p64 PARTNAME is 'X', expected 'userdata'
```
Send me the exact line; nothing was written.

## Safety
- Only `userdata` (p64) is ever formatted. One format call, guarded four ways.
- Still `sync && umount -a -r` before poweroff on any RAM-only boot.
