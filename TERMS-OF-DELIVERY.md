# Terms of delivery (read before pushing the repo):

## What this delivers (Phase 1)
Two **boot** images only. They run entirely from RAM:
- debug-boot.img     — tiny busybox shell + diagnostic output; proves kernel/DTB work on wayne hardware
- openwrt-boot.img   — full ImmortalWrt 21.02.7 userspace in RAM; no disk writes

Neither image contains a flashable recovery installer. The workflow produces raw boot.imgs via GitHub Actions; you load them with fastboot or flash a bootloader-backed recovery zip later when available. No userdata/system/vendor modifications at this stage.

## Boot loop safety
fastboot boot loads into RAM and executes without touching any partitions. If the new image fails, your phone reverts to Android. Still recommended to have a TWRP backup and original stock boot.img available for restore.

## How to push these files
The kit source is a minimal repo ready for `git clone` -> local edits -> `git commit` -> `git push`. Your Termux commands are at the bottom of README.md after you add them. I’ll package the current files as a ZIP including:
- .github/workflows/build.yml (workflow YAML)
- scripts/pack-boot.py       (packing helper; safe argument list)
- scripts/check-pack.py      (regression test script)
- kernel-config-fragment.txt (kernel config additions)
- overlay-openwrt/init       (/init wrapper for OpenWrt)
- overlay-debug/init         (/init for debug shell)
- README.md                  (docs)
- TERMUX-PUSH-COMMANDS.md    (your exact git commands)

Checksums provided inside the ZIP match the artifacts once built by CI. Do not upload prebuilt boot.img binaries to GitHub until the first build completes successfully.

## Limits / assumptions
- Wayne only (A-only partition layout). Not tested on A/B devices like Mi A2/jasmine.
- Requires LKGeek_sdm660 branch build-all-rekernel (4.19.x) as the kernel tree.
- Workflow downloads donor boot.img from Kernel_Action; it uses that header format.
- CPIO tool is used both in workflow and tests; both busybox and GNU cpio validated.

End goal (modem/router mode) will need USB gadget driver validation (CDC-ACM/g_serial), then RNDIS/NCM (USB ethernet), and finally ModemManager/uqmi over QMI/qrtr for mobile data. None of these steps depend on userdata writes at boot.
