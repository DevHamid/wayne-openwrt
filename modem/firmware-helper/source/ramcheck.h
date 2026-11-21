/* SPDX-License-Identifier: BSD-3-Clause */
/* Included after the TFTP option/response helpers. No filesystem operations. */
#define RAMCHECK_PATH "/readwrite/server_check.txt"
#define RAMCHECK_LIMIT 64
#define RAMCHECK_ATTEMPTS 8

static unsigned ramcheck_attempts;
static unsigned char ramcheck_bytes[RAMCHECK_LIMIT];
static size_t ramcheck_size;
static bool ramcheck_present;

static bool ramcheck_options_valid(const char *p, const char *end)
{
	static const char * const names[] = {
		"blksize", "timeoutms", "tsize", "wsize", "rsize", "seek"
	};
	unsigned seen = 0;
	while (p < end) {
		size_t n = strnlen(p, end - p), i;
		if (!n || n == (size_t)(end - p))
			return false;
		for (i = 0; i < sizeof(names) / sizeof(names[0]); i++)
			if (!strcmp(p, names[i]))
				break;
		if (i == sizeof(names) / sizeof(names[0]) || (seen & (1u << i)))
			return false;
		seen |= 1u << i;
		p += n + 1;
		n = strnlen(p, end - p);
		if (!n || n == (size_t)(end - p) || n > 10)
			return false;
		for (i = 0; i < n; i++)
			if (p[i] < '0' || p[i] > '9')
				return false;
		p += n + 1;
	}
	return true;
}

static ssize_t ramcheck_recv(int sock, unsigned char *data, size_t capacity,
                            const struct sockaddr_qrtr *peer)
{
	struct sockaddr_qrtr from = {0};
	socklen_t from_len = sizeof(from);
	ssize_t n = recvfrom(sock, data, capacity, MSG_TRUNC,
	                     (struct sockaddr *)&from, &from_len);
	if (n < 4 || (size_t)n > capacity || from_len != sizeof(from) ||
	    from.sq_family != peer->sq_family || from.sq_node != peer->sq_node ||
	    from.sq_port != peer->sq_port)
		return -1;
	return n;
}

static bool handle_ramcheck(const char *buf, size_t len,
                           struct sockaddr_qrtr *peer)
{
	const char *p, *end = buf + len;
	size_t blksize = 512, wsize = 1, rsize = 0;
	ssize_t tsize = -1;
	off_t seek = -1;
	unsigned int timeoutms = 1000;
	struct timeval timeout = { .tv_sec = 2 };
	unsigned char data[RAMCHECK_LIMIT + 5];
	ssize_t n;
	int sock, ret;
	bool options, writing;

	if (!ramcheck_enabled || len < 2 + sizeof(RAMCHECK_PATH) ||
	    memcmp(buf + 2, RAMCHECK_PATH, sizeof(RAMCHECK_PATH)))
		return false;
	if ((unsigned char)buf[0] != 0 ||
	    ((unsigned char)buf[1] != OP_WRQ && (unsigned char)buf[1] != OP_RRQ))
		return false;
	writing = (unsigned char)buf[1] == OP_WRQ;
	if (len > 512 || peer->sq_family != AF_QIPCRTR || peer->sq_node != 0 ||
	    peer->sq_port == QRTR_PORT_CTRL ||
	    ramcheck_attempts >= RAMCHECK_ATTEMPTS)
		goto deny;
	ramcheck_attempts++;
	p = buf + 2 + sizeof(RAMCHECK_PATH);
	if ((size_t)(end - p) < sizeof("octet") ||
	    memcmp(p, "octet", sizeof("octet")))
		goto deny;
	p += sizeof("octet");
	options = p < end;
	if (options && !ramcheck_options_valid(p, end))
		goto deny;
	if (options && parse_options(p, end - p, &blksize, &tsize, &wsize,
	                            &timeoutms, &rsize, &seek) < 0)
		goto deny;
	/* Only one small final DATA block; never allow sparse or bulk writes. */
	if (tsize > RAMCHECK_LIMIT || rsize > RAMCHECK_LIMIT ||
	    (writing && rsize != 0) || seek > 0 ||
	    timeoutms > 2000)
		goto deny;
	if (!writing && (!ramcheck_present || ramcheck_size >= blksize))
		goto deny;
	wsize = 1;
	sock = qrtr_open(0);
	if (sock < 0)
		return true;
	if (setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0 ||
	    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
	    connect(sock, (struct sockaddr *)peer, sizeof(*peer)) < 0)
		goto close;
	if (!writing) {
		size_t count = ramcheck_size;
		if (rsize && rsize < count)
			count = rsize;
		if (options) {
			size_t total = ramcheck_size;
			ret = tftp_send_oack(sock, &blksize, &total, &wsize,
			                     &timeoutms, rsize ? &rsize : NULL, NULL);
			if (ret < 2)
				goto close;
			n = ramcheck_recv(sock, data, sizeof(data), peer);
			if (n != 4 || data[0] || data[1] != OP_ACK || data[2] || data[3])
				goto close;
		}
		data[0] = 0; data[1] = OP_DATA; data[2] = 0; data[3] = 1;
		memcpy(data + 4, ramcheck_bytes, count);
		if (send(sock, data, count + 4, 0) != (ssize_t)(count + 4))
			goto close;
		n = ramcheck_recv(sock, data, sizeof(data), peer);
		if (n == 4 && !data[0] && data[1] == OP_ACK && !data[2] && data[3] == 1)
			log_info("ramcheck_read=complete bytes=%zu storage=process-memory\n", count);
		goto close;
	}
	if (options) {
		ret = tftp_send_oack(sock, &blksize,
		                     tsize >= 0 ? (size_t *)&tsize : NULL,
		                     &wsize, &timeoutms, NULL, NULL);
		if (ret < 2)
			goto close;
	} else if (tftp_send_ack(sock, 0) != 4) {
		goto close;
	}
	n = ramcheck_recv(sock, data, sizeof(data), peer);
	if (n < 4 || n > RAMCHECK_LIMIT + 4 || data[0] != 0 ||
	    data[1] != OP_DATA || data[2] != 0 || data[3] != 1 ||
	    (size_t)(n - 4) >= blksize || (tsize >= 0 && n - 4 != tsize)) {
		tftp_send_error(sock, TFTP_ERROR_EBADOP, "Invalid RAM check block");
		goto close;
	}
	if (tftp_send_ack(sock, 1) != 4)
		goto close;
	memcpy(ramcheck_bytes, data + 4, n - 4);
	ramcheck_size = n - 4;
	ramcheck_present = true;
	log_info("ramcheck_write=accepted bytes=%zu storage=process-memory\n",
	         ramcheck_size);
close:
	if (close(sock) < 0)
		log_err("ramcheck_close=failed\n");
	return true;
deny:
	tftp_send_error_to(peer, TFTP_ERROR_EACCESS, "RAM check policy");
	return true;
}
