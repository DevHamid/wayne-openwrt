# Termux push commands (run these on your tablet)

These five commands move the kit from the ZIP into GitHub and start the first build.
You never run a heavy compile here — Termux only moves files and talks to GitHub.

## 1. Install git (once)

Vanilla Termux uses `pkg`; inside a proot/chroot distro (root@…) use `apt-get`:

```bash
pkg install git unzip || apt-get install -y git unzip
```

## 2. Download and unpack the kit

```bash
cd ~
mkdir -p wayne-openwrt-tmp
cd wayne-openwrt-tmp
# the ZIP you saved from Telegram — adjust the path if it landed elsewhere
unzip ~/storage/downloads/wayne-openwrt-v0.6.zip
```

## 3. Clone YOUR empty repo, then copy the kit in

```bash
cd ~
git clone https://github.com/DevHamid/wayne-openwrt.git repo
cp -r wayne-openwrt-tmp/. repo/
cd repo
```

## 4. Check what git sees (no upload yet — just looking)

```bash
git status
```

You should see the kit files listed as untracked:
`.github/workflows/build.yml`, `scripts/`, `overlay-openwrt/`, `overlay-debug/`,
`kernel-config-fragment.txt`, `README.md`, `TERMS-OF-DELIVERY.md`.

## 5. Commit and push (this starts the build)

```bash
git add .
git commit -m "First kit: OpenWrt-on-wayne Phase 1 (RAM boot image)"
git push -u origin main
```

If git asks for credentials: enter your GitHub username + a
[personal access token](https://github.com/settings/tokens) (scope `repo`)
as the password.

## Watch the build

Open https://github.com/DevHamid/wayne-openwrt/actions — the run "Build OpenWrt
Wayne" should appear. It takes ~20–40 minutes (kernel compile). When the green
check appears, download the `wayne-openwrt` artifact:

- `debug-boot.img`    — tiny shell, proves kernel boots
- `openwrt-boot.img`  — full ImmortalWrt in RAM

## What you will NOT do in Termux

- no `make`, no toolchain, no `apt install clang` — GitHub runs that
- no flashing from Termux — flashing happens on a PC via fastboot/TWRP later
