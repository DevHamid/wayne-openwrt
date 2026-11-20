#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define main query_main
#include "locator_query.c"
#undef main

static int sockets, sends, closes;
static const char *test_case;

int __wrap_socket(int family, int type, int protocol)
{
    assert(family == AF_QIPCRTR && type == SOCK_DGRAM && protocol == 0);
    assert(++sockets == 1);
    return 77;
}

ssize_t __wrap_sendto(int fd, const void *buf, size_t size, int flags,
                     const struct sockaddr *address, socklen_t address_len)
{
    static const unsigned char expected[] = {
        0, 0x34, 0x12, 0x21, 0, 10, 0, 1, 7, 0, 'w','l','a','n','/','f','w'
    };
    const struct sockaddr_qrtr *dest = (const struct sockaddr_qrtr *)address;
    assert(++sends == 1 && fd == 77 && flags == 0);
    assert(address_len == sizeof(*dest) && dest->sq_family == AF_QIPCRTR);
    assert(dest->sq_node == 1 && dest->sq_port == 777);
    assert(size == sizeof(expected) && !memcmp(buf, expected, size));
    if (!strcmp(test_case, "send-eintr")) { errno = EINTR; return -1; }
    if (!strcmp(test_case, "partial-send")) return size - 1;
    return size;
}

int __wrap_poll(struct pollfd *fds, nfds_t count, int timeout)
{
    assert(count == 1 && fds->fd == 77 && timeout == 2000);
    if (!strcmp(test_case, "timeout")) return 0;
    if (!strcmp(test_case, "poll-eintr")) { errno = EINTR; return -1; }
    fds->revents = POLLIN;
    return 1;
}

ssize_t __wrap_recvfrom(int fd, void *buf, size_t size, int flags,
                       struct sockaddr *address, socklen_t *address_len)
{
    struct sockaddr_qrtr *peer = (struct sockaddr_qrtr *)address;
    long length;
    FILE *file;
    assert(fd == 77 && flags == (MSG_DONTWAIT | MSG_TRUNC));
    if (!strcmp(test_case, "recv-eintr")) { errno = EINTR; return -1; }
    file = fopen(getenv("FAKE_REPLY"), "rb");
    assert(file != NULL && !fseek(file, 0, SEEK_END));
    length = ftell(file);
    assert(length >= 0 && !fseek(file, 0, SEEK_SET));
    assert(fread(buf, 1, (size_t)length < size ? (size_t)length : size, file) ==
           ((size_t)length < size ? (size_t)length : size));
    fclose(file);
    memset(peer, 0, sizeof(*peer));
    peer->sq_family = !strcmp(test_case, "wrong-family") ? AF_INET : AF_QIPCRTR;
    peer->sq_node = !strcmp(test_case, "wrong-node") ? 0 : 1;
    peer->sq_port = !strcmp(test_case, "wrong-port") ? 778 : 777;
    *address_len = !strcmp(test_case, "short-address") ? 1 : sizeof(*peer);
    return length;
}

int __wrap_close(int fd)
{
    assert(fd == 77 && ++closes == 1);
    return 0;
}

int main(int argc, char **argv)
{
    int result;
    test_case = getenv("FAKE_CASE");
    assert(test_case != NULL);
    result = query_main(argc, argv);
    if (result == 2) assert(sockets == 0 && sends == 0 && closes == 0);
    else assert(sockets == 1 && sends == 1 && closes == 1);
    return result;
}
