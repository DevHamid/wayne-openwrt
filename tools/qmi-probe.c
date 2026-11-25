/*
 * qmi-probe.c v2 — minimal QMI-over-QRTR probe for the wayne (sdm660) modem.
 * No external deps: raw AF_QIPCRTR socket + QMI ctl framing.
 *
 * Usage:
 *   qmi-probe            -> list discovered QMI services (per-service lookups)
 *   qmi-probe sim        -> DMS get-sim-status
 *   qmi-probe reg        -> NAS get-serving-system
 *   qmi-probe dbg        -> raw lookup debug (shows every ctrl reply)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <linux/qrtr.h>

#define QRTR_TYPE_NEW_SERVER 4
#define QRTR_TYPE_NEW_LOOKUP 10

struct ctrl_pkt {
	uint32_t cmd;
	struct {
		uint32_t service;
		uint32_t instance;
		uint32_t node;
		uint32_t port;
	} server;
};

#define QMI_SVC_WDS 1
#define QMI_SVC_DMS 2
#define QMI_SVC_NAS 3
#define QMI_SVC_UIM 23

struct svc {
	unsigned id;
	const char *name;
	unsigned instance;
	int node;
	int port;
};

static struct svc svcs[] = {
	{ QMI_SVC_WDS, "WDS", 0, -1, -1 },
	{ QMI_SVC_DMS, "DMS", 0, -1, -1 },
	{ QMI_SVC_NAS, "NAS", 0, -1, -1 },
	{ QMI_SVC_UIM, "UIM", 0, -1, -1 },
	{ 26,          "WDA", 0, -1, -1 },
	{ 49,          "IPACTL", 0, -1, -1 },
};

static int fd;
static int dbg;

static void die(const char *m) { perror(m); exit(1); }

/* one lookup for a single service; collects the NEW_SERVER replies */
static void lookup_one(struct svc *s)
{
	struct sockaddr_qrtr sq;
	socklen_t sl = sizeof(sq);
	struct ctrl_pkt pkt;
	struct timeval tv = { .tv_sec = 2, .tv_usec = 0 };
	int n;

	if (getsockname(fd, (struct sockaddr *)&sq, &sl) < 0)
		die("getsockname");
	memset(&pkt, 0, sizeof(pkt));
	pkt.cmd = QRTR_TYPE_NEW_LOOKUP;
	pkt.server.service = s->id;
	pkt.server.instance = 0;	/* (instance<<8)|version = 0 = any */

	sq.sq_port = -2;			/* QRTR_PORT_CTRL */
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
	if (sendto(fd, &pkt, sizeof(pkt), 0, (struct sockaddr *)&sq, sizeof(sq)) < 0) {
		if (dbg) printf("  lookup svc %u: sendto failed (%s)\n", s->id, strerror(errno));
		return;
	}
	while ((n = recv(fd, &pkt, sizeof(pkt), 0)) > 0) {
		if (dbg)
			printf("  rx cmd=%u svc=%u inst=%u node=%u port=%u\n",
			       pkt.cmd, pkt.server.service, pkt.server.instance,
			       pkt.server.node, pkt.server.port);
		if ((size_t)n < sizeof(pkt))
			continue;
		if (pkt.cmd != QRTR_TYPE_NEW_SERVER)
			continue;
		if (pkt.server.service == s->id) {
			s->node = pkt.server.node;
			s->port = pkt.server.port;
			s->instance = pkt.server.instance;
			break;	/* one server is enough */
		}
	}
}

static void lookup_all(void)
{
	fd = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
	if (fd < 0)
		die("socket(AF_QIPCRTR)");
	struct sockaddr_qrtr sq;
	socklen_t sl = sizeof(sq);
	if (getsockname(fd, (struct sockaddr *)&sq, &sl) == 0)
		printf("local qrtr node=%u port=%d\n", sq.sq_node, (int)sq.sq_port);
	/* bind like libqrtr's qrtr_open(): a real local port, so the NS can
	 * route replies back to us reliably */
	memset(&sq, 0, sizeof(sq));
	sq.sq_family = AF_QIPCRTR;
	sq.sq_node = 1;
	sq.sq_port = 0x4000;
	if (bind(fd, (struct sockaddr *)&sq, sizeof(sq)) < 0)
		perror("bind(0x4000)");
	if (getsockname(fd, (struct sockaddr *)&sq, &sl) == 0)
		printf("bound node=%u port=%u\n", sq.sq_node, sq.sq_port);
	for (unsigned i = 0; i < sizeof(svcs) / sizeof(svcs[0]); i++)
		lookup_one(&svcs[i]);
}

#define QMI_REQ  0x00
#define QMI_RESP 0x02

static uint16_t txn;

static int qmi_xchg(struct svc *s, uint16_t msgid,
		    const uint8_t *tlvs, size_t tlvlen,
		    uint8_t *resp, size_t respmax, int timeout_s)
{
	uint8_t req[512];
	struct sockaddr_qrtr dst, from;
	socklen_t fl = sizeof(from);
	struct timeval tv = { .tv_sec = timeout_s, .tv_usec = 0 };
	uint16_t want = ++txn;
	size_t need = 7 + tlvlen;
	ssize_t n;

	if (sizeof(req) < need)
		return -1;
	req[0] = QMI_REQ;
	req[1] = want & 0xff;
	req[2] = (want >> 8) & 0xff;
	req[3] = msgid & 0xff;
	req[4] = (msgid >> 8) & 0xff;
	req[5] = tlvlen & 0xff;
	req[6] = (tlvlen >> 8) & 0xff;
	if (tlvlen)
		memcpy(req + 7, tlvs, tlvlen);

	memset(&dst, 0, sizeof(dst));
	dst.sq_family = AF_QIPCRTR;
	dst.sq_node = s->node;
	dst.sq_port = s->port;
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
	if (sendto(fd, req, (int)need, 0, (struct sockaddr *)&dst, sizeof(dst)) < 0)
		return -1;
	while ((n = recvfrom(fd, resp, respmax, 0,
			     (struct sockaddr *)&from, &fl)) > 0) {
		if ((size_t)n < 7)
			continue;
		uint16_t rtxn = resp[1] | (resp[2] << 8);
		uint8_t type = resp[0];
		if (rtxn != want)
			continue;
		if (type != QMI_RESP && type != QMI_REQ)
			continue;
		return (int)n;
	}
	return -1;
}

static const uint8_t *qmi_tlv(const uint8_t *msg, size_t len, uint8_t want,
			      uint16_t *outlen)
{
	size_t tlvlen = msg[5] | (msg[6] << 8);
	const uint8_t *p = msg + 7;
	const uint8_t *end = msg + 7 + tlvlen;

	if (end > msg + len)
		end = msg + len;
	while (p + 3 <= end) {
		uint8_t t = p[0];
		uint16_t l = p[1] | (p[2] << 8);
		if (p + 3 + l > end)
			break;
		if (t == want) {
			*outlen = l;
			return p + 3;
		}
		p += 3 + l;
	}
	return NULL;
}

static void hexdump(const uint8_t *p, ssize_t n)
{
	printf("  raw (%zd bytes):", n);
	for (ssize_t i = 0; i < n && i < 160; i++) {
		if (i % 16 == 0)
			printf("\n   %04zx: ", i);
		printf("%02x ", p[i]);
	}
	printf("\n");
}

static void show_result(const uint8_t *r, ssize_t n)
{
	uint16_t l;
	const uint8_t *v = qmi_tlv(r, n, 0x02, &l);
	if (v && l >= 4)
		printf("  result: status=%u err=%u\n", v[0] | (v[1] << 8), v[2] | (v[3] << 8));
	else
		printf("  result: none\n");
}

static void do_sim(void)
{
	struct svc *s = &svcs[1];
	uint8_t resp[2048];
	ssize_t n = qmi_xchg(s, 0x0025, NULL, 0, resp, sizeof(resp), 4);

	printf("DMS get-sim-status (svc %u @ %d:%d):\n", s->id, s->node, s->port);
	if (n < 0) {
		printf("  no response (%s)\n", strerror(errno));
		return;
	}
	hexdump(resp, n);
	show_result(resp, n);
	uint16_t l;
	const uint8_t *v = qmi_tlv((const uint8_t *)resp, n, 0x01, &l);
	if (v && l >= 1) {
		const char *st[] = { "absent", "error", "unknown", "state-err", "ready", "busy", "locked" };
		printf("  sim_state=%u (%s)\n", v[0], v[0] < 7 ? st[v[0]] : "?");
	}
}

static void do_reg(void)
{
	struct svc *s = &svcs[2];
	uint8_t resp[2048];
	ssize_t n = qmi_xchg(s, 0x0024, NULL, 0, resp, sizeof(resp), 4);

	printf("NAS get-serving-system (svc %u @ %d:%d):\n", s->id, s->node, s->port);
	if (n < 0) {
		printf("  no response (%s)\n", strerror(errno));
		return;
	}
	hexdump(resp, n);
	show_result(resp, n);
	uint16_t l;
	const uint8_t *v = qmi_tlv((const uint8_t *)resp, n, 0x01, &l);
	if (v && l >= 3) {
		const char *rs[] = { "no-srv", "limited", "registered", "limited-reg", "unknown" };
		const char *ss[] = { "no-srv", "limited", "serving" };
		uint8_t reg = v[0], cs = v[1], ps = v[2];
		printf("  reg_state=%u (%s) cs=%s ps=%s\n", reg,
		       reg < 5 ? rs[reg] : "?", cs < 3 ? ss[cs] : "?", ps < 3 ? ss[ps] : "?");
		if (l >= 5)
			printf("  radio_if=%u roaming=%u\n", v[3], v[4]);
	}
}

static void do_list(void)
{
	printf("QRTR QMI services (node:port):\n");
	for (unsigned i = 0; i < sizeof(svcs) / sizeof(svcs[0]); i++)
		printf("  %-4s id=%-3u inst=%-3u @ %d:%d %s\n", svcs[i].name,
		       svcs[i].id, svcs[i].instance, svcs[i].node, svcs[i].port,
		       svcs[i].node < 0 ? "(not found)" : "");
}

static void do_raw(unsigned svc_id, unsigned msgid)
{
	struct svc *s = NULL;
	for (unsigned i = 0; i < sizeof(svcs) / sizeof(svcs[0]); i++)
		if (svcs[i].id == svc_id)
			s = &svcs[i];
	if (!s || s->node < 0) {
		printf("svc %u not found\n", svc_id);
		return;
	}
	uint8_t resp[4096];
	ssize_t n = qmi_xchg(s, (uint16_t)msgid, NULL, 0, resp, sizeof(resp), 5);
	printf("%s (svc %u @ %d:%d) msg 0x%04x:\n", s->name, s->id, s->node, s->port, msgid);
	if (n < 0) {
		printf("  no response (%s)\n", strerror(errno));
		return;
	}
	hexdump(resp, n);
}

/* WDS Start Network Interface (0x0020) — bring up an IPv4 data call */
static void do_wds_start(void)
{
	struct svc *s = &svcs[0];	/* WDS */
	uint8_t tlvs[64], resp[4096];
	size_t t = 0;
	ssize_t n;

	/* TLV 0x14: IP family preference, 4 bytes, value 4 = IPv4 */
	tlvs[t++] = 0x14; tlvs[t++] = 0x04; tlvs[t++] = 0x00;
	tlvs[t++] = 0x04; tlvs[t++] = 0x00; tlvs[t++] = 0x00; tlvs[t++] = 0x00;
	/* TLV 0x21: authentication preference = PAP|CHAP (1 byte mask = 3) */
	tlvs[t++] = 0x21; tlvs[t++] = 0x01; tlvs[t++] = 0x00;
	tlvs[t++] = 0x03;
	/* TLV 0x31: profile identifier = 3GPP profile #1 (1B type + 4B index) */
	tlvs[t++] = 0x31; tlvs[t++] = 0x05; tlvs[t++] = 0x00;
	tlvs[t++] = 0x00; tlvs[t++] = 0x01; tlvs[t++] = 0x00; tlvs[t++] = 0x00; tlvs[t++] = 0x00;
	/* TLV 0x01: APN omitted -> modem default */

	uint8_t req[64];
	size_t need = 7 + t;
	req[0] = QMI_REQ;
	req[1] = (txn + 1) & 0xff; req[2] = ((txn + 1) >> 8) & 0xff;
	req[3] = 0x20; req[4] = 0x00;	/* Start Network Interface */
	req[5] = t & 0xff; req[6] = (t >> 8) & 0xff;
	memcpy(req + 7, tlvs, t);
	txn++;

	struct sockaddr_qrtr dst, from;
	socklen_t fl = sizeof(from);
	struct timeval tv = { .tv_sec = 30, .tv_usec = 0 };
	memset(&dst, 0, sizeof(dst));
	dst.sq_family = AF_QIPCRTR;
	dst.sq_node = s->node; dst.sq_port = s->port;
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
	if (sendto(fd, req, (int)need, 0, (struct sockaddr *)&dst, sizeof(dst)) < 0) {
		printf("sendto failed: %s\n", strerror(errno));
		return;
	}
	printf("WDS Start Network sent (svc %u @ %d:%d), waiting for call setup...\n",
	       s->id, s->node, s->port);
	uint16_t want = txn;
	while ((n = recvfrom(fd, resp, sizeof(resp), 0,
			     (struct sockaddr *)&from, &fl)) > 0) {
		if ((size_t)n < 7) continue;
		uint16_t rtxn = resp[1] | (resp[2] << 8);
		if (rtxn != want) continue;
		break;
	}
	if (n <= 0) {
		printf("  no response (%s)\n", strerror(errno));
		return;
	}
	hexdump(resp, n);
	show_result(resp, n);
	uint16_t l;
	const uint8_t *v;
	if ((v = qmi_tlv(resp, n, 0x01, &l)) && l >= 4)
		printf("  call handle=%u\n", v[0] | (v[1]<<8) | (v[2]<<16) | ((unsigned)v[3]<<24));
	if ((v = qmi_tlv(resp, n, 0x12, &l)) && l >= 4)
		printf("  ipv4=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
	if ((v = qmi_tlv(resp, n, 0x15, &l)) && l >= 4)
		printf("  gw=%u.%u.%u.%u\n", v[0], v[1], v[2], v[3]);
}

int main(int argc, char **argv)
{
	dbg = (argc > 1 && !strcmp(argv[1], "dbg"));
	lookup_all();
	if (argc < 2 || !strcmp(argv[1], "list"))
		do_list();
	else if (!strcmp(argv[1], "sim"))
		do_sim();
	else if (!strcmp(argv[1], "reg"))
		do_reg();
	else if (!strcmp(argv[1], "dbg"))
		do_list();
	else if (!strcmp(argv[1], "raw") && argc >= 4)
		do_raw((unsigned)strtoul(argv[2], NULL, 0), (unsigned)strtoul(argv[3], NULL, 0));
	else if (!strcmp(argv[1], "start"))
		do_wds_start();
	else {
		fprintf(stderr, "usage: %s [list|sim|reg|dbg]\n", argv[0]);
		return 1;
	}
	return 0;
}
