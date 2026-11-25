/* wayne-data.c — minimal QMI-over-QRTR data-call bring-up for the wayne (sdm660) built-in modem.
 * Commands:
 *   bind <mux>          WDS Bind Mux Data Port (0x00A2)
 *   start <apn> <prof>  WDS Start Network Interface (0x0020) with APN + profile + roaming allow
 *   stop                WDS Stop Network Interface (0x0021)
 *   settings            WDS Get Current Settings (0x0024)
 *   fmt <ll>            WDA Set Data Format (0x0020)
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <linux/qrtr.h>

#define QRTR_TYPE_NEW_SERVER 4
#define QRTR_TYPE_NEW_LOOKUP 10
#define QMI_SVC_WDS 1
#define QMI_SVC_WDA 26

static int fd;
static unsigned txn = 0;

struct qrtr_server {
    uint32_t service;
    uint32_t instance;
    uint32_t node;
    uint32_t port;
};
struct ctrl_pkt {
    uint32_t cmd;
    struct qrtr_server server;
};

static void hexdump(const uint8_t *b, ssize_t n) {
    for (ssize_t i = 0; i < n; i += 16) {
        printf("   %04zx:", i);
        for (ssize_t j = i; j < i + 16 && j < n; j++) printf(" %02x", b[j]);
        printf("\n");
    }
}

static int lookup_svc(unsigned id, int *node, int *port) {
    struct sockaddr_qrtr sq;
    socklen_t sl = sizeof(sq);
    struct ctrl_pkt pkt;
    struct timeval tv = { .tv_sec = 3 };
    if (getsockname(fd, (struct sockaddr *)&sq, &sl) < 0) return -1;
    memset(&sq, 0, sizeof(sq));
    sq.sq_family = AF_QIPCRTR;
    sq.sq_node = 1;
    sq.sq_port = QRTR_PORT_CTRL;
    memset(&pkt, 0, sizeof(pkt));
    pkt.cmd = QRTR_TYPE_NEW_LOOKUP;
    pkt.server.service = id;
    pkt.server.instance = 0;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    if (sendto(fd, &pkt, sizeof(pkt), 0, (struct sockaddr *)&sq, sizeof(sq)) < 0) return -1;
    for (;;) {
        ssize_t n = recv(fd, &pkt, sizeof(pkt), 0);
        if (n <= 0) return -1;
        if (n < (ssize_t)sizeof(pkt)) continue;
        if (pkt.cmd != QRTR_TYPE_NEW_SERVER) continue;
        if (pkt.server.service != id) continue;
        *node = (int)pkt.server.node;
        *port = (int)pkt.server.port;
        return 0;
    }
}

static ssize_t xchg(int svc, int node, int port, uint16_t msgid,
                    const uint8_t *tlvs, size_t tl, uint8_t *resp, size_t rl, int timeout_s) {
    uint8_t req[1024];
    size_t need = 7 + tl;
    unsigned t = ++txn;
    req[0] = 0x00;
    req[1] = t & 0xff; req[2] = (t >> 8) & 0xff;
    req[3] = msgid & 0xff; req[4] = (msgid >> 8) & 0xff;
    req[5] = tl & 0xff; req[6] = (tl >> 8) & 0xff;
    if (tl) memcpy(req + 7, tlvs, tl);
    struct sockaddr_qrtr dst = { .sq_family = AF_QIPCRTR, .sq_node = node, .sq_port = port };
    struct timeval tv = { .tv_sec = timeout_s };
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    if (sendto(fd, req, need, 0, (struct sockaddr *)&dst, sizeof(dst)) < 0) return -1;
    for (;;) {
        struct sockaddr_qrtr from; socklen_t fl = sizeof(from);
        ssize_t n = recvfrom(fd, resp, rl, 0, (struct sockaddr *)&from, &fl);
        if (n <= 0) return n;
        if ((size_t)n < 7) continue;
        if ((resp[1] | (resp[2] << 8)) != t) continue;
        return n;
    }
    (void)svc;
}

static const uint8_t *tlv(const uint8_t *r, ssize_t n, uint8_t type, uint16_t *len) {
    ssize_t i = 7;
    while (i + 3 <= n) {
        uint8_t t = r[i];
        uint16_t l = r[i + 1] | (r[i + 2] << 8);
        if (i + 3 + l > n) return NULL;
        if (t == type) { *len = l; return r + i + 3; }
        i += 3 + l;
    }
    return NULL;
}

static void show_result(const uint8_t *r, ssize_t n) {
    uint16_t l; const uint8_t *v = tlv(r, n, 0x02, &l);
    if (v && l >= 4) printf("  result: status=%u err=%u\n", v[0] | (v[1] << 8), v[2] | (v[3] << 8));
    else printf("  no result TLV\n");
}

static int wds_node, wds_port;

static int do_bind(unsigned mux) {
    uint8_t tl[64], resp[2048]; size_t t = 0;
    /* TLV 0x10 Endpoint Info: u32 endpoint type (2 = AP), u32 interface id (0) */
    tl[t++] = 0x10; tl[t++] = 8; tl[t++] = 0;
    uint32_t vals[2] = { 2, 0 };
    memcpy(tl + t, vals, 8); t += 8;
    /* TLV 0x11 Mux Id */
    tl[t++] = 0x11; tl[t++] = 1; tl[t++] = 0; tl[t++] = (uint8_t)mux;
    ssize_t n = xchg(QMI_SVC_WDS, wds_node, wds_port, 0x00A2, tl, t, resp, sizeof(resp), 15);
    printf("WDS Bind Mux Data Port (mux=0x%02x):\n", mux);
    if (n <= 0) { printf("  no response (%s)\n", strerror(errno)); return -1; }
    hexdump(resp, n); show_result(resp, n);
    return 0;
}

static int do_start(const char *apn, unsigned prof) {
    uint8_t tl[128], resp[4096]; size_t t = 0;
    /* 0x14 IP family = IPv4 */
    tl[t++] = 0x14; tl[t++] = 4; tl[t++] = 0; tl[t++] = 4; tl[t++] = 0; tl[t++] = 0; tl[t++] = 0;
    /* 0x19 roaming preference = 1 (allow) */
    tl[t++] = 0x19; tl[t++] = 1; tl[t++] = 0; tl[t++] = 1;
    /* 0x31 profile index (3GPP): 1B type=0 + 2B index */
    tl[t++] = 0x31; tl[t++] = 3; tl[t++] = 0; tl[t++] = 0; tl[t++] = (uint8_t)prof; tl[t++] = 0;
    if (apn && *apn) { /* 0x01 APN */
        size_t al = strlen(apn);
        tl[t++] = 0x01; tl[t++] = (uint8_t)al; tl[t++] = 0;
        memcpy(tl + t, apn, al); t += al;
    }
    ssize_t n = xchg(QMI_SVC_WDS, wds_node, wds_port, 0x0020, tl, t, resp, sizeof(resp), 45);
    printf("WDS Start Network (apn=%s prof=%u):\n", (apn && *apn) ? apn : "(default)", prof);
    if (n <= 0) { printf("  no response (%s)\n", strerror(errno)); return -1; }
    hexdump(resp, n); show_result(resp, n);
    uint16_t l; const uint8_t *v;
    if ((v = tlv(resp, n, 0x01, &l)) && l >= 4)
        printf("  call handle=%u\n", v[0] | (v[1] << 8) | (v[2] << 16) | ((unsigned)v[3] << 24));
    if ((v = tlv(resp, n, 0x12, &l)) && l >= 4) printf("  ipv4=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    if ((v = tlv(resp, n, 0x15, &l)) && l >= 4) printf("  gw=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    if ((v = tlv(resp, n, 0x1E, &l)) && l >= 4) printf("  dns1=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    return 0;
}

static int do_settings(void) {
    uint8_t resp[4096];
    ssize_t n = xchg(QMI_SVC_WDS, wds_node, wds_port, 0x0024, NULL, 0, resp, sizeof(resp), 15);
    printf("WDS Get Current Settings:\n");
    if (n <= 0) { printf("  no response (%s)\n", strerror(errno)); return -1; }
    hexdump(resp, n); show_result(resp, n);
    uint16_t l; const uint8_t *v;
    if ((v = tlv(resp, n, 0x1E, &l)) && l >= 4) printf("  ipv4=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    if ((v = tlv(resp, n, 0x20, &l)) && l >= 4) printf("  gw=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    if ((v = tlv(resp, n, 0x21, &l)) && l >= 4) printf("  dns1=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
    return 0;
}

static int do_fmt(void) {
    int node, port;
    if (lookup_svc(QMI_SVC_WDA, &node, &port) < 0) { printf("WDA not found\n"); return -1; }
    uint8_t tl[64], resp[2048]; size_t t = 0;
    /* 0x10 link layer protocol = 4 (RMNET) ; 0x11 uplink aggregation = 1 ; 0x12 downlink = 1 */
    tl[t++] = 0x10; tl[t++] = 1; tl[t++] = 0; tl[t++] = 4;
    tl[t++] = 0x11; tl[t++] = 1; tl[t++] = 0; tl[t++] = 1;
    tl[t++] = 0x12; tl[t++] = 1; tl[t++] = 0; tl[t++] = 1;
    tl[t++] = 0x13; tl[t++] = 4; tl[t++] = 0; tl[t++] = 1; tl[t++] = 0; tl[t++] = 0; tl[t++] = 0;
    ssize_t n = xchg(QMI_SVC_WDA, node, port, 0x0020, tl, t, resp, sizeof(resp), 15);
    printf("WDA Set Data Format:\n");
    if (n <= 0) { printf("  no response (%s)\n", strerror(errno)); return -1; }
    hexdump(resp, n); show_result(resp, n);
    return 0;
}

int main(int argc, char **argv) {
    fd = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
    if (fd < 0) { perror("socket"); return 1; }
    struct sockaddr_qrtr sa = { .sq_family = AF_QIPCRTR, .sq_node = 0, .sq_port = 0 };
    bind(fd, (struct sockaddr *)&sa, sizeof(sa));
    if (lookup_svc(QMI_SVC_WDS, &wds_node, &wds_port) < 0) { printf("WDS not found\n"); return 1; }
    printf("WDS @ %d:%d\n", wds_node, wds_port);
    if (argc < 2) { printf("usage: %s bind <mux> | start <apn> <prof> | settings | fmt\n", argv[0]); return 1; }
    if (!strcmp(argv[1], "bind")) return do_bind((unsigned)strtoul(argc > 2 ? argv[2] : "0", NULL, 0));
    if (!strcmp(argv[1], "start")) return do_start(argc > 2 ? argv[2] : "", (unsigned)strtoul(argc > 3 ? argv[3] : "1", NULL, 0));
    if (!strcmp(argv[1], "settings")) return do_settings();
    if (!strcmp(argv[1], "fmt")) return do_fmt();
    printf("unknown command\n");
    return 1;
}
