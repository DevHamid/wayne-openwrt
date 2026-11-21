#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <linux/qrtr.h>

#define main mapper_main
#include "source/pd-mapper.c"
#undef main

static unsigned char captured[4096];
static size_t captured_len;
static uint32_t destination_node, destination_port;
static int fail_response_send;

int __wrap_socket(int domain, int type, int protocol)
{
    fputs("unexpected_socket: offline fixture forbids network access\n", stderr);
    exit(99);
}

int __wrap_getsockname(int fd, struct sockaddr *addr, socklen_t *len)
{
    struct sockaddr_qrtr *sq = (struct sockaddr_qrtr *)addr;
    assert(*len >= sizeof(*sq));
    memset(sq, 0, sizeof(*sq));
    sq->sq_family = AF_QIPCRTR;
    sq->sq_node = 1;
    sq->sq_port = 555;
    *len = sizeof(*sq);
    return 0;
}

ssize_t __wrap_sendto(int fd, const void *data, size_t len, int flags,
                     const struct sockaddr *addr, socklen_t addrlen)
{
    const struct sockaddr_qrtr *sq = (const struct sockaddr_qrtr *)addr;
    assert(len <= sizeof(captured) && addrlen == sizeof(*sq));
    assert(sq->sq_family == AF_QIPCRTR);
    memcpy(captured, data, len);
    captured_len = len;
    destination_node = sq->sq_node;
    destination_port = sq->sq_port;
    if (fail_response_send && len >= 7 && captured[0] == 2) { errno = EIO; return -1; }
    return len;
}

int main(int argc, char **argv)
{
    if (argc > 1 && (!strcmp(argv[1], "--wire") ||
                     !strcmp(argv[1], "--wire-trace") ||
                     !strcmp(argv[1], "--wire-trace-limit") ||
                     !strcmp(argv[1], "--wire-trace-malformed") ||
                     !strcmp(argv[1], "--wire-trace-send-error"))) {
        unsigned char request[512] = {0, 0x34, 0x12, 0x21, 0};
        struct qrtr_packet packet = {.type = QRTR_TYPE_DATA, .node = 0,
                                     .port = 777, .data = request};
        size_t size, i;
        assert(argc == 4);
        trace_queries = strcmp(argv[1], "--wire") != 0;
        fail_response_send = !strcmp(argv[1], "--wire-trace-send-error");
        assert(pd_load_maps(argv[2]) == 0 && pd_maps != NULL);
        assert(qrtr_publish(7, SERVREG_QMI_SERVICE, SERVREG_QMI_VERSION,
                            SERVREG_QMI_INSTANCE) == 0);
        printf("advertisement=");
        for (i = 0; i < captured_len; i++) printf("%02x", captured[i]);
        putchar('\n');
        size = strlen(argv[3]);
        assert(size > 0 && size < 128);
        request[5] = (size + 3) & 255;
        request[6] = (size + 3) >> 8;
        request[7] = 1;
        request[8] = size & 255;
        request[9] = size >> 8;
        memcpy(request + 10, argv[3], size);
        packet.data_len = size + 10;
        if (!strcmp(argv[1], "--wire-trace-malformed")) request[0] = QMI_RESPONSE;
        captured_len = 0;
        for (int j = 0; j < (!strcmp(argv[1], "--wire-trace-limit") ? 70 : 1); j++)
            handle_get_domain_list(7, &packet);
        assert(captured_len > 0 && destination_node == 0 && destination_port == 777);
        printf("wire_response=");
        for (i = 0; i < captured_len; i++) printf("%02x", captured[i]);
        putchar('\n');
        return 0;
    }
    return mapper_main(argc, argv);
}
