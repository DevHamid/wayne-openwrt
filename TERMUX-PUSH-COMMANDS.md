# Termux push commands — v0.7 (donor control)

Your repo already exists. v0.7 is an UPDATE: it adds one new CI step
(`donor-control.img`) and one new artifact. Nothing else changes — the init
scripts and packer are byte-identical to what shipped in v0.6.

## 1. Download and unpack the kit

```bash
cd ~
rm -rf wayne-openwrt-tmp
mkdir -p wayne-openwrt-tmp
cd wayne-openwrt-tmp
unzip "$(find /storage/emulated/0 -name 'wayne-openwrt-v0.7.zip' 2>/dev/null | head -1)"
ls    # MUST show: .github  scripts  overlay-debug  overlay-openwrt  README.md ...
```

If `ls` does not show those folders/files, STOP — nothing was unpacked.

## 2. Copy the kit into your existing clone

```bash
cd ~
git clone https://github.com/DevHamid/wayne-openwrt.git repo
cp -r wayne-openwrt-tmp/. repo/
cd repo
git status    # should list build.yml, README.md as modified
```

## 3. Commit and push (this starts the build)

```bash
git add .
git commit -m "v0.7: add donor-control.img (pinned donor repack through our packer)"
git push origin main
git log --oneline -1    # MUST show: v0.7: add donor-control.img (pinned donor repack through our packer)
```

If `git log --oneline -1` does NOT show the v0.7 message, the push failed —
tell me before opening Actions.

## 4. Watch the build

https://github.com/DevHamid/wayne-openwrt/actions → run "Build OpenWrt Wayne".
Download artifact `wayne-openwrt` when green. It now contains:

- `donor-control.img`  — **TEST THIS ONE ONLY** (the control)
- debug-boot.img, openwrt-boot.img, bisect-*.img (from before — do NOT test yet)

## What you will NOT do in Termux

- no `make`, no toolchain — GitHub runs the build
- no flashing from Termux
