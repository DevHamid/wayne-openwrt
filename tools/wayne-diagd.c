/*
 * wayne-diagd.c — /dev/diag drain daemon for the wayne (sdm660) OpenWrt build.
 *
 * WHY THIS EXISTS
 * --------------
 * The modem's DIAG task starves ("dog_hb: Task starvation: diag" -> ERR_FATAL,
 * ~90 s crash loop) when nothing on the AP holds /dev/diag open and drains it.
 * Stock Android keeps qcrild on it all boot. The earlier `cat /dev/diag`
 * drain worked on the adios-wayne kernel, but the v2 (LKGeek) kernel's
 * diagchar driver rejects a raw read until the message/log masks are set up:
 *   diag: In diag_copy_to_user_msg_mask Unable to send msg masks to user
 *         space clients, err: -22   (EINVAL)
 * A bare `cat` does no ioctl, so the driver has no mask session for the fd and
 * refuses the copy. This daemon performs the DIAG ioctl handshake the way
 * Android's qcrild / MobileInsight's diag_revealer do, then drains forever.
 *
 * Handshake reference:
 *   MobileInsight diag_revealer.c
 *   (github.com/mobile-insight/mobileinsight-mobile, BSD)
 *   msm kernel drivers/char/diag/diagchar_core.c + include/linux/diagchar.h
 *
 * SAFETY
 * ------
 * Read-only on the DIAG channel. Never touches EFS / modemst / calibration.
 * If any handshake ioctl fails we log it and keep draining anyway (best
 * effort) — a non-fatal handshake must not stop the anti-starvation drain,
 * because the drain is what keeps the modem alive.
 *
 * Build (aarch64, in CI or on-device with musl-gcc / OpenWrt SDK):
 *   cc -O2 -o wayne-diagd wayne-diagd.c
 * Run:
 *   wayne-diagd            (foreground; procd supervises)
 *   wayne-diagd -v         (verbose ioctl logging to stderr)
 */

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

/* ---- diagchar.h ioctl numbers (msm kernel, stable across 4.x) ---- */
#define DIAG_IOCTL_COMMAND_REG       0
#define DIAG_IOCTL_SWITCH_LOGGING    7
#define DIAG_IOCTL_LSM_DEINIT        9
#define DIAG_IOCTL_DCI_REG           23
#define DIAG_IOCTL_REMOTE_DEV        32

/* diag_ioctl_switch_logging_mode.request_mode values */
#define DIAG_USB_MODE                1
#define DIAG_MEMORY_DEVICE_MODE      2
#define DIAG_NO_LOGGING_MODE         3

/* DIAG_COMMAND_REG command types (write() framing) */
#define DIAG_CMD_IOCTL_SWITCH_LOGGING 1

#ifndef DIAG_MD_LOCAL
#define DIAG_MD_LOCAL 0
#endif

static int g_verbose = 0;

static void logmsg(const char *fmt, ...)
{
    va_list ap;
    char ts[32];
    time_t now = time(NULL);
    struct tm tmv;
    localtime_r(&now, &tmv);
    strftime(ts, sizeof(ts), "%H:%M:%S", &tmv);
    fprintf(stderr, "[%s] wayne-diagd: ", ts);
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    fflush(stderr);
}

#define vlog(...) do { if (g_verbose) logmsg(__VA_ARGS__); } while (0)

/* Best-effort: try an ioctl, log the outcome, never abort the drain. */
static void try_ioctl(int fd, unsigned long req, void *arg, const char *name)
{
    int ret = ioctl(fd, req, arg);
    if (ret < 0)
        logmsg("ioctl %s failed: %s (errno=%d) — continuing", name, strerror(errno), errno);
    else
        vlog("ioctl %s ok (ret=%d)", name, ret);
}

int main(int argc, char **argv)
{
    int fd;
    int remote_dev = 0;
    uint8_t buf[16384];

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-v")) g_verbose = 1;
        else if (!strcmp(argv[i], "-h")) {
            fprintf(stderr, "usage: %s [-v]\n", argv[0]);
            return 0;
        }
    }

    /* 1. Open read/write — DIAG handshake ioctls require O_RDWR. */
    fd = open("/dev/diag", O_RDWR);
    if (fd < 0) {
        logmsg("open /dev/diag failed: %s (errno=%d)", strerror(errno), errno);
        return 1;
    }
    vlog("opened /dev/diag fd=%d", fd);

    /* 2. Handshake. All best-effort: on some trees these succeed, on others
     *    they are no-ops. Either way the goal is a persistent drain. */

    /* 2a. Which remote device mask? 0 = local MSM (wayne is local). */
    try_ioctl(fd, DIAG_IOCTL_REMOTE_DEV, &remote_dev, "DIAG_IOCTL_REMOTE_DEV");

    /* 2b. Switch logging to MEMORY_DEVICE so the driver routes DIAG to the
     *     registered client (us) instead of expecting a USB host. Some trees
     *     want a 12-byte struct {req_mode, peripheral_mask, mode_param}; we
     *     zero it and set req_mode — the driver ignores trailing fields it
     *     does not know. */
    {
        struct {
            uint32_t req_mode;
            uint32_t peripheral_mask;
            uint8_t  mode_param;
            uint8_t  pad[16];   /* room for newer/larger structs */
        } mode;
        memset(&mode, 0, sizeof(mode));
        mode.req_mode = DIAG_MEMORY_DEVICE_MODE;
        mode.peripheral_mask = 0;      /* all peripherals */
        mode.mode_param = 0;
        try_ioctl(fd, DIAG_IOCTL_SWITCH_LOGGING, &mode, "DIAG_IOCTL_SWITCH_LOGGING");
    }

    /* 2c. Register a command client so the driver allocates a mask session
     *     for this fd. This is the step that clears the EINVAL on
     *     diag_copy_to_user_msg_mask. Payload is a DIAG_COMMAND_REG header;
     *     exact layout varies, so we send a minimal, driver-tolerated form. */
    {
        unsigned char cmdreg[16];
        memset(cmdreg, 0, sizeof(cmdreg));
        cmdreg[0] = DIAG_CMD_IOCTL_SWITCH_LOGGING; /* command type */
        try_ioctl(fd, DIAG_IOCTL_COMMAND_REG, cmdreg, "DIAG_IOCTL_COMMAND_REG");
    }

    /* 3. Drain forever. procd restarts us if we ever exit. */
    logmsg("draining /dev/diag");
    for (;;) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n < 0) {
            if (errno == EINTR || errno == EAGAIN) {
                usleep(10000);
                continue;
            }
            /* EFAULT/EINVAL here means masks still not ready — modem may
             * still be booting. Back off and retry; do NOT exit (exiting
             * would drop the anti-starvation hold). */
            vlog("read error: %s (errno=%d) — backoff", strerror(errno), errno);
            usleep(200000);
            continue;
        }
        /* bytes discarded — the point is to keep the channel flowing */
    }
    return 0;
}
