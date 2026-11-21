// SPDX-License-Identifier: GPL-2.0
/*
 * pdr_restart — send one SERVREG_NOTIF restart-PD request.
 *
 * Mirrors what the vendor kernel's icnss_trigger_recovery() does through
 * service_notif_pd_restart(): a QMI request to service 0x42 (66) carrying the
 * PD path in a single TLV. No library dependency: raw AF_QIPCRTR datagram.
 *
 * QMI wire format (7-byte packed header, this vendor kernel's struct qmi_header):
 *   [0] type  [1..2] transaction (LE)  [3..4] message id (LE)  [5..6] length (LE)
 * then TLVs: [type][length LE16][value]
 *
 * RESTART_PD_REQ (0x0024): TLV 0x01 = service_name (<=64 bytes, no NUL)
 * RESTART_PD_RESP (0x0024): TLV 0x02 = result { u16 result, u16 error }
 */
#define _GNU_SOURCE
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <signal.h>
#include <limits.h>
#include <sys/time.h>
#include <unistd.h>

#ifndef AF_QIPCRTR
#define AF_QIPCRTR 42
#endif

struct sockaddr_qrtr {
	/* Must match the kernel's __kernel_sa_family_t (u16): a narrower field
	 * leaves the high byte as padding, which the kernel reads as part of
	 * sq_family and rejects with EINVAL before any packet is sent. */
	unsigned short sq_family;
	unsigned int sq_node;
	unsigned int sq_port;
};

#define MSG_RESTART_PD		0x0024
#define PD_NAME_MAX		64
#define HDR_LEN			7
#define QMI_RESPONSE		0x02
#define TLV_HDR_LEN		3
#define TLV_SERVICE_NAME	0x01
#define TLV_RESULT		0x02

static int build_request(uint8_t *buf, size_t cap, uint8_t txn, const char *name)
{
	size_t n = strlen(name), total, payload;

	if (n == 0 || n > PD_NAME_MAX)
		return -1;
	payload = TLV_HDR_LEN + n;
	total = HDR_LEN + payload;
	if (total > cap)
		return -1;

	buf[0] = 0;
	buf[1] = txn & 0xff;
	buf[2] = (txn >> 8) & 0xff;
	buf[3] = MSG_RESTART_PD & 0xff;
	buf[4] = (MSG_RESTART_PD >> 8) & 0xff;
	buf[5] = payload & 0xff;
	buf[6] = (payload >> 8) & 0xff;
	buf[7] = TLV_SERVICE_NAME;
	buf[8] = n & 0xff;
	buf[9] = (n >> 8) & 0xff;
	memcpy(buf + HDR_LEN + TLV_HDR_LEN, name, n);
	return (int)total;
}

/* Returns 0 when the buffer is a usable response for txn. */
static int parse_response(const uint8_t *b, size_t len, uint8_t txn,
			  int *result, int *error)
{
	size_t off, payload;
	unsigned int msg_id;
	int found = 0;

	if (len < HDR_LEN + TLV_HDR_LEN + 4)
		return -EINVAL;
	if (b[0] != QMI_RESPONSE)
		return -EPROTO;
	if ((((unsigned int)b[1] | ((unsigned int)b[2] << 8))) != txn)
		return -EPROTO;
	msg_id = (unsigned int)b[3] | ((unsigned int)b[4] << 8);
	if (msg_id != MSG_RESTART_PD)
		return -EPROTO;
	payload = (size_t)b[5] | ((size_t)b[6] << 8);
	if (payload + HDR_LEN != len)
		return -EPROTO;

	for (off = HDR_LEN; off + TLV_HDR_LEN <= HDR_LEN + payload;) {
		uint8_t type = b[off];
		size_t tlv_len = (size_t)b[off + 1] | ((size_t)b[off + 2] << 8);

		if (off + TLV_HDR_LEN + tlv_len > HDR_LEN + payload)
			return -EPROTO;
		if (type == TLV_RESULT) {
			if (tlv_len != 4 || found)
				return -EPROTO;
			*result = b[off + 3] | (b[off + 4] << 8);
			*error = b[off + 5] | (b[off + 6] << 8);
			found = 1;
		}
		off += TLV_HDR_LEN + tlv_len;
	}
	if (off != len)
		return -EPROTO;
	return found ? 0 : -ENOENT;
}

static void print_hex(const uint8_t *b, size_t n)
{
	size_t i;

	for (i = 0; i < n; i++)
		printf("%02x", b[i]);
	printf("\n");
}

static int hex_to_bytes(const char *hex, uint8_t *out, size_t cap)
{
	size_t n = strlen(hex), i;

	if (n == 0 || n % 2 || n / 2 > cap)
		return -1;
	for (i = 0; i < n / 2; i++) {
		unsigned int v;
		if (sscanf(hex + 2 * i, "%2x", &v) != 1)
			return -1;
		out[i] = (uint8_t)v;
	}
	return (int)(n / 2);
}

static int do_send(unsigned int node, unsigned int port, const char *name)
{
	uint8_t req[128], resp[256];
	struct sockaddr_qrtr addr;
	struct timeval tv = { .tv_sec = 2, .tv_usec = 0 };
	int fd, len, result = -1, error = -1, rc;
	ssize_t n;

	memset(&addr, 0, sizeof(addr));
	addr.sq_family = AF_QIPCRTR;
	addr.sq_node = node;
	addr.sq_port = port;

	len = build_request(req, sizeof(req), 0x01, name);
	if (len < 0) {
		fprintf(stderr, "invalid PD name\n");
		return 2;
	}

	fd = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
	if (fd < 0) {
		perror("socket(AF_QIPCRTR)");
		return 3;
	}
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

	if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
		perror("connect");
		close(fd);
		return 4;
	}
	if (send(fd, req, (size_t)len, 0) != len) {
		perror("send");
		close(fd);
		return 5;
	}
	printf("request_sent=yes node=%u port=%u pd=%s bytes=%d\n", node, port,
	       name, len);

	n = recv(fd, resp, sizeof(resp), 0);
	close(fd);
	if (n < 0) {
		printf("response=timeout errno=%d\n", errno);
		return 6;
	}
	printf("response_bytes=%zd\n", n);
	rc = parse_response(resp, (size_t)n, 0x01, &result, &error);
	if (rc < 0) {
		printf("response_parse=failed rc=%d raw=", rc);
		print_hex(resp, (size_t)n);
		return 7;
	}
	printf("response_parse=ok qmi_result=%d qmi_error=%d\n", result, error);
	return result == 0 ? 0 : 8;
}

static int build_listener(uint8_t *buf, size_t cap, const char *name)
{
	int n = build_request(buf, cap, 1, name);
	if (n < 0 || (size_t)n + 4 > cap)
		return -1;
	memmove(buf + 11, buf + 7, (size_t)n - 7);
	buf[3] = 0x20;
	buf[5] += 4;
	buf[7] = 1; buf[8] = 1; buf[9] = 0; buf[10] = 1;
	buf[11] = 2;
	return n + 4;
}

static int provider_alive(pid_t pid, const char *exe)
{
	char path[64], actual[PATH_MAX];
	ssize_t n;
	if (pid <= 1 || exe[0] != '/' || kill(pid, 0) < 0)
		return 0;
	snprintf(path, sizeof(path), "/proc/%ld/exe", (long)pid);
	n = readlink(path, actual, sizeof(actual) - 1);
	if (n < 0)
		return 0;
	actual[n] = 0;
	return !strcmp(actual, exe);
}

/* No retry and no extra requests: close the listener on every exit path. */
static int do_listen_restart(unsigned int node, unsigned int port,
			     const char *name, pid_t pid, const char *exe)
{
	uint8_t req[128], response[256];
	struct sockaddr_qrtr addr = {0};
	struct timeval tv = { .tv_sec = 2 };
	int fd = -1, rc = 3, len, result, error;
	ssize_t n;
	if (!provider_alive(pid, exe)) {
		printf("provider_alive=no stage=before_listener\n");
		return 9;
	}
	len = build_listener(req, sizeof(req), name);
	if (len < 0)
		return 2;
	addr.sq_family = AF_QIPCRTR; addr.sq_node = node; addr.sq_port = port;
	fd = socket(AF_QIPCRTR, SOCK_DGRAM, 0);
	if (fd < 0)
		return 3;
	if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0 ||
	    connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0)
		goto out;
	for (int stage = 0; stage < 2; stage++) {
		const char *label = stage ? "restart" : "listener";
		if (stage) {
			if (!provider_alive(pid, exe)) {
				printf("provider_alive=no stage=before_restart\n");
				rc = 9; goto out;
			}
			printf("provider_alive=yes stage=before_restart\n");
			len = build_request(req, sizeof(req), 2, name);
		}
		printf("request_attempt=%s txn=%d\n", label, stage + 1);
		if (send(fd, req, (size_t)len, 0) != len) { rc = 5; goto out; }
		printf("request_sent=%s bytes=%d\n", label, len);
		n = recv(fd, response, sizeof(response), 0);
		if (n < 0) { printf("response=%s timeout_or_error=%d\n", label, errno); rc = 6; goto out; }
		printf("response_frame=%s hex=", label);
		print_hex(response, (size_t)n);
		/* Reuse the strict restart decoder only after checking this stage's ids. */
		if (n < HDR_LEN || response[1] != stage + 1 || response[2] ||
		    response[3] != (stage ? 0x24 : 0x20) || response[4] ||
		    (size_t)n != HDR_LEN + (size_t)response[5] + ((size_t)response[6] << 8)) {
			printf("response=%s parse=rejected\n", label); rc = 7; goto out;
		}
		response[1] = 1; response[3] = 0x24;
		if (parse_response(response, (size_t)n, 1, &result, &error) < 0) {
			printf("response=%s parse=rejected\n", label); rc = 7; goto out;
		}
		printf("response=%s qmi_result=%d qmi_error=%d\n", label, result, error);
		if (result || error) { rc = 8; goto out; }
	}
	rc = 0;
out:
	close(fd);
	printf("listener_socket=closed\n");
	return rc;
}

int main(int argc, char **argv)
{
	uint8_t buf[256];
	int n, result = -1, error = -1, rc;

	if (argc == 3 && !strcmp(argv[1], "--packet")) {
		n = build_request(buf, sizeof(buf), 0x01, argv[2]);
		if (n < 0)
			return 2;
		print_hex(buf, (size_t)n);
		return 0;
	}
	if (argc == 3 && !strcmp(argv[1], "--parse")) {
		n = hex_to_bytes(argv[2], buf, sizeof(buf));
		if (n < 0)
			return 2;
		rc = parse_response(buf, (size_t)n, 0x01, &result, &error);
		if (rc < 0) {
			printf("parse=rejected rc=%d\n", rc);
			return 3;
		}
		printf("parse=ok qmi_result=%d qmi_error=%d\n", result, error);
		return 0;
	}
	if (argc == 7 && !strcmp(argv[1], "--listen-restart")) {
		char *end;
		unsigned long node, port, pid;
		errno = 0; node = strtoul(argv[2], &end, 0);
		if (errno || *end || !*argv[2] || argv[2][0] == '-' || node > UINT_MAX) return 2;
		errno = 0; port = strtoul(argv[3], &end, 0);
		if (errno || *end || !*argv[3] || argv[3][0] == '-' || port == 0 || port > UINT_MAX) return 2;
		errno = 0; pid = strtoul(argv[5], &end, 10);
		if (errno || *end || !*argv[5] || argv[5][0] == '-' || pid <= 1 || pid > INT_MAX) return 2;
		return do_listen_restart((unsigned int)node, (unsigned int)port,
					argv[4], (pid_t)pid, argv[6]);
	}
	if (argc == 5 && !strcmp(argv[1], "--send"))
		return do_send((unsigned int)strtoul(argv[2], NULL, 0),
			       (unsigned int)strtoul(argv[3], NULL, 0), argv[4]);

	fprintf(stderr,
		"usage: %s --packet <pd-path>\n"
		"       %s --parse <hex>\n"
		"       %s --send <node> <port> <pd-path>\n"
		"       %s --listen-restart <node> <port> <pd-path> <provider-pid> <provider-exe>\n",
		argv[0], argv[0], argv[0], argv[0]);
	return 1;
}
